from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.kaynaklar import KaynakHatasi
from app.kaynaklar.haber import (
    HABER_KAYNAKLARI, HaberOgesi, makale_ayristir, ogeleri_getir, rss_ayristir, sehit_gecer_mi,
)

F = Path(__file__).parent / "fixtures" / "haber"
UTC = timezone.utc
TR = timezone(timedelta(hours=3))


def oku(ad: str) -> str:
    return (F / ad).read_text(encoding="utf-8")


def ayristir(dosya: str, kod: str) -> list[HaberOgesi]:
    return rss_ayristir(oku(dosya), HABER_KAYNAKLARI[kod])


def test_hurriyet_rss_z_soneki_utc():
    ogeler = ayristir("hurriyet_gundem.xml", "hurriyet")
    assert len(ogeler) == 4
    ilk = ogeler[0]
    assert ilk.yayin == datetime(2026, 10, 23, 7, 2, tzinfo=UTC) and ilk.yayin.utcoffset() == timedelta(0)
    assert ilk.kimlik == "43351885" and ilk.kaynak_kodu == "hurriyet"
    assert ilk.url.endswith("-43351885") and ilk.baslik.startswith("İstanbul'da bu yollar")
    assert ilk.ozet.startswith("İstanbul Valiliği")


def test_hurriyet_gercek_sehit_ogesi():
    sehit = ayristir("hurriyet_gundem.xml", "hurriyet")[3]  # gerçek örnekten alınmış öğe
    assert sehit.kimlik == "43340748" and sehit_gecer_mi(sehit.baslik, sehit.ozet)


def test_sabah_rss_arti_0300_ve_kimlik_url():
    ogeler = ayristir("sabah_sondakika.xml", "sabah")
    assert len(ogeler) == 4
    assert ogeler[0].yayin == datetime(2026, 10, 23, 10, 10, tzinfo=TR) and ogeler[0].yayin.utcoffset() == timedelta(hours=3)
    assert ogeler[0].kimlik == ogeler[0].url  # URL'de sayısal kimlik yok: guid/URL
    assert all(o.ozet and "<" not in o.ozet for o in ayristir("sabah_gundem.xml", "sabah"))


def test_sabah_gundem_ozeti_html_ve_devami_baglantisindan_arinir():
    ilk = ayristir("sabah_gundem.xml", "sabah")[0]
    assert "<img" not in ilk.ozet and "Devamı için tıklayınız" not in ilk.ozet
    assert ilk.ozet.startswith("İstanbul’da merkezli 3,5 milyar")


def test_sabah_sentetik_sehit_ogesi():
    # Gerçek örnekte "şehit" geçen haber yoktu: fixture'daki son öğe SENTETİKTİR.
    sentetik = ayristir("sabah_sondakika.xml", "sabah")[3]
    assert sentetik.baslik.startswith("[SENTETİK]") and sehit_gecer_mi(sentetik.baslik)


def test_aa_rss_kimlik_guid_ve_sentetik():
    ogeler = ayristir("aa_guncel.xml", "aa")
    assert len(ogeler) == 4
    assert ogeler[0].kimlik == "4098028"  # URL "/4098028" ile biter (tire yok): guid kullanılır
    assert ogeler[0].yayin == datetime(2026, 10, 23, 10, 8, 21, tzinfo=TR)
    assert ogeler[3].baslik.startswith("[SENTETİK]")  # sentetik öğe (gerçek örnekte şehit yoktu)


def test_trt_rss_aciklama_yorumu_ve_cdata():
    ogeler = ayristir("trt_sondakika.xml", "trt")
    assert len(ogeler) == 3
    assert ogeler[0].kimlik == "960972" and ogeler[0].yayin == datetime(2026, 10, 23, 9, 48, tzinfo=TR)
    assert ogeler[0].ozet.startswith("Hafta sonunun ilk günü") and "<!--" not in ogeler[0].ozet
    assert sehit_gecer_mi(ogeler[2].baslik)  # gerçek örnekteki şehit öğesi


def test_bozuk_oge_atlanir_digerleri_kalir(caplog):
    xml = """<rss><channel>
      <item><title>Bozuk tarih</title><link>https://x.test/a-1234567</link><pubDate>dün</pubDate></item>
      <item><title>Linksiz</title><pubDate>Fri, 23 Oct 2026 07:02:00 +0300</pubDate></item>
      <item><title>İyi</title><link>https://x.test/b-7654321</link><pubDate>Fri, 23 Oct 2026 07:02:00 +0300</pubDate></item>
    </channel></rss>"""
    with caplog.at_level("WARNING"):
        ogeler = rss_ayristir(xml, HABER_KAYNAKLARI["hurriyet"])
    assert [o.kimlik for o in ogeler] == ["7654321"] and len(caplog.records) == 2


def test_rss_dtd_ve_varlik_reddedilir():
    saldiri = """<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>
    <rss><channel><item><title>&b;</title><link>https://x.test/a-1234567</link>
    <pubDate>Fri, 23 Oct 2026 07:02:00 +0300</pubDate></item></channel></rss>"""
    with pytest.raises(KaynakHatasi):
        rss_ayristir(saldiri, HABER_KAYNAKLARI["hurriyet"])
    with pytest.raises(KaynakHatasi):
        rss_ayristir("<rss><channel>", HABER_KAYNAKLARI["hurriyet"])


@pytest.mark.parametrize("metin,beklenen", [
    ("Pençe-Kilit bölgesinde 2 askerimiz şehit oldu", True),
    ("Şehidimizi uğurladık", True),
    ("Şehadet haberi", True),
    ("ŞEHİT polis memuru", True),
    ("SEHIT oldu", True),
    ("İstanbul şehir hatları", False),
    ("Şehirler arası yol", False),
])
def test_sehit_gecer_mi(metin, beklenen):
    assert sehit_gecer_mi(metin) is beklenen


def test_sehit_gecer_mi_birden_cok_metin():
    assert sehit_gecer_mi("Başlık", "", "Özette şehit geçiyor")
    assert not sehit_gecer_mi("Başlık", "şehir", "")


def test_hurriyet_makale():
    m = makale_ayristir(oku("hurriyet_makale.html"), HABER_KAYNAKLARI["hurriyet"])
    assert m.yayin == datetime(2026, 10, 20, 21, 47, 48, tzinfo=TR)
    assert m.baslik == "Polis memurunu şehit eden iki kardeşin cezası belli oldu"
    assert m.govde.startswith("Olay, 20 Kasım 2024'te")  # JSON-LD articleBody'deki çöp metin değil
    assert "Google’da Takip Edin" not in m.govde and m.baslik not in m.govde
    assert len(m.govde) <= 20_000


def test_sabah_makale_jsonld_govdesi():
    m = makale_ayristir(oku("sabah_makale.html"), HABER_KAYNAKLARI["sabah"])
    assert m.yayin == datetime(2026, 10, 7, 1, 13, 16, tzinfo=TR)
    assert m.baslik == "Pursaklar’da uygulama yapan polislere silahlı saldırı: 1 polis şehit"
    assert m.govde.startswith("Pursaklar ilçesinde") and m.baslik not in m.govde
    assert "Uygulamamızı İndirin" not in m.govde


def test_sabah_makale_jsonld_yoksa_secici_kullanilir():
    html = '<html><body><div class="newsBox"><p>Birinci.</p><p> </p><p>İkinci.</p></div></body></html>'
    m = makale_ayristir(html, HABER_KAYNAKLARI["sabah"])
    assert m.govde == "Birinci.\n\nİkinci." and m.yayin is None and m.baslik == ""


def test_makale_govdesi_20000_ile_sinirlanir():
    html = '<div class="news-content"><p>' + "a" * 30_000 + "</p></div>"
    assert len(makale_ayristir(html, HABER_KAYNAKLARI["hurriyet"]).govde) == 20_000


def test_bos_govde_kaynak_hatasi():
    with pytest.raises(KaynakHatasi):
        makale_ayristir(oku("hurriyet_404.html"), HABER_KAYNAKLARI["hurriyet"])


def test_jsonld_naive_tarih_turkiye_saati_sayilir():
    html = ('<script type="application/ld+json">{"@type":"NewsArticle","headline":"B",'
            '"datePublished":"2026-10-07T01:13:16"}</script><div class="news-content"><p>x</p></div>')
    assert makale_ayristir(html, HABER_KAYNAKLARI["hurriyet"]).yayin == datetime(2026, 10, 7, 1, 13, 16, tzinfo=TR)


class SahteGetirici:
    def __init__(self, akislar: dict[str, str]):
        self.akislar, self.istekler = akislar, []

    def metin(self, kod, url, *, params=None):
        self.istekler.append((kod, url))
        return self.akislar[url]


def test_ogeleri_getir_iki_akista_ayni_haberi_bir_kez_ve_yeniden_eskiye():
    kaynak = HABER_KAYNAKLARI["sabah"]
    g = SahteGetirici({kaynak.rss[0]: oku("sabah_sondakika.xml"), kaynak.rss[1]: oku("sabah_gundem.xml")})
    ogeler = ogeleri_getir(g, kaynak)
    assert [k for k, _ in g.istekler] == ["sabah", "sabah"]
    kimlikler = [o.kimlik for o in ogeler]
    assert len(kimlikler) == len(set(kimlikler)) == 5  # 4 + 3 öğeden 2 ortak
    assert [o.yayin for o in ogeler] == sorted((o.yayin for o in ogeler), reverse=True)
    assert ogeler[3].baslik.startswith("[SENTETİK]") and ogeler[-1].baslik == "Yeni dünya için tarihi adım"
