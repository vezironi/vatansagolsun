"""Emniyet Genel Müdürlüğü şehit listeleri okuyucusu."""
import re
from collections.abc import Iterator
from urllib.parse import urlsplit

from selectolax.parser import HTMLParser

from app.kaynaklar import HamKayit, KaynakHatasi
from app.kaynaklar.ayristir import isim_ayir, tarih_coz
from app.models import Kategori
from app.text import slug

KOK = "https://www.egm.gov.tr"
AJAX = KOK + "/ISAYWebPart/ContentList/DahaFazlaYukle"
BOLUMLER = {
    "sehitlerimiz": ("/sehitlerimiz", "YNcLZaW4rMBeGR5FZn5E6A=="),
    "ozelharekat": ("/ozelharekat/sehitlerimiz", "MNwu2a6REuJpCzWh5FhgSg=="),
}
ISTIHBARAT = "/istihbarat/istihbarat-sehitlerimiz"

KAYNAK_KODU = "egm"
KAYNAK_ADI = "Emniyet Genel Müdürlüğü"
_KURUMLAR = {
    "sehitlerimiz": KAYNAK_ADI,
    "ozelharekat": KAYNAK_ADI + " — Özel Harekât",
}
_ISTIHBARAT_KURUMU = KAYNAK_ADI + " — İstihbarat"
_DOSYA_ADI = re.compile(r"\.(png|jpe?g|gif|webp|bmp)$", re.IGNORECASE)


def kartlari_ayristir(html: str, *, bolum: str) -> list[HamKayit]:
    kayitlar = []
    for kart in HTMLParser(html).css("a.news-card-horizontal[href]"):
        baslik = kart.css_first(".card-title")
        yol = urlsplit(kart.attributes.get("href") or "").path
        if baslik is None or not yol:
            continue
        ham = " ".join(baslik.text().split())
        ad, soyad, gorev = isim_ayir(ham, soyadli=True)
        if not ad:
            continue
        tarih_dugumu = kart.css_first(".cardDate")
        tarih, hassasiyet, yil = tarih_coz(tarih_dugumu.text().strip() if tarih_dugumu else None)
        kayitlar.append(HamKayit(
            kaynak_kodu=KAYNAK_KODU, dis_kimlik=yol, ad=ad, soyad=soyad, gorev=gorev,
            tarih=tarih, hassasiyet=hassasiyet, yil=yil, kategori=Kategori.polis,
            kurum=_KURUMLAR[bolum], kaynak_adi=KAYNAK_ADI, kaynak_url=KOK + yol,
        ))
    return kayitlar


def _istihbarat_adi(img) -> str:
    alt = " ".join((img.attributes.get("alt") or "").split())
    if alt and not _DOSYA_ADI.search(alt):
        return alt
    # alt dosya adı ise (ör. "omer_aktas.png"): görselin hücresindeki ilk metin satırı ad
    hucre = img.parent
    while hucre is not None and hucre.tag not in ("td", "body"):
        hucre = hucre.parent
    if hucre is None:
        return ""
    for satir in hucre.text(separator="\n").split("\n"):
        satir = " ".join(satir.replace("\xa0", " ").split())
        if satir:
            return satir
    return ""


def istihbarat_ayristir(html: str) -> list[HamKayit]:
    kayitlar = []
    for img in HTMLParser(html).css("img[alt]"):
        alt = (img.attributes.get("alt") or "").strip()
        src = img.attributes.get("src") or ""
        # üst bilgi görselleri ve logolar değil, yalnızca "Sehitlerimiz" varlık klasöründeki fotoğraflar
        if not alt or "logo" in alt.lower() or "/sehitlerimiz/" not in src.lower():
            continue
        ham = _istihbarat_adi(img)
        ad, soyad, gorev = isim_ayir(ham, soyadli=True)
        if not ad:
            continue
        kayitlar.append(HamKayit(
            kaynak_kodu=KAYNAK_KODU, dis_kimlik="istihbarat:" + slug(ham), ad=ad, soyad=soyad,
            gorev=gorev, kategori=Kategori.polis, kurum=_ISTIHBARAT_KURUMU,
            kaynak_adi=KAYNAK_ADI, kaynak_url=KOK + ISTIHBARAT,
        ))
    return kayitlar


def _imleci_coz(baslangic: str | None) -> tuple[int, int]:
    """İmleci (bölüm sırası, sayfa) çiftine çevirir; sıra: bölümler, ardından istihbarat."""
    sira = [*BOLUMLER, "istihbarat"]
    if baslangic is None:
        return 0, 0
    bolum, _, sayfa = baslangic.partition(":")
    if bolum not in sira or not sayfa.isdigit():
        raise KaynakHatasi(f"geçersiz EGM imleci: {baslangic!r}")
    return sira.index(bolum), int(sayfa)


def sayfalar(g, *, baslangic: str | None) -> Iterator[tuple[str, list[HamKayit]]]:
    bolum_sirasi, son_sayfa = _imleci_coz(baslangic)
    for sira, (bolum, (yol, tur_kimligi)) in enumerate(BOLUMLER.items()):
        if sira < bolum_sirasi:
            continue
        sayfa = son_sayfa + 1 if sira == bolum_sirasi else 1
        liste_url = KOK + yol
        if sayfa == 1:
            yield f"{bolum}:1", kartlari_ayristir(g.metin(KAYNAK_KODU, liste_url), bolum=bolum)
            sayfa = 2
        while True:
            govde = {"page": sayfa, "ContentTypeId": tur_kimligi, "OrderByAsc": "true", "ContentCount": "6"}
            yanit = g.post_json(KAYNAK_KODU, AJAX, govde, referer=liste_url)
            if not yanit.strip():
                break
            yield f"{bolum}:{sayfa}", kartlari_ayristir(yanit, bolum=bolum)
            sayfa += 1
    if (bolum_sirasi, son_sayfa) < (len(BOLUMLER), 1):
        yield "istihbarat:1", istihbarat_ayristir(g.metin(KAYNAK_KODU, KOK + ISTIHBARAT))
