"""Haber siteleri: RSS akışları ve makale sayfaları (Hürriyet, Sabah, AA, TRT)."""
import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from selectolax.parser import HTMLParser

from app.kaynaklar import KaynakHatasi
from app.kaynaklar.ayristir import metin_temizle
from app.kaynaklar.getirici import Getirici
from app.text import katla

logger = logging.getLogger(__name__)

TURKIYE = timezone(timedelta(hours=3))  # Türkiye kalıcı olarak UTC+3
GOVDE_SINIRI = 20_000
_KIMLIK = re.compile(r"-(\d{6,})(?:\.html)?/?$")
_SEHIT = re.compile(r"\b(?:sehi[td]|sehadet)")
_DTD = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)
_DEVAMI = re.compile(r"\s*Devamı için tıklayınız\s*$")
# JSON-LD `articleBody` yalnızca bu kaynaklarda güvenilir (Hürriyet'te çöp metin döner).
_JSONLD_GOVDE_GUVENILIR = {"sabah"}


@dataclass
class HaberOgesi:
    kaynak_kodu: str
    kimlik: str
    url: str
    baslik: str
    ozet: str
    yayin: datetime  # saat dilimli


@dataclass
class HaberKaynagi:
    kod: str
    ad: str
    rss: list[str]
    govde_secici: str


@dataclass
class Makale:
    baslik: str
    govde: str
    yayin: datetime | None


HABER_KAYNAKLARI: dict[str, HaberKaynagi] = {
    "hurriyet": HaberKaynagi(
        "hurriyet", "Hürriyet", ["https://www.hurriyet.com.tr/rss/gundem"], ".news-content"
    ),
    "sabah": HaberKaynagi(
        "sabah", "Sabah",
        ["https://www.sabah.com.tr/rss/sondakika.xml", "https://www.sabah.com.tr/rss/gundem.xml"],
        "div.newsBox",
    ),
    # AA ve TRT makale gövde seçicileri örnek sayfa alınmadan yazıldı (araştırmada yalnızca RSS
    # örnekleri var): DOĞRULANMADI. Bu kaynaklar varsayılan olarak kapalıdır; açmadan önce
    # gerçek bir makale sayfasıyla denenmeli.
    "aa": HaberKaynagi(
        "aa", "Anadolu Ajansı", ["https://www.aa.com.tr/tr/rss/default?cat=guncel"], "div.detay-icerik"
    ),
    "trt": HaberKaynagi(
        "trt", "TRT Haber", ["https://www.trthaber.com/sondakika.rss"], "div.news-content"
    ),
}


def _html_metni(parca: str | None) -> str:
    parca = parca or ""
    if "<" not in parca and "&" not in parca:
        return metin_temizle(parca)
    return metin_temizle(HTMLParser(f"<div>{parca}</div>").text())


def _yayin_coz(deger: str) -> datetime:
    yayin = parsedate_to_datetime(deger.strip())  # "…Z" (Hürriyet) UTC sayılır
    return yayin if yayin.tzinfo else yayin.replace(tzinfo=timezone.utc)


def _kimlik(url: str, guid: str) -> str:
    eslesme = _KIMLIK.search(url)
    return eslesme.group(1) if eslesme else (guid or url)


def rss_ayristir(xml: str, kaynak: HaberKaynagi) -> list[HaberOgesi]:
    """RSS metnini öğelere çevirir; bozuk öğeler atlanır.

    Güvenlik: DOCTYPE/ENTITY içeren belge reddedilir. `xml.etree.ElementTree` dış varlıkları
    zaten getirmez, ama iç varlık genişletmesi (billion laughs) mümkün olduğundan DTD'ye hiç
    izin verilmez; meşru RSS akışlarında DTD bulunmaz.
    """
    xml = xml.lstrip("﻿ \t\r\n")
    if _DTD.search(xml):
        raise KaynakHatasi(f"{kaynak.kod}: RSS DOCTYPE/ENTITY içeriyor; reddedildi")
    try:
        kok = ET.fromstring(xml)
    except ET.ParseError as hata:
        raise KaynakHatasi(f"{kaynak.kod}: RSS ayrıştırılamadı: {hata}") from hata
    ogeler = []
    for oge in kok.iter("item"):
        try:
            url = (oge.findtext("link") or "").strip()
            baslik = metin_temizle(oge.findtext("title"))
            tarih = (oge.findtext("pubDate") or "").strip()
            if not (url and baslik and tarih):
                raise ValueError("link, başlık ya da pubDate eksik")
            ozet = _html_metni(oge.findtext("description"))
            ozet = _DEVAMI.sub("", ozet)
            guid = (oge.findtext("guid") or "").strip()
            ogeler.append(HaberOgesi(
                kaynak_kodu=kaynak.kod, kimlik=_kimlik(url, guid), url=url,
                baslik=baslik, ozet=ozet, yayin=_yayin_coz(tarih),
            ))
        except (ValueError, TypeError) as hata:
            logger.warning("%s: bozuk RSS öğesi atlandı: %s", kaynak.kod, hata)
    return ogeler


def sehit_gecer_mi(*metinler: str) -> bool:
    """Metinlerde şehit/şehid/şehadet geçiyor mu? ("şehir" gibi sözcükler eşleşmez.)"""
    return bool(_SEHIT.search(katla(" ".join(m for m in metinler if m))))


def _yayin_iso(deger: object) -> datetime | None:
    if not isinstance(deger, str):
        return None
    try:
        yayin = datetime.fromisoformat(deger.strip())
    except ValueError:
        return None
    return yayin if yayin.tzinfo else yayin.replace(tzinfo=TURKIYE)


def _haber_makalesi(veri: object) -> dict | None:
    """JSON-LD ağacında NewsArticle düğümünü bulur (düz nesne, liste ya da @graph)."""
    if isinstance(veri, list):
        for parca in veri:
            bulunan = _haber_makalesi(parca)
            if bulunan:
                return bulunan
    elif isinstance(veri, dict):
        tur = veri.get("@type")
        if tur == "NewsArticle" or (isinstance(tur, list) and "NewsArticle" in tur):
            return veri
        return _haber_makalesi(veri.get("@graph"))
    return None


def _json_ld(doc: HTMLParser) -> dict:
    for dugum in doc.css('script[type="application/ld+json"]'):
        try:
            bulunan = _haber_makalesi(json.loads(dugum.text(), strict=False))
        except ValueError:
            continue
        if bulunan:
            return bulunan
    return {}


def _govde_secicisinden(doc: HTMLParser, secici: str) -> str:
    parcalar = []
    for kap in doc.css(secici):
        for dugum in kap.css("h2, p"):
            metin = metin_temizle(dugum.text())
            if metin:
                parcalar.append(metin)
    return "\n\n".join(parcalar)


def makale_ayristir(html: str, kaynak: HaberKaynagi) -> Makale:
    doc = HTMLParser(html)
    ld = _json_ld(doc)
    govde = ""
    if kaynak.kod in _JSONLD_GOVDE_GUVENILIR:
        govde = metin_temizle(ld.get("articleBody"))
    if not govde:
        govde = _govde_secicisinden(doc, kaynak.govde_secici)
    if not govde:
        raise KaynakHatasi(f"{kaynak.kod}: makale gövdesi bulunamadı")
    baslik = metin_temizle(ld.get("headline"))
    if not baslik:
        h1 = doc.css_first("h1")
        baslik = metin_temizle(h1.text()) if h1 else ""
    return Makale(baslik=baslik, govde=govde[:GOVDE_SINIRI], yayin=_yayin_iso(ld.get("datePublished")))


def ogeleri_getir(g: Getirici, kaynak: HaberKaynagi) -> list[HaberOgesi]:
    """Kaynağın tüm RSS akışlarını okur; kimliğe göre tekilleştirir, yeniden eskiye sıralar.

    Bir akış okunamazsa hata yukarı çıkar: eksik veriyle imleç ilerletilmemeli.
    """
    tekil: dict[str, HaberOgesi] = {}
    for url in kaynak.rss:
        for oge in rss_ayristir(g.metin(kaynak.kod, url), kaynak):
            tekil.setdefault(oge.kimlik, oge)
    return sorted(tekil.values(), key=lambda o: o.yayin, reverse=True)
