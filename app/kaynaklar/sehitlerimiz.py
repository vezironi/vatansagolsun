"""sehitlerimiz.org.tr okuyucusu: kayıt sayfaları, yıl listeleri, son eklenenler."""
import json
import logging
import re
from collections.abc import Iterator
from urllib.parse import urlsplit

from selectolax.parser import HTMLParser

from app.dates import bugun
from app.kaynaklar import HamKayit, KaynakHatasi, KaynakIzniYok
from app.kaynaklar.ayristir import isim_ayir, kategori_bul, soyadli_mi, tarih_coz
from app.models import Hassasiyet
from app.text import ad_duzenle

logger = logging.getLogger(__name__)

KOK = "https://sehitlerimiz.org.tr"
KAYNAK_KODU = "sehitlerimiz"
KAYNAK_ADI = "sehitlerimiz.org.tr — Türkiye Şehit Arşivi"
ILK_YIL = 2000  # öncesi kahramanlar.org.tr'den gelir (spec 4.3)

_KAYIT_ID = re.compile(r"-(\d+)/?$")
_LISTE_BAGLANTISI = 'ol.name-list li a[href^="/sehit/"]'


def _yol(url: str) -> str:
    return urlsplit(url).path


def kayit_id(url: str) -> int:
    eslesme = _KAYIT_ID.search(_yol(url))
    if eslesme is None:
        raise KaynakHatasi(f"kayıt kimliği bulunamadı: {url!r}")
    return int(eslesme[1])


def _kimlik_ya_da_none(url: str) -> int | None:
    try:
        return kayit_id(url)
    except KaynakHatasi:
        return None


def _temiz(deger) -> str | None:
    metin = " ".join(str(deger or "").split())
    return None if metin in ("", "-") else metin


def _kisi_json_ld(ag: HTMLParser) -> dict:
    for betik in ag.css('script[type="application/ld+json"]'):
        try:
            veri = json.loads(betik.text())
        except ValueError:
            continue
        for aday in veri if isinstance(veri, list) else [veri]:
            if isinstance(aday, dict) and aday.get("@type") == "Person":
                return aday
    return {}


def _ad_alani(sozluk, anahtar: str) -> str | None:
    deger = sozluk.get(anahtar)
    return _temiz(deger.get("name")) if isinstance(deger, dict) else None


def kayit_ayristir(html: str, url: str) -> HamKayit:
    ag = HTMLParser(html)
    kisi = _kisi_json_ld(ag)
    alanlar = {}
    for kutu in ag.css("dl.fields div"):
        dt, dd = kutu.css_first("dt"), kutu.css_first("dd")
        if dt is not None and dd is not None and (deger := _temiz(dd.text())):
            alanlar[_temiz(dt.text())] = deger

    h1 = ag.css_first("article.record h1") or ag.css_first("h1")
    ham_ad = _temiz(kisi.get("name")) or (_temiz(h1.text()) if h1 else None)
    if not ham_ad:
        raise KaynakHatasi(f"kayıt sayfasında ad bulunamadı: {url}")

    tarih, hassasiyet, yil = None, Hassasiyet.bilinmiyor, None
    for aday in (_temiz(kisi.get("deathDate")), alanlar.get("Şehadet Tarihi")):
        tarih, hassasiyet, yil = tarih_coz(aday)
        if hassasiyet != Hassasiyet.bilinmiyor:
            break

    gorev = _temiz(kisi.get("jobTitle")) or alanlar.get("Rütbe / Görev")
    kurum = _ad_alani(kisi, "affiliation") or alanlar.get("Kurum")
    donem = alanlar.get("Dönem / Cephe")
    baba = alanlar.get("Baba Adı")
    ad, soyad, isim_gorevi = isim_ayir(ham_ad, soyadli=soyadli_mi(yil, donem))
    yol = _yol(url)
    return HamKayit(
        kaynak_kodu=KAYNAK_KODU, dis_kimlik=str(kayit_id(url)), ad=ad, soyad=soyad,
        tarih=tarih, hassasiyet=hassasiyet, yil=yil, gorev=gorev or isim_gorevi,
        kategori=kategori_bul(gorev, kurum, donem), kurum=kurum,
        memleket=alanlar.get("Memleket") or alanlar.get("Doğum Yeri") or _ad_alani(kisi, "birthPlace"),
        baba_adi=ad_duzenle(baba) if baba else None, donem=donem,
        kaynak_adi=KAYNAK_ADI, kaynak_url=KOK + yol,
    )


def _liste_yollari(kok) -> list[str]:
    return [a.attributes["href"] for a in kok.css(_LISTE_BAGLANTISI)]


def yil_listesi_ayristir(html: str) -> tuple[list[str], bool]:
    ag = HTMLParser(html)
    return _liste_yollari(ag), ag.css_first("link[rel=next], a[rel=next]") is not None


def son_eklenenler_ayristir(html: str) -> list[str]:
    bolum = HTMLParser(html).css_first("#son-eklenenler")
    if bolum is None:
        return []
    # Gerçek sayfada id başlığın (h2) üzerinde, liste kardeşi: liste yoksa kapsayan bölüme bak.
    if bolum.css_first("ol.name-list") is None and bolum.parent is not None:
        bolum = bolum.parent
    return _liste_yollari(bolum)


def _kayit_getir(g, yol: str) -> HamKayit | None:
    """Tek kayıt sayfası; izin hatası dışındaki sorunlarda kaydı günlüğe yazıp atlar."""
    try:
        return kayit_ayristir(g.metin(KAYNAK_KODU, KOK + yol), yol)
    except KaynakIzniYok:
        raise
    except KaynakHatasi as hata:
        logger.warning("sehitlerimiz kaydı atlandı %s: %s", yol, hata)
        return None


def _imleci_coz(baslangic: str | None) -> tuple[int, int]:
    if baslangic is None:
        return 0, 0
    yil, _, sayfa = baslangic.partition(":")
    if not (yil.isdigit() and sayfa.isdigit()):
        raise KaynakHatasi(f"geçersiz sehitlerimiz imleci: {baslangic!r}")
    return int(yil), int(sayfa)


def sayfalar(g, *, baslangic: str | None, yillar: range | None = None) -> Iterator[tuple[str, list[HamKayit]]]:
    """Yıl yıl, sayfa sayfa; imleç "{yyyy}:{N}" son tamamlanan sayfadır."""
    son_yil, son_sayfa = _imleci_coz(baslangic)
    for yil in yillar if yillar is not None else range(ILK_YIL, bugun().year + 1):
        if yil < son_yil:
            continue
        sayfa = son_sayfa + 1 if yil == son_yil else 1
        while True:
            try:
                html = g.metin(KAYNAK_KODU, f"{KOK}/yil/{yil}", params={"sayfa": sayfa})
            except KaynakHatasi as hata:
                if hata.durum_kodu == 404:  # yıl (ya da yılın son sayfasından sonrası) yok
                    break
                raise
            yollar, devam = yil_listesi_ayristir(html)
            if not yollar:
                break
            kayitlar = [h for yol in yollar if (h := _kayit_getir(g, yol)) is not None]
            yield f"{yil}:{sayfa}", kayitlar
            if not devam:
                break
            sayfa += 1


def yeni_kayitlar(g, *, son_id: int) -> tuple[list[HamKayit], int]:
    """/arsiv'deki son eklenenlerden son_id'den büyük olanları çeker.

    Dönen kimlik, atlanan (alınamayan) bir kayıttan öteye geçmez; böylece sonraki
    kontrol onu yeniden dener.
    """
    yeniler = sorted(
        (kimlik, y) for y in son_eklenenler_ayristir(g.metin(KAYNAK_KODU, KOK + "/arsiv"))
        if (kimlik := _kimlik_ya_da_none(y)) is not None and kimlik > son_id
    )
    if not yeniler:
        return [], son_id
    kayitlar, en_buyuk, kesildi = [], son_id, False
    for kimlik, yol in yeniler:
        ham = _kayit_getir(g, yol)
        if ham is None:
            kesildi = True
        else:
            kayitlar.append(ham)
            if not kesildi:
                en_buyuk = kimlik
    return kayitlar, en_buyuk


def en_buyuk_id(g) -> int:
    """/arsiv'deki son eklenenler arasındaki en büyük kayıt kimliği (hiç yoksa 0)."""
    kimlikler = [k for y in son_eklenenler_ayristir(g.metin(KAYNAK_KODU, KOK + "/arsiv"))
                 if (k := _kimlik_ya_da_none(y)) is not None]
    return max(kimlikler, default=0)
