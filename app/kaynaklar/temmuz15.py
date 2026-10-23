"""15temmuzsehitleri.com okuyucusu: 15 Temmuz 2016 darbe girişimi şehitleri.

Liste sayfası tüm şehitleri (fotoğraflarıyla) tek seferde verir; her şehidin ayrıntısı
(memleket, kurum, şehadet yeri, biyografi) sitenin kendi modalinin kullandığı HeroInfo
JSON'undan alınır.
"""
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from selectolax.parser import HTMLParser

from app.kaynaklar import HamKayit, KaynakHatasi
from app.kaynaklar.ayristir import (
    alan_temizle, cumleye_kirp, gorsel_adresi, isim_ayir, kategori_bul, metin_temizle, tarih_coz,
)
from app.models import Hassasiyet, Kategori
from app.text import katla

logger = logging.getLogger(__name__)

KOK = "https://15temmuzsehitleri.com"
LISTE_URL = KOK + "/tr/sehitlerimiz-111"
BILGI_URL = KOK + "/TR/f/HeroInfo"
KAYNAK_KODU = "temmuz15"
KAYNAK_ADI = "15 Temmuz Şehitleri (15temmuzsehitleri.com)"
PARCA = 25  # imleç bu kadar kayıtta bir kaydedilir
DARBE_GECESI = date(2016, 7, 15)
_ASKERI = ("asker", "subay", "cavus", "komutan", "harbiye", "kuvvet")
_YIL = re.compile(r"\d{4}")


@dataclass
class ListeOgesi:
    id: int
    ad: str
    dogum: str | None
    sehadet: str | None
    meslek: str | None
    fotograf: str | None = None


def liste_ayristir(html: str) -> list[ListeOgesi]:
    ogeler = []
    for a in HTMLParser(html).css(".hero a.hero-item[data-id]"):
        kimlik = a.attributes.get("data-id") or ""
        baslik = a.css_first("h4")
        if not kimlik.isdigit() or baslik is None:
            continue
        p = [metin_temizle(d.text()) for d in a.css(".hero-item-left p")]
        dogum, _, sehadet = (p[0].strip("()") if p else "").partition(" - ")
        ogeler.append(ListeOgesi(
            id=int(kimlik), ad=metin_temizle(baslik.text()), dogum=alan_temizle(dogum),
            sehadet=alan_temizle(sehadet), meslek=alan_temizle(p[1]) if len(p) > 1 else None,
            fotograf=gorsel_adresi(a.css_first(".hero-item-right img"), KOK),
        ))
    return sorted(ogeler, key=lambda o: o.id)


def _h6(parca: str | None) -> str | None:
    """"<h5>MESLEĞİ </h5><h6> Polis </h6>" -> "Polis"."""
    dugum = HTMLParser(parca).css_first("h6") if parca else None
    return alan_temizle(dugum.text()) if dugum else None


def _kategori(*ipuclari: str | None) -> Kategori:
    k = kategori_bul(*ipuclari)
    if k != Kategori.asker:
        return k
    metin = katla(" ".join(i for i in ipuclari if i))
    return Kategori.asker if any(a in metin for a in _ASKERI) else Kategori.diger


def kayit_olustur(oge: ListeOgesi, bilgi: dict) -> HamKayit:
    ad, soyad, _ = isim_ayir(alan_temizle(bilgi.get("NameSurname")) or oge.ad, soyadli=True)
    gorev = _h6(bilgi.get("Mevki")) or _h6(bilgi.get("Job")) or oge.meslek
    kurum = _h6(bilgi.get("CalistigiKurum"))
    tarih, hassasiyet, yil = tarih_coz(alan_temizle(bilgi.get("SehitDate")) or oge.sehadet)
    if (tarih and tarih < DARBE_GECESI) or (yil and yil < DARBE_GECESI.year):
        logger.warning("temmuz15/%s: darbe gecesinden önceki tarih (%s) yok sayıldı", oge.id, tarih or yil)
        tarih, hassasiyet, yil = None, Hassasiyet.yil, DARBE_GECESI.year
    dogum = alan_temizle(bilgi.get("DogumDate")) or oge.dogum or ""
    icerik = bilgi.get("Content")
    biyografi = alan_temizle(HTMLParser(icerik).text(separator=" ")) if icerik else None
    return HamKayit(
        kaynak_kodu=KAYNAK_KODU, dis_kimlik=f"{KAYNAK_KODU}:{oge.id}", ad=ad, soyad=soyad,
        tarih=tarih, hassasiyet=hassasiyet, yil=yil, gorev=gorev,
        kategori=_kategori(_h6(bilgi.get("Mevki")), _h6(bilgi.get("Job")) or oge.meslek, kurum),
        kurum=kurum, memleket=_h6(bilgi.get("Memleketi")),
        dogum_yili=int(dogum) if _YIL.fullmatch(dogum) else None,
        sehadet_yeri=_h6(bilgi.get("SehadetYeri")), sehadet_olayi=cumleye_kirp(biyografi),
        fotograf_url=oge.fotograf, kaynak_adi=KAYNAK_ADI, kaynak_url=LISTE_URL, metin=biyografi,
    )


def _bilgi(g, kimlik: int) -> dict:
    try:
        veri = g.json(KAYNAK_KODU, BILGI_URL, params={"Id": kimlik})
    except KaynakHatasi as hata:
        if hata.durum_kodu is None:  # ağ hatası: aktarım dursun, kaldığı yerden devam edilsin
            raise
        logger.warning("temmuz15/%s ayrıntısı alınamadı (%s); liste verisi kullanılıyor", kimlik, hata)
        return {}
    return veri if isinstance(veri, dict) else {}


def sayfalar(g, *, baslangic: str | None) -> Iterator[tuple[str, list[HamKayit]]]:
    """İmleç, işlenen son şehidin site kimliğidir; devamda yalnızca daha büyükleri alınır."""
    son = int(baslangic) if baslangic and baslangic.isdigit() else 0
    ogeler = [o for o in liste_ayristir(g.metin(KAYNAK_KODU, LISTE_URL)) if o.id > son]
    for i in range(0, len(ogeler), PARCA):
        parca = ogeler[i:i + PARCA]
        yield str(parca[-1].id), [kayit_olustur(o, _bilgi(g, o.id)) for o in parca]
