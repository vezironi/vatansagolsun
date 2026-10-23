"""kahramanlar.org.tr JSON API okuyucusu."""
import hashlib
import json
import logging
import re
from collections.abc import Iterator

from app.kaynaklar import HamKayit, KaynakHatasi
from app.kaynaklar.ayristir import isim_ayir, kategori_bul, soyadli_mi, tarih_coz
from app.models import Hassasiyet
from app.text import ad_duzenle, katla

logger = logging.getLogger(__name__)

API = "https://kahramanlar.org.tr/api.php"
LIMIT = 50
KAYNAK_KODU = "kahramanlar"
KAYNAK_ADI = "kahramanlar.org.tr"
KAYNAK_URL = "https://kahramanlar.org.tr/"

_PARANTEZ_YIL = re.compile(r"\((\d{4})\)")
_GENEL_MEMLEKET = {"turkiye", "msb"}


def _temiz(deger) -> str | None:
    """Boşlukları sadeleştirir; boş ve "-" değerler None olur."""
    metin = " ".join(str(deger or "").split())
    return None if metin in ("", "-") else metin


def kayit_cevir(k: dict) -> HamKayit | None:
    ham_ad = _temiz(k.get("ad"))
    if ham_ad is None:
        return None
    rutbe = _temiz(k.get("rutbe"))
    harp = _temiz(k.get("harp"))

    tarih, hassasiyet, yil = tarih_coz(_temiz(k.get("sehadet_tarihi")))
    if yil is None and harp and (eslesme := _PARANTEZ_YIL.search(harp)):
        yil, hassasiyet = int(eslesme[1]), Hassasiyet.yil

    soyadli = soyadli_mi(yil, harp)
    ad, soyad, gorev = isim_ayir(ham_ad, soyadli=soyadli)
    if not ad:
        return None
    lakap = _temiz(k.get("lakap"))
    memleket = _temiz(k.get("memleketi"))
    baba = _temiz(k.get("baba_adi"))
    dogum = _temiz(k.get("dogum_yili"))
    return HamKayit(
        kaynak_kodu=KAYNAK_KODU,
        dis_kimlik="kh:" + hashlib.sha1(json.dumps(k, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:20],
        ad=ad, soyad=soyad,
        lakap=ad_duzenle(lakap) if lakap and not soyadli else None,
        tarih=tarih, hassasiyet=hassasiyet, yil=yil,
        gorev=gorev or rutbe,
        kategori=kategori_bul(rutbe, harp),
        memleket=None if memleket is None or katla(memleket) in _GENEL_MEMLEKET else ad_duzenle(memleket),
        baba_adi=ad_duzenle(baba) if baba else None,
        dogum_yili=int(dogum) if dogum and dogum.isdigit() else None,
        donem=harp,
        kaynak_adi=KAYNAK_ADI, kaynak_url=KAYNAK_URL,
    )


def sayfalar(g, *, baslangic: str | None) -> Iterator[tuple[str, list[HamKayit]]]:
    if baslangic is None:
        sayfa = 1
    elif baslangic.isdigit():
        sayfa = int(baslangic) + 1
    else:
        raise KaynakHatasi(f"geçersiz kahramanlar imleci: {baslangic!r}")
    while True:
        yanit = g.json(KAYNAK_KODU, API, params={"page": sayfa, "limit": LIMIT})
        if not isinstance(yanit, dict) or not isinstance(yanit.get("data"), list):
            raise KaynakHatasi(f"kahramanlar sayfa {sayfa}: beklenmeyen yanıt biçimi")
        kayitlar = []
        for k in yanit["data"]:
            try:
                ham = kayit_cevir(k)
            except (AttributeError, TypeError, ValueError) as hata:
                logger.warning("kahramanlar sayfa %s: bozuk kayıt atlandı (%s)", sayfa, hata)
                continue
            if ham is not None:
                kayitlar.append(ham)
        yield str(sayfa), kayitlar
        if not yanit.get("has_more"):
            return
        sayfa += 1
