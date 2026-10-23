"""Sahil Güvenlik Komutanlığı şehitleri okuyucusu."""
from collections.abc import Iterator
from urllib.parse import urlsplit

from selectolax.parser import HTMLParser

from app.kaynaklar import HamKayit
from app.kaynaklar.ayristir import isim_ayir, tarih_coz
from app.models import Kategori
from app.text import slug

KOK = "https://www.sg.gov.tr"
KAYNAK_KODU = "sg"
KAYNAK_ADI = "Sahil Güvenlik Komutanlığı"


def ayristir(html: str) -> list[HamKayit]:
    kayitlar = []
    for kart in HTMLParser(html).css("div.manager-vertical-card"):
        ad_dugumu = kart.css_first(".manager-name")
        ham = " ".join(ad_dugumu.text().split()) if ad_dugumu else ""
        ad, soyad, gorev = isim_ayir(ham, soyadli=True) if ham else ("", None, None)
        if not ad:
            continue
        tarih_dugumu = kart.css_first(".manager-sm-card-body p")
        tarih, hassasiyet, yil = tarih_coz(tarih_dugumu.text().strip() if tarih_dugumu else None)
        baglanti = kart.css_first("a[href]")
        yol = urlsplit(baglanti.attributes.get("href") or "").path if baglanti else ""
        kayitlar.append(HamKayit(
            kaynak_kodu=KAYNAK_KODU, dis_kimlik=yol or "sg:" + slug(ham), ad=ad, soyad=soyad,
            gorev=gorev, tarih=tarih, hassasiyet=hassasiyet, yil=yil, kategori=Kategori.asker,
            kurum=KAYNAK_ADI, kaynak_adi=KAYNAK_ADI, kaynak_url=KOK + "/sehitlerimiz",
        ))
    return kayitlar


def sayfalar(g, *, baslangic: str | None) -> Iterator[tuple[str, list[HamKayit]]]:
    if baslangic == "1":
        return
    yield "1", ayristir(g.metin(KAYNAK_KODU, KOK + "/sehitlerimiz"))
