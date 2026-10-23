"""Aktarım çekirdeği: ham kaydı eşleştir, öncelikle birleştir, kaydet; kaldığı yerden devam et."""
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import repo
from app.kaynaklar import HamKayit, KaynakHatasi
from app.models import Durum, Hassasiyet, Kaynak, KaynakDurumu, Kategori, Sehit
from app.schemas import SehitVeri
from app.text import isim_anahtari, katla

logger = logging.getLogger(__name__)

ONCELIK: dict[str, int] = {
    "panel": 4, "egm": 3, "sg": 3, "sehitlerimiz": 2, "kahramanlar": 1, "haber": 0, "ornek": 0,
}

_HASSASIYET_SIRASI = {Hassasiyet.bilinmiyor: 0, Hassasiyet.yil: 1, Hassasiyet.tam: 2}
_DOLDURULACAK = ("soyad", "lakap", "gorev", "kurum", "memleket", "baba_adi", "dogum_yili", "donem")


@dataclass
class Sonuc:
    durum: Literal["yeni", "birlesti", "atlandi", "hatali"]
    sehit_id: int | None
    mesaj: str | None = None


def _oncelik(kod: str | None) -> int:
    return ONCELIK.get(kod or "", 0)


def _kirp(deger: str | None, uzunluk: int) -> str | None:
    if deger is None:
        return None
    deger = deger.strip()
    return deger[:uzunluk] or None


def ham_to_veri(ham: HamKayit) -> SehitVeri:
    hassasiyet = Hassasiyet(ham.hassasiyet)
    yil = ham.yil
    if yil is None and ham.tarih is not None:
        yil = ham.tarih.year
    return SehitVeri(
        ad=_kirp(ham.ad, 200) or "",
        soyad=_kirp(ham.soyad, 200),
        lakap=_kirp(ham.lakap, 200),
        tarih_hassasiyeti=hassasiyet,
        sehadet_tarihi=ham.tarih,
        yil=yil,
        gorev=_kirp(ham.gorev, 200),
        kategori=ham.kategori,
        kurum=_kirp(ham.kurum, 200),
        memleket=_kirp(ham.memleket, 200),
        baba_adi=_kirp(ham.baba_adi, 200),
        dogum_yili=ham.dogum_yili,
        donem=_kirp(ham.donem, 100),
        resmi_teyit=True,
        isimsiz=False,
        kaynak_kodu=ham.kaynak_kodu[:50],
    )


def _ayni(a: str | None, b: str | None) -> bool:
    return bool(a and b and katla(a) == katla(b))


def _ham_yil(ham: HamKayit) -> int | None:
    if ham.yil is not None:
        return ham.yil
    return ham.tarih.year if ham.tarih else None


def eslesen_bul(s: Session, ham: HamKayit) -> Sehit | None:
    """Durumdan bağımsız, isim anahtarı + tarih/ek alan kurallarıyla aynı kişiyi bulur."""
    anahtar = isim_anahtari(_kirp(ham.ad, 200) or "", _kirp(ham.soyad, 200), _kirp(ham.lakap, 200))
    if not anahtar:
        return None
    adaylar = list(s.scalars(select(Sehit).where(Sehit.isim_anahtari == anahtar).order_by(Sehit.id)))
    if not adaylar:
        return None

    h_hass = Hassasiyet(ham.hassasiyet)
    if h_hass == Hassasiyet.tam and ham.tarih is None:
        h_hass = Hassasiyet.bilinmiyor
    h_yil = _ham_yil(ham)

    def hass(a: Sehit) -> Hassasiyet:
        return Hassasiyet(a.tarih_hassasiyeti)

    def tek(kural: str, uyanlar: list[Sehit]) -> Sehit | None:
        if len(uyanlar) > 1:
            logger.warning(
                "%s/%s: belirsiz eşleşme (kural %s, aday id'ler %s); yeni kayıt açılıyor",
                ham.kaynak_kodu, ham.dis_kimlik, kural, [a.id for a in uyanlar],
            )
            return None
        return uyanlar[0] if uyanlar else None

    # 1. iki tam tarih eşit
    if h_hass == Hassasiyet.tam:
        uyanlar = [a for a in adaylar if hass(a) == Hassasiyet.tam and a.sehadet_tarihi == ham.tarih]
        if uyanlar:
            return tek("1", uyanlar)
    # 2. biri yıl hassasiyetli, yıllar eşit
    if h_yil is not None and h_hass != Hassasiyet.bilinmiyor:
        uyanlar = [
            a for a in adaylar
            if hass(a) != Hassasiyet.bilinmiyor and Hassasiyet.yil in (h_hass, hass(a)) and a.yil == h_yil
        ]
        if uyanlar:
            return tek("2", uyanlar)
    # 3. en az biri tarihsiz/yıl-hassas + baba adı / dönem / kurum eşit
    uyanlar = []
    for a in adaylar:
        if hass(a) == Hassasiyet.tam and h_hass == Hassasiyet.tam:
            continue
        if h_yil is not None and a.yil is not None and h_yil != a.yil:
            continue  # bilinen yıllar çelişiyorsa asla eşleşmez
        if _ayni(ham.baba_adi, a.baba_adi) or _ayni(ham.donem, a.donem) or _ayni(ham.kurum, a.kurum):
            uyanlar.append(a)
    if uyanlar:
        return tek("3", uyanlar)
    # 4. tek aday, ikisinin de tarihi yok
    if len(adaylar) == 1 and h_hass == Hassasiyet.bilinmiyor and hass(adaylar[0]) == Hassasiyet.bilinmiyor:
        return adaylar[0]
    return None


def _tarihi_guncelle(sehit: Sehit, veri: SehitVeri, *, esit_olsa_da: bool, kilitli: bool) -> None:
    mevcut = _HASSASIYET_SIRASI[Hassasiyet(sehit.tarih_hassasiyeti)]
    yeni = _HASSASIYET_SIRASI[veri.tarih_hassasiyeti]
    if kilitli and mevcut > 0:
        return  # elle düzenlenmiş kaydın bilinen tarihi korunur
    if yeni > mevcut or (esit_olsa_da and yeni == mevcut and yeni > 0):
        sehit.tarih_hassasiyeti = veri.tarih_hassasiyeti
        sehit.sehadet_tarihi = veri.sehadet_tarihi
        sehit.yil = veri.yil


def _birlestir(sehit: Sehit, veri: SehitVeri) -> None:
    # Panelde elle düzenlenmiş kayıt en yüksek öncelikli sayılır: yalnızca boşlar dolar.
    mevcut_oncelik = ONCELIK["panel"] if sehit.elle_duzenlendi else _oncelik(sehit.kaynak_kodu)
    ham_ustun = _oncelik(veri.kaynak_kodu) > mevcut_oncelik
    if ham_ustun:
        sehit.ad = veri.ad
        for alan in ("soyad", "lakap", "gorev"):
            if getattr(veri, alan):
                setattr(sehit, alan, getattr(veri, alan))
        if Kategori(veri.kategori) != Kategori.diger:
            sehit.kategori = veri.kategori
        sehit.kaynak_kodu = veri.kaynak_kodu
    elif Kategori(sehit.kategori) == Kategori.diger and Kategori(veri.kategori) != Kategori.diger:
        sehit.kategori = veri.kategori
    # Hassasiyet asla düşmez: eşleşen kayıtların bilinen yılları zaten çelişmez.
    _tarihi_guncelle(sehit, veri, esit_olsa_da=ham_ustun, kilitli=bool(sehit.elle_duzenlendi))
    for alan in _DOLDURULACAK:
        if getattr(sehit, alan) in (None, "") and getattr(veri, alan) not in (None, ""):
            setattr(sehit, alan, getattr(veri, alan))
    sehit.resmi_teyit = bool(sehit.resmi_teyit or veri.resmi_teyit)
    sehit.alanlari_yenile()  # durum'a dokunulmaz


def _kaynak_kaydi(sehit: Sehit, ham: HamKayit) -> Kaynak:
    return Kaynak(
        sehit=sehit,
        url=ham.kaynak_url,
        metin=ham.metin,
        kaynak_adi=(ham.kaynak_adi or ham.kaynak_kodu)[:100],
        kaynak_kodu=ham.kaynak_kodu,
        dis_kimlik=ham.dis_kimlik,
    )


def kayit_aktar(s: Session, ham: HamKayit, *, yeni_durum: Durum = Durum.yayinda) -> Sonuc:
    """Tek kaydı savepoint içinde işler; asla fırlatmaz. Commit çağırana aittir."""
    if not ham.ad or not ham.ad.strip():
        return Sonuc("hatali", None, "Ad boş.")
    try:
        with s.begin_nested():
            var = s.scalar(
                select(Kaynak.id).where(
                    Kaynak.kaynak_kodu == ham.kaynak_kodu, Kaynak.dis_kimlik == ham.dis_kimlik
                )
            )
            if var is not None:
                return Sonuc("atlandi", None)
            veri = ham_to_veri(ham)
            mevcut = eslesen_bul(s, ham)
            if mevcut is None:
                sehit = repo.yeni_sehit(s, veri, durum=yeni_durum, commit=False)
                s.add(_kaynak_kaydi(sehit, ham))
                s.flush()
                return Sonuc("yeni", sehit.id)
            _birlestir(mevcut, veri)
            s.add(_kaynak_kaydi(mevcut, ham))
            s.flush()
            return Sonuc("birlesti", mevcut.id)
    except Exception as hata:  # noqa: BLE001 - tek kayıt tüm aktarımı düşürmemeli
        return Sonuc("hatali", None, _temizle(f"{type(hata).__name__}: {hata}"))


def kaynak_durumu(s: Session, kaynak_kodu: str) -> KaynakDurumu:
    durum = s.get(KaynakDurumu, kaynak_kodu)
    if durum is None:
        durum = KaynakDurumu(
            kaynak_kodu=kaynak_kodu, tamamlandi=False, eklenen=0, birlesen=0, atlanan=0, hatali=0
        )
        s.add(durum)
        s.flush()
    return durum


def _temizle(mesaj: str | None) -> str:
    """SQL ve parametre dökümünü atar, 500 karaktere kırpar."""
    mesaj = (mesaj or "").split("[SQL:")[0].split("(Background on")[0].strip()
    return mesaj[:500]


def _simdi() -> datetime:
    return datetime.now(timezone.utc)


def kaynak_calistir(
    s: Session,
    kaynak_kodu: str,
    sayfalar: Iterable[tuple[str, list[HamKayit]]],
    *,
    yeni_durum: Durum = Durum.yayinda,
) -> KaynakDurumu:
    durum = kaynak_durumu(s, kaynak_kodu)
    durum.tamamlandi = False
    s.commit()  # sıfırlama, ilk sayfadan önce hata gelse de kalıcı olsun
    son_hata: str | None = None
    sayac = {"yeni": "eklenen", "birlesti": "birlesen", "atlandi": "atlanan", "hatali": "hatali"}

    def hata_yaz(mesaj: str) -> None:
        d = kaynak_durumu(s, kaynak_kodu)
        d.son_durum, d.son_mesaj, d.son_calisma = "hata", mesaj, _simdi()
        s.commit()

    try:
        for imlec, kayitlar in sayfalar:
            for ham in kayitlar:
                sonuc = kayit_aktar(s, ham, yeni_durum=yeni_durum)
                if sonuc.durum == "hatali":
                    son_hata = _temizle(sonuc.mesaj)
                    logger.warning("%s/%s aktarılamadı: %s", ham.kaynak_kodu, ham.dis_kimlik, son_hata)
                alan = sayac[sonuc.durum]
                setattr(durum, alan, (getattr(durum, alan) or 0) + 1)
            durum.imlec = imlec
            durum.son_calisma = _simdi()
            s.commit()
    except KaynakHatasi as hata:
        s.rollback()
        hata_yaz(str(hata))
        return kaynak_durumu(s, kaynak_kodu)
    except Exception as hata:
        s.rollback()
        hata_yaz(f"{type(hata).__name__}: {hata}")
        raise
    durum.tamamlandi = True
    durum.son_durum, durum.son_mesaj, durum.son_calisma = "basarili", son_hata, _simdi()
    s.commit()
    return durum
