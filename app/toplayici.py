"""Haber kaynağı taraması: RSS -> anahtar sözcük süzgeci -> Claude analizi -> onay bekleyen taslaklar."""
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.aktarim import kaynak_durumu, temizle, kayit_aktar
from app.analiz import AnalizHatasi, Analizci, AnalizYapilandirilmamis, HaberAnalizi
from app.config import get_settings
from app.dates import TZ
from app.kaynaklar import HamKayit, KaynakHatasi, ayristir, haber
from app.models import Durum, Hassasiyet, Kategori, KaynakDurumu
from app.text import ad_duzenle, slug, soyad_duzenle

logger = logging.getLogger(__name__)

TELAFI_GUN = 3
SAYAC_KODU = "analiz_sayaci"
_SAYAC_ALANI = {"yeni": "eklenen", "birlesti": "birlesen", "atlandi": "atlanan", "hatali": "hatali"}


TAKILI_DENEME = 3


@dataclass
class HaberImleci:
    """`son_kimlikler`: `son_yayin` anında zaten işlenmiş öğeler. `takili`: art arda hata veren öğe."""
    son_yayin: datetime | None
    son_kimlikler: list[str] = field(default_factory=list)
    takili: dict | None = None  # {"kimlik": ..., "deneme": n}

    @classmethod
    def oku(cls, metin: str | None) -> "HaberImleci":
        if not metin:
            return cls(None)
        try:
            if metin.lstrip().startswith("{"):
                v = json.loads(metin)
                yayin = v.get("son_yayin")
                return cls(datetime.fromisoformat(yayin) if yayin else None,
                           list(v.get("son_kimlikler") or []), v.get("takili"))
            return cls(datetime.fromisoformat(metin))  # eski biçim: yalnızca ISO metin
        except (ValueError, AttributeError):
            return cls(None)

    def yaz(self) -> str:
        return json.dumps({
            "son_yayin": self.son_yayin.isoformat() if self.son_yayin else None,
            "son_kimlikler": self.son_kimlikler, "takili": self.takili,
        })

    def ilerle(self, oge) -> None:
        if oge.yayin == self.son_yayin:
            self.son_kimlikler.append(oge.kimlik)
        else:
            self.son_yayin, self.son_kimlikler = oge.yayin, [oge.kimlik]
        self.takili = None

    def hata(self, oge) -> int:
        """Aynı öğenin art arda hata sayısını artırıp döndürür."""
        onceki = self.takili["deneme"] if self.takili and self.takili["kimlik"] == oge.kimlik else 0
        self.takili = {"kimlik": oge.kimlik, "deneme": onceki + 1}
        return onceki + 1


def analiz_sayaci_artir(s: Session, bugun: date, sinir: int) -> bool:
    """Günlük analiz sayacını bir artırır; sınır doluysa artırmadan False döner."""
    durum = kaynak_durumu(s, SAYAC_KODU)
    gun, _, sayi = (durum.imlec or "").partition(":")
    n = int(sayi) if gun == bugun.isoformat() and sayi.isdigit() else 0
    if n >= sinir:
        return False
    durum.imlec = f"{bugun.isoformat()}:{n + 1}"
    s.flush()
    return True


def _kisi_taslagi(kod: str, kaynak, oge, makale, analiz: HaberAnalizi, kisi) -> HamKayit:
    ad = ad_duzenle(kisi.ad)
    soyad = soyad_duzenle(kisi.soyad) if kisi.soyad and kisi.soyad.strip() else None
    tarih, hassasiyet, yil = ayristir.tarih_coz(kisi.sehadet_tarihi)
    return HamKayit(
        kaynak_kodu="haber", dis_kimlik=f"{kod}:{oge.kimlik}#{slug(f'{ad} {soyad or ''}')}",
        ad=ad, soyad=soyad, gorev=kisi.gorev, kategori=Kategori(kisi.kategori),
        memleket=kisi.memleket, kurum=kisi.kurum, tarih=tarih, hassasiyet=hassasiyet, yil=yil,
        resmi_teyit=analiz.resmi_kurum_duyurusu, kaynak_adi=kaynak.ad, kaynak_url=oge.url,
        metin=f"{makale.baslik}\n\n{makale.govde[:4000]}",
    )


def _isimsiz_taslagi(kod: str, kaynak, oge, makale, analiz: HaberAnalizi) -> HamKayit:
    gun = oge.yayin.astimezone(TZ).date()
    metin = f"İsimsiz şehit sayısı: {analiz.isimsiz_sayisi}. {analiz.olay_ozeti}\n\n{makale.baslik}\n\n{makale.govde[:4000]}"
    return HamKayit(
        kaynak_kodu="haber", dis_kimlik=f"{kod}:{oge.kimlik}#isimsiz", ad="İsimsiz", isimsiz=True,
        tarih=gun, hassasiyet=Hassasiyet.tam, yil=gun.year, resmi_teyit=analiz.resmi_kurum_duyurusu,
        kaynak_adi=kaynak.ad, kaynak_url=oge.url, metin=metin,
    )


def _taslaklar(kod, kaynak, oge, makale, analiz: HaberAnalizi) -> list[HamKayit]:
    taslaklar = [_kisi_taslagi(kod, kaynak, oge, makale, analiz, k) for k in analiz.kisiler]
    if analiz.isimsiz_sayisi > 0:
        taslaklar.append(_isimsiz_taslagi(kod, kaynak, oge, makale, analiz))
    return taslaklar


def _sonuc_yaz(s: Session, durum: KaynakDurumu, simdi: datetime, son_durum: str, mesaj: str | None) -> KaynakDurumu:
    durum.son_calisma, durum.son_durum, durum.son_mesaj = simdi, son_durum, mesaj
    s.commit()
    return durum


def haber_kaynagi_tara(
    s: Session, kod: str, g, analizci: Analizci | None, *, simdi: datetime
) -> KaynakDurumu:
    durum = kaynak_durumu(s, kod)
    ayar = get_settings()
    if kod not in ayar.kaynak_izinleri:
        return _sonuc_yaz(s, durum, simdi, "atlandi", "izin yok")
    if analizci is None:
        return _sonuc_yaz(s, durum, simdi, "hata", "API anahtarı yok")

    kaynak = haber.HABER_KAYNAKLARI[kod]
    imlec = HaberImleci.oku(durum.imlec)
    son_yayin = imlec.son_yayin
    bugun_basi = simdi.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    alt_sinir = bugun_basi if son_yayin is None else max(son_yayin, simdi - timedelta(days=TELAFI_GUN))
    bugun = simdi.astimezone(TZ).date()

    def islenecek(o) -> bool:
        if o.yayin > simdi:  # gelecek tarihli öğe imleci ileri sürmesin; sonraki çalışmaya kalır
            return False
        return o.yayin > alt_sinir or (o.yayin == alt_sinir == son_yayin and o.kimlik not in imlec.son_kimlikler)

    try:
        ogeler = sorted((o for o in haber.ogeleri_getir(g, kaynak) if islenecek(o)), key=lambda o: o.yayin)
    except KaynakHatasi as hata:
        return _sonuc_yaz(s, durum, simdi, "hata", temizle(str(hata)))

    son_durum, mesaj, hatali_taslak = "basarili", None, 0
    for oge in ogeler:
        if haber.sehit_gecer_mi(oge.baslik, oge.ozet):
            try:
                makale = haber.makale_ayristir(g.metin(kod, oge.url), kaynak)
                if not analiz_sayaci_artir(s, bugun, ayar.gunluk_analiz_siniri):
                    mesaj = "günlük analiz sınırı"  # kısıtlama, hata değil
                    break
                s.commit()  # sayaç, çağrıdan önce kalıcı: başarısız çağrı da para harcar
                analiz = analizci.analiz_et(baslik=makale.baslik or oge.baslik, govde=makale.govde, yayin=oge.yayin)
            except AnalizYapilandirilmamis:
                son_durum, mesaj = "hata", "API anahtarı geçersiz/yok"
                break
            except (KaynakHatasi, AnalizHatasi) as hata:
                logger.warning("%s/%s işlenemedi: %s", kod, oge.kimlik, hata)
                deneme = imlec.hata(oge)
                if deneme < TAKILI_DENEME:
                    son_durum, mesaj = "hata", temizle(f"{oge.kimlik}: {hata}")
                    durum.imlec = imlec.yaz()
                    break
                logger.warning("%s/%s %d. denemede atlandı", kod, oge.kimlik, deneme)
                durum.hatali = (durum.hatali or 0) + 1
                mesaj = f"{deneme}. denemede atlandı: {oge.kimlik}"
                imlec.ilerle(oge)
                durum.imlec = imlec.yaz()
                s.commit()
                continue
            if analiz.sehit_haberi and analiz.yeni_olay:
                for ham in _taslaklar(kod, kaynak, oge, makale, analiz):
                    sonuc = kayit_aktar(s, ham, yeni_durum=Durum.onay_bekliyor)
                    alan = _SAYAC_ALANI[sonuc.durum]
                    setattr(durum, alan, (getattr(durum, alan) or 0) + 1)
                    if sonuc.durum == "hatali":
                        hatali_taslak += 1
                        logger.warning("%s/%s taslağı aktarılamadı: %s", kod, ham.dis_kimlik, temizle(sonuc.mesaj))
        imlec.ilerle(oge)
        durum.imlec = imlec.yaz()
        s.commit()  # çökme olursa işlenen öğeler ve imleç korunur
    if hatali_taslak and mesaj is None:
        mesaj = f"{hatali_taslak} taslak aktarılamadı"
    return _sonuc_yaz(s, durum, simdi, son_durum, mesaj)
