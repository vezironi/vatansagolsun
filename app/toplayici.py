"""Haber kaynağı taraması: RSS -> anahtar sözcük süzgeci -> Claude analizi -> onay bekleyen taslaklar."""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.aktarim import _temizle, kaynak_durumu, kayit_aktar
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


@dataclass
class HaberImleci:
    son_yayin: datetime | None

    @classmethod
    def oku(cls, metin: str | None) -> "HaberImleci":
        try:
            return cls(datetime.fromisoformat(metin) if metin else None)
        except ValueError:
            return cls(None)

    def yaz(self) -> str | None:
        return self.son_yayin.isoformat() if self.son_yayin else None


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
    son_yayin = HaberImleci.oku(durum.imlec).son_yayin
    bugun_basi = simdi.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    alt_sinir = bugun_basi if son_yayin is None else max(son_yayin, simdi - timedelta(days=TELAFI_GUN))
    bugun = simdi.astimezone(TZ).date()

    try:
        ogeler = sorted((o for o in haber.ogeleri_getir(g, kaynak) if o.yayin > alt_sinir), key=lambda o: o.yayin)
    except KaynakHatasi as hata:
        return _sonuc_yaz(s, durum, simdi, "hata", _temizle(str(hata)))

    son_durum, mesaj = "basarili", None
    for oge in ogeler:
        if haber.sehit_gecer_mi(oge.baslik, oge.ozet):
            if not analiz_sayaci_artir(s, bugun, ayar.gunluk_analiz_siniri):
                son_durum, mesaj = "hata", "günlük analiz sınırı"
                break
            try:  # sayaç, çağrı yapılmadan önce işlenir: başarısız çağrı da para harcar
                s.commit()
                makale = haber.makale_ayristir(g.metin(kod, oge.url), kaynak)
                analiz = analizci.analiz_et(baslik=makale.baslik or oge.baslik, govde=makale.govde, yayin=oge.yayin)
            except AnalizYapilandirilmamis:
                son_durum, mesaj = "hata", "API anahtarı geçersiz/yok"
                break
            except (KaynakHatasi, AnalizHatasi) as hata:
                logger.warning("%s/%s işlenemedi: %s", kod, oge.kimlik, hata)
                son_durum, mesaj = "hata", _temizle(f"{oge.kimlik}: {hata}")
                break
            if analiz.sehit_haberi and analiz.yeni_olay:
                for ham in _taslaklar(kod, kaynak, oge, makale, analiz):
                    sonuc = kayit_aktar(s, ham, yeni_durum=Durum.onay_bekliyor)
                    alan = _SAYAC_ALANI[sonuc.durum]
                    setattr(durum, alan, (getattr(durum, alan) or 0) + 1)
                    if sonuc.durum == "hatali":
                        logger.warning("%s/%s taslağı aktarılamadı: %s", kod, ham.dis_kimlik, _temizle(sonuc.mesaj))
        durum.imlec = HaberImleci(oge.yayin).yaz()
        s.commit()  # çökme olursa işlenen öğeler ve imleç korunur
    return _sonuc_yaz(s, durum, simdi, son_durum, mesaj)
