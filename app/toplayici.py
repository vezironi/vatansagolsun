"""Haber kaynağı taraması: RSS -> anahtar sözcük süzgeci -> Claude analizi -> onay bekleyen taslaklar."""
import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections.abc import Callable, Iterator, Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import or_, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.aktarim import kaynak_durumu, temizle, kayit_aktar
from app.analiz import AnalizHatasi, Analizci, AnalizYapilandirilmamis, HaberAnalizi, TUKENDI_MESAJI, analizci_olustur
from app.config import get_settings
from app.dates import TZ
from app.kaynaklar import HamKayit, KaynakHatasi, ayristir, egm, haber, sg
from app.kaynaklar.getirici import Getirici
from app.models import Durum, Hassasiyet, Kategori, KaynakDurumu
from app.text import ad_duzenle, slug, soyad_duzenle

logger = logging.getLogger(__name__)

TELAFI_GUN = 3
SAYAC_KODU = "analiz_sayaci"
_SAYAC_ALANI = {"yeni": "eklenen", "birlesti": "birlesen", "atlandi": "atlanan", "hatali": "hatali"}


TAKILI_DENEME = 3
EN_COK_KISI = 20  # tek haberden en fazla bu kadar taslak (istem enjeksiyonuna karşı tavan)


@dataclass
class HaberImleci:
    """Haber kaynağının imleci (JSON, `KaynakDurumu.imlec` TEXT).

    `islenen`: son `TELAFI_GUN` günde işlenmiş (ya da takılıp atlanmış) öğeler, {kimlik: yayın ISO}.
    Sonradan eklenen eski tarihli haberler de (Hürriyet'in toplu, geriye tarihli yayınları)
    böylece kaçmaz: zaman değil kimlik belirleyicidir.
    `taban`: bundan önce yayımlanan öğeler işlenmiş sayılır — ilk çalışmada bugünün (İstanbul)
    başı, eski biçimden okunurken eski imleç zamanı. Telafi penceresinden çıkınca düşer.
    `son_yayin`: işlenen en yeni öğe (yalnızca durum gösterimi). `takili`: art arda hata veren öğe.
    """
    son_yayin: datetime | None = None
    islenen: dict[str, str] = field(default_factory=dict)
    taban: datetime | None = None
    takili: dict | None = None  # {"kimlik": ..., "deneme": n}

    @classmethod
    def oku(cls, metin: str | None) -> "HaberImleci | None":
        """İmleç yoksa ya da okunamıyorsa None (ilk çalışma). Eski biçimler de okunur."""
        if not metin:
            return None
        try:
            if not metin.lstrip().startswith("{"):
                # En eski biçim: yalnızca son işlenen ISO zaman; o ana kadar (dahil) işlenmiş.
                return cls(taban=datetime.fromisoformat(metin) + timedelta(microseconds=1))
            v = json.loads(metin)
            son = datetime.fromisoformat(v["son_yayin"]) if v.get("son_yayin") else None
            if "islenen" not in v:
                # Önceki biçim {son_yayin, son_kimlikler}: son_yayin'dan eskiler işlenmiş;
                # o andakilerden yalnızca son_kimlikler işlenmiş.
                kimlikler = v.get("son_kimlikler") or []
                return cls(son_yayin=son, taban=son, takili=v.get("takili"),
                           islenen={k: son.isoformat() for k in kimlikler} if son else {})
            taban = datetime.fromisoformat(v["taban"]) if v.get("taban") else None
            return cls(son_yayin=son, islenen=dict(v.get("islenen") or {}), taban=taban,
                       takili=v.get("takili"))
        except (ValueError, AttributeError, TypeError, KeyError):
            return None

    def yaz(self) -> str:
        return json.dumps({
            "son_yayin": self.son_yayin.isoformat() if self.son_yayin else None,
            "taban": self.taban.isoformat() if self.taban else None,
            "islenen": self.islenen, "takili": self.takili,
        }, separators=(",", ":"))

    def ozet(self) -> str:
        """Komut satırı için kısa gösterim (kimlik kümesi yazılmaz)."""
        son = self.son_yayin.isoformat() if self.son_yayin else "-"
        return f"son_yayin={son} islenen={len(self.islenen)}" + (f" takili={self.takili}" if self.takili else "")

    def buda(self, simdi: datetime) -> None:
        """Telafi penceresinin (simdi - TELAFI_GUN) dışında kalan kayıtları atar."""
        esik = simdi - timedelta(days=TELAFI_GUN)
        kalan = {}
        for kimlik, yayin in self.islenen.items():
            try:
                if datetime.fromisoformat(yayin) > esik:
                    kalan[kimlik] = yayin
            except (TypeError, ValueError):
                continue
        self.islenen = kalan
        if self.taban is not None and self.taban <= esik:
            self.taban = None  # pencere zaten daha eskisini dışarıda bırakır

    def islenecek_mi(self, oge, simdi: datetime) -> bool:
        if oge.yayin > simdi:  # gelecek tarihli öğe: sonraki çalışmaya kalır
            return False
        if oge.yayin <= simdi - timedelta(days=TELAFI_GUN):
            return False
        if self.taban is not None and oge.yayin < self.taban:
            return False
        return oge.kimlik not in self.islenen

    def isle(self, oge) -> None:
        self.islenen[oge.kimlik] = oge.yayin.isoformat()
        if self.son_yayin is None or oge.yayin > self.son_yayin:
            self.son_yayin = oge.yayin
        if self.takili and self.takili.get("kimlik") == oge.kimlik:
            self.takili = None

    def hata(self, oge) -> int:
        """Aynı öğenin art arda hata sayısını artırıp döndürür."""
        onceki = self.takili["deneme"] if self.takili and self.takili.get("kimlik") == oge.kimlik else 0
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
        sehadet_olayi=analiz.olay_ozeti or None, metin=f"{makale.baslik}\n\n{makale.govde[:4000]}",
    )


def _isimsiz_taslagi(kod: str, kaynak, oge, makale, analiz: HaberAnalizi) -> HamKayit:
    gun = oge.yayin.astimezone(TZ).date()
    metin = f"İsimsiz şehit sayısı: {analiz.isimsiz_sayisi}. {analiz.olay_ozeti}\n\n{makale.baslik}\n\n{makale.govde[:4000]}"
    return HamKayit(
        kaynak_kodu="haber", dis_kimlik=f"{kod}:{oge.kimlik}#isimsiz", ad="İsimsiz", isimsiz=True,
        tarih=gun, hassasiyet=Hassasiyet.tam, yil=gun.year, resmi_teyit=analiz.resmi_kurum_duyurusu,
        kaynak_adi=kaynak.ad, kaynak_url=oge.url, sehadet_olayi=analiz.olay_ozeti or None, metin=metin,
    )


def _taslaklar(kod, kaynak, oge, makale, analiz: HaberAnalizi) -> list[HamKayit]:
    kisiler = analiz.kisiler
    if len(kisiler) > EN_COK_KISI:
        logger.warning("%s/%s: analiz %d kişi döndürdü; ilk %d alındı", kod, oge.kimlik, len(kisiler), EN_COK_KISI)
        kisiler = kisiler[:EN_COK_KISI]
    taslaklar = [_kisi_taslagi(kod, kaynak, oge, makale, analiz, k) for k in kisiler]
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
    bugun_basi = simdi.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    # İlk çalışma (imleç yok): yalnızca bugünün haberleri; taban imleçte kalır.
    imlec = HaberImleci.oku(durum.imlec) or HaberImleci(taban=bugun_basi)
    imlec.buda(simdi)
    bugun = simdi.astimezone(TZ).date()

    try:
        ogeler = sorted((o for o in haber.ogeleri_getir(g, kaynak) if imlec.islenecek_mi(o, simdi)),
                        key=lambda o: o.yayin)
    except KaynakHatasi as hata:
        return _sonuc_yaz(s, durum, simdi, "hata", temizle(str(hata)))

    son_durum, mesaj, hatali_taslak = "basarili", None, 0
    for oge in ogeler:
        try:
            oge_hatali = 0
            if haber.sehit_gecer_mi(oge.baslik, oge.ozet):
                kullanilabilir = getattr(analizci, "kullanilabilir_mi", None)
                if kullanilabilir is not None and not kullanilabilir():
                    son_durum, mesaj = "hata", TUKENDI_MESAJI  # sayaç ve takılı koruması harcanmaz
                    break
                makale = haber.makale_ayristir(g.metin(kod, oge.url), kaynak)
                if not analiz_sayaci_artir(s, bugun, ayar.gunluk_analiz_siniri):
                    mesaj = "günlük analiz sınırı"  # kısıtlama, hata değil
                    break
                s.commit()  # sayaç, çağrıdan önce kalıcı: başarısız çağrı da para harcar
                analiz = analizci.analiz_et(baslik=makale.baslik or oge.baslik, govde=makale.govde, yayin=oge.yayin)
                if analiz.sehit_haberi and analiz.yeni_olay:
                    for ham in _taslaklar(kod, kaynak, oge, makale, analiz):
                        sonuc = kayit_aktar(s, ham, yeni_durum=Durum.onay_bekliyor)
                        alan = _SAYAC_ALANI[sonuc.durum]
                        setattr(durum, alan, (getattr(durum, alan) or 0) + 1)
                        if sonuc.durum == "hatali":
                            oge_hatali += 1
                            logger.warning("%s/%s taslağı aktarılamadı: %s", kod, ham.dis_kimlik, temizle(sonuc.mesaj))
            imlec.isle(oge)
            durum.imlec = imlec.yaz()
            s.commit()  # çökme olursa işlenen öğeler ve imleç korunur
            hatali_taslak += oge_hatali
        except AnalizYapilandirilmamis as hata:
            s.rollback()
            durum = kaynak_durumu(s, kod)
            son_durum, mesaj = "hata", temizle(str(hata)) or TUKENDI_MESAJI
            break
        except Exception as hata:  # noqa: BLE001 - takılan öğe her turda baştan denenmesin
            # Öğenin yarım işi geri alınır; takılı sayacı ayrı bir işlemde kalıcı olur ki
            # koruma çalışmalar arasında sayabilsin (analiz sayacı zaten commit edildi).
            s.rollback()
            if isinstance(hata, (KaynakHatasi, AnalizHatasi)):
                logger.warning("%s/%s işlenemedi: %s", kod, oge.kimlik, hata)
                neden = str(hata)
            else:
                logger.exception("%s/%s işlenirken beklenmeyen hata", kod, oge.kimlik)
                neden = f"{type(hata).__name__}: {hata}"
            durum = kaynak_durumu(s, kod)
            deneme = imlec.hata(oge)
            if deneme < TAKILI_DENEME:
                son_durum, mesaj = "hata", temizle(f"{oge.kimlik}: {neden}")
                durum.imlec = imlec.yaz()
                s.commit()
                break
            logger.warning("%s/%s %d. denemede atlandı", kod, oge.kimlik, deneme)
            durum.hatali = (durum.hatali or 0) + 1
            mesaj = f"{deneme}. denemede atlandı: {oge.kimlik}"
            imlec.isle(oge)
            durum.imlec = imlec.yaz()
            s.commit()
    durum.imlec = imlec.yaz()  # öğe olmasa da: ilk çalışmanın tabanı ve budama kalıcı olsun
    if hatali_taslak and mesaj is None:
        mesaj = f"{hatali_taslak} taslak aktarılamadı"
    return _sonuc_yaz(s, durum, simdi, son_durum, mesaj)


RESMI_KAYNAKLAR = ("egm", "sg")
EGM_TARAMA_SAYFALARI = ("sehitlerimiz:1", "sehitlerimiz:2")  # en yeniler listenin başında


def toplayici_kodu(kod: str) -> str:
    """Kaynağın toplayıcı çalışmasının durum satırı; resmî kaynaklarda toplu aktarımdan ayrıdır."""
    return f"{kod}_toplayici" if kod in RESMI_KAYNAKLAR else kod


def resmi_kaynak_tara(s: Session, kod: Literal["egm", "sg"], g) -> KaynakDurumu:
    """Resmî sayfanın en yeni kayıtlarını onay bekleyen olarak alır; toplu aktarım imlecine dokunmaz."""
    durum = kaynak_durumu(s, toplayici_kodu(kod))
    simdi = datetime.now(timezone.utc)
    if kod not in get_settings().kaynak_izinleri:
        return _sonuc_yaz(s, durum, simdi, "atlandi", "izin yok")
    toplu = s.get(KaynakDurumu, kod)
    if toplu is None or not toplu.tamamlandi:
        return _sonuc_yaz(s, durum, simdi, "atlandi", f"önce 'aktar {kod}' çalıştırın")

    sayfalar = egm.sayfalar(g, baslangic=None) if kod == "egm" else sg.sayfalar(g, baslangic=None)
    hatali = 0
    try:
        for imlec, kayitlar in sayfalar:
            for ham in kayitlar:
                sonuc = kayit_aktar(s, ham, yeni_durum=Durum.onay_bekliyor)
                alan = _SAYAC_ALANI[sonuc.durum]
                setattr(durum, alan, (getattr(durum, alan) or 0) + 1)
                if sonuc.durum == "hatali":
                    hatali += 1
                    logger.warning("%s/%s taslağı aktarılamadı: %s", kod, ham.dis_kimlik, temizle(sonuc.mesaj))
            s.commit()
            if kod == "egm" and imlec == EGM_TARAMA_SAYFALARI[-1]:
                break  # üretici tembel: daha fazla sayfa istenmez
    except KaynakHatasi as hata:
        s.rollback()
        return _sonuc_yaz(s, kaynak_durumu(s, toplayici_kodu(kod)), simdi, "hata", temizle(str(hata)))
    return _sonuc_yaz(s, durum, simdi, "basarili", f"{hatali} kayıt aktarılamadı" if hatali else None)


KILIT_KODU = "toplayici_kilidi"  # SQLite/geliştirme: kilit satırı (imlec = alınma anı, UTC ISO)
KILIT_ANAHTARI = 7_301_190_323  # PostgreSQL advisory lock anahtarı (sabit)
KILIT_BAYAT_DAKIKA = 20  # çökmüş turun SQLite kilidi bu süreden sonra geçersiz sayılır
ZATEN_CALISIYOR = "toplayıcı zaten çalışıyor"


def _kilit_simdi() -> datetime:
    return datetime.now(timezone.utc)


def _kilit_metni(an: datetime) -> str:
    return an.astimezone(timezone.utc).isoformat(timespec="seconds")


def _postgresql_mi(bag) -> bool:
    return bag.dialect.name == "postgresql"


def toplayici_calisiyor_mu(s: Session) -> bool:
    """Şu an bir toplayıcı turu (zamanlanmış ya da elle) kilidi tutuyor mu?"""
    if _postgresql_mi(s.get_bind()):
        alindi = bool(s.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": KILIT_ANAHTARI}))
        if alindi:
            s.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": KILIT_ANAHTARI})
        return not alindi
    satir = s.get(KaynakDurumu, KILIT_KODU)
    esik = _kilit_metni(_kilit_simdi() - timedelta(minutes=KILIT_BAYAT_DAKIKA))
    return bool(satir is not None and satir.imlec and satir.imlec >= esik)


def _satir_kilidi_al(s: Session) -> bool:
    try:
        kaynak_durumu(s, KILIT_KODU)
        s.commit()
    except IntegrityError:  # başka süreç aynı anda satırı oluşturdu
        s.rollback()
    simdi = _kilit_simdi()
    esik = _kilit_metni(simdi - timedelta(minutes=KILIT_BAYAT_DAKIKA))
    sonuc = s.execute(
        update(KaynakDurumu)
        .where(KaynakDurumu.kaynak_kodu == KILIT_KODU,
               or_(KaynakDurumu.imlec.is_(None), KaynakDurumu.imlec < esik))
        .values(imlec=_kilit_metni(simdi), son_calisma=simdi)
    )
    s.commit()
    return sonuc.rowcount == 1


@contextmanager
def _toplayici_kilidi(session_factory: Callable[[], Session]) -> Iterator[bool]:
    """Elle `topla` ile zamanlanmış tur çakışmasın. PostgreSQL: oturum düzeyinde advisory lock
    (bağlantı kopunca kendiliğinden düşer). SQLite: zaman damgalı kilit satırı."""
    with session_factory() as s:
        motor = s.get_bind()
    if _postgresql_mi(motor):
        with motor.connect() as bag:  # kilit bu bağlantıya bağlı: tur boyunca açık kalır
            alindi = bool(bag.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": KILIT_ANAHTARI}))
            bag.commit()
            try:
                yield alindi
            finally:
                if alindi:
                    bag.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": KILIT_ANAHTARI})
                    bag.commit()
        return
    with session_factory() as s:
        alindi = _satir_kilidi_al(s)
    try:
        yield alindi
    finally:
        if alindi:
            try:
                with session_factory() as s:
                    s.execute(update(KaynakDurumu).where(KaynakDurumu.kaynak_kodu == KILIT_KODU).values(imlec=None))
                    s.commit()
            except Exception:  # noqa: BLE001 - bırakılamazsa 20 dakika sonra bayatlar
                logger.exception("toplayıcı kilidi bırakılamadı")


def toplayici_calistir(
    session_factory: Callable[[], Session], *, g=None, analizci: Analizci | None = None,
    simdi: datetime | None = None, kodlar: Sequence[str] | None = None,
) -> list[KaynakDurumu]:
    """Tek tur: egm, sg, ardından izinli haber kaynakları. `kodlar` verilirse yalnızca onlar.

    Başka bir tur kilidi tutuyorsa hiçbir iş yapmadan boş liste döner.
    """
    with _toplayici_kilidi(session_factory) as alindi:
        if not alindi:
            logger.warning(ZATEN_CALISIYOR)
            return []
        return _tur(session_factory, g=g, analizci=analizci, simdi=simdi, kodlar=kodlar)


def _tur(session_factory, *, g, analizci, simdi, kodlar) -> list[KaynakDurumu]:
    simdi = simdi or datetime.now(timezone.utc)
    g = g or Getirici()
    analizci = analizci or analizci_olustur(get_settings(), session_factory)
    if kodlar is None:
        izinler = get_settings().kaynak_izinleri
        kodlar = [*RESMI_KAYNAKLAR, *(k for k in haber.HABER_KAYNAKLARI if k in izinler)]
    sonuclar = []
    for kod in kodlar:
        satir = toplayici_kodu(kod)
        with session_factory() as s:
            try:
                if kod in RESMI_KAYNAKLAR:
                    durum = resmi_kaynak_tara(s, kod, g)
                else:
                    durum = haber_kaynagi_tara(s, kod, g, analizci, simdi=simdi)
            except Exception as hata:  # noqa: BLE001 - bir kaynak diğerlerini durdurmasın
                logger.exception("%s taraması başarısız", kod)
                mesaj = temizle(f"{type(hata).__name__}: {hata}")
                try:
                    s.rollback()
                    durum = _sonuc_yaz(s, kaynak_durumu(s, satir), simdi, "hata", mesaj)
                except Exception:  # noqa: BLE001 - veritabanı da yanıt vermiyorsa sonuç yine döner
                    logger.exception("%s hata durumu yazılamadı", kod)
                    durum = KaynakDurumu(kaynak_kodu=satir, son_durum="hata", son_mesaj=mesaj, son_calisma=simdi,
                                         eklenen=0, birlesen=0, atlanan=0, hatali=0)
            if durum in s:  # oturum kapandıktan sonra da okunabilsin
                s.refresh(durum)
                s.expunge(durum)
        sonuclar.append(durum)
    return sonuclar
