from datetime import date
from pathlib import Path

import pytest

from app.kaynaklar import KaynakHatasi, egm
from app.models import Kategori

F = Path(__file__).parent / "fixtures" / "kaynaklar"


def oku(ad):
    return (F / ad).read_text(encoding="utf-8")


def test_kartlar():
    k = egm.kartlari_ayristir(oku("egm_liste.html"), bolum="sehitlerimiz")
    assert len(k) == 3
    ilk = k[0]
    assert (ilk.ad, ilk.soyad, ilk.gorev, ilk.tarih) == ("Ahmet", "TÜRKOĞLU", "Polis Memuru", date(2026, 10, 8))
    assert ilk.dis_kimlik == "/sehit-polis-memuru-ahmet-turkoglu" and ilk.kategori == Kategori.polis
    assert ilk.kaynak_url == "https://www.egm.gov.tr/sehit-polis-memuru-ahmet-turkoglu"
    assert ilk.kurum == "Emniyet Genel Müdürlüğü" and ilk.kaynak_adi == "Emniyet Genel Müdürlüğü"
    assert ilk.kaynak_kodu == "egm"


def test_kartlar_ozel_harekat_kurumu():
    k = egm.kartlari_ayristir(oku("egm_ajax_dolu.html"), bolum="ozelharekat")
    assert len(k) == 2
    assert k[0].dis_kimlik == "/sehit-polis-memuru-emrah-koc"
    assert all(x.kurum == "Emniyet Genel Müdürlüğü — Özel Harekât" for x in k)
    assert all(x.kategori == Kategori.polis for x in k)


def test_bozuk_kart_atlanir():
    html = (
        '<a class="news-card-horizontal" href="/x"><span class="cardDate">01.01.2020</span></a>'
        '<a class="news-card-horizontal" href="/y"><h5 class="card-title">  </h5></a>'
        '<a class="news-card-horizontal"><h5 class="card-title">Şehit Polis Memuru Ali VELİ</h5></a>'
        '<a class="news-card-horizontal" href="/z"><h5 class="card-title">Şehit Polis Memuru Ali VELİ</h5>'
        '<span class="cardDate">saçma</span></a>'
    )
    k = egm.kartlari_ayristir(html, bolum="sehitlerimiz")
    assert [x.dis_kimlik for x in k] == ["/z"] and k[0].tarih is None


def test_istihbarat_tarihsiz():
    k = egm.istihbarat_ayristir(oku("egm_istihbarat.html"))
    assert len(k) == 4 and all(x.tarih is None for x in k)
    assert any(x.soyad == "KILIÇTEPE" for x in k)
    assert {x.kurum for x in k} == {"Emniyet Genel Müdürlüğü — İstihbarat"}
    assert all(x.kategori == Kategori.polis for x in k)
    omer = next(x for x in k if x.soyad == "AKTAŞ")  # alt dosya adı, ad sayfa metninden
    assert omer.ad == "Ömer" and omer.dis_kimlik == "istihbarat:omer-aktas"


class SahteGetirici:
    def __init__(self, ajax_sayfalari):
        self.ajax, self.cagrilar = ajax_sayfalari, []

    def metin(self, kod, url, *, params=None):
        self.cagrilar.append(("GET", url))
        return oku("egm_istihbarat.html") if "istihbarat" in url else oku("egm_liste.html")

    def post_json(self, kod, url, govde, *, referer):
        self.cagrilar.append(("POST", govde["page"], govde["ContentTypeId"]))
        return self.ajax.get((govde["ContentTypeId"], govde["page"]), "")


def test_sayfalar_ve_devam():
    g = SahteGetirici({("YNcLZaW4rMBeGR5FZn5E6A==", 2): oku("egm_ajax_dolu.html")})
    imlecler = [i for i, _ in egm.sayfalar(g, baslangic=None)]
    assert imlecler == ["sehitlerimiz:1", "sehitlerimiz:2", "ozelharekat:1", "istihbarat:1"]
    g2 = SahteGetirici({})
    assert [i for i, _ in egm.sayfalar(g2, baslangic="ozelharekat:1")] == ["istihbarat:1"]
    assert g2.cagrilar == [("POST", 2, "MNwu2a6REuJpCzWh5FhgSg=="), ("GET", egm.KOK + egm.ISTIHBARAT)]


def test_devam_ayni_bolumde_sonraki_sayfadan():
    ajax = oku("egm_ajax_dolu.html")
    g = SahteGetirici({("YNcLZaW4rMBeGR5FZn5E6A==", 2): ajax, ("YNcLZaW4rMBeGR5FZn5E6A==", 3): ajax})
    imlecler = [i for i, _ in egm.sayfalar(g, baslangic="sehitlerimiz:2")]
    assert imlecler == ["sehitlerimiz:3", "ozelharekat:1", "istihbarat:1"]
    assert ("GET", egm.KOK + "/sehitlerimiz") not in g.cagrilar
    assert g.cagrilar[0] == ("POST", 3, "YNcLZaW4rMBeGR5FZn5E6A==")


def test_bosluk_yaniti_bolumu_bitirir_ve_istihbarat_sonrasi_bos():
    g = SahteGetirici({("YNcLZaW4rMBeGR5FZn5E6A==", 2): "\r\n\r\n\r\n"})
    assert [i for i, _ in egm.sayfalar(g, baslangic=None)] == ["sehitlerimiz:1", "ozelharekat:1", "istihbarat:1"]
    assert list(egm.sayfalar(SahteGetirici({}), baslangic="istihbarat:1")) == []


def test_gecersiz_imlec():
    with pytest.raises(KaynakHatasi):
        list(egm.sayfalar(SahteGetirici({}), baslangic="bilinmeyen:x"))


# --- son inceleme: I2/I3/I5 ---

def _kart(href, baslik, tarih="01.02.2020"):
    return (f'<a class="news-card-horizontal" href="{href}"><span class="cardDate">{tarih}</span>'
            f'<h5 class="card-title">{baslik}</h5></a>')


def test_kart_basliklari_canli_ornekler(caplog):
    import logging
    html = (
        _kart("/a", "Şehidimiz Polis Memuru Hamdullah KIRTAY")
        + _kart("/b", "Şehidimiz 4.sınıf Emniyet Müdürü Tufan ŞAHİN")
        + _kart("/c", "Şehit Polis Memuru Vedat KAYA Şehit Polis Memuru Sedat YABALAK", "03.04.2016")
        + _kart("/d", "Şehit Polis Memuru")
        + _kart("/e", "Şehit")
    )
    with caplog.at_level(logging.WARNING, logger="app.kaynaklar.egm"):
        k = egm.kartlari_ayristir(html, bolum="sehitlerimiz")
    assert [(x.ad, x.soyad, x.gorev, x.dis_kimlik) for x in k] == [
        ("Hamdullah", "KIRTAY", "Polis Memuru", "/a"),
        ("Tufan", "ŞAHİN", "4. Sınıf Emniyet Müdürü", "/b"),
        ("Vedat", "KAYA", "Polis Memuru", "/c#vedat-kaya"),
        ("Sedat", "YABALAK", "Polis Memuru", "/c#sedat-yabalak"),
    ]
    vedat, sedat = k[2], k[3]
    assert vedat.tarih == sedat.tarih == date(2016, 4, 3)
    assert vedat.kaynak_url == sedat.kaynak_url == "https://www.egm.gov.tr/c"
    assert "/d" in caplog.text and "/e" in caplog.text  # adsız kart atlandı ve günlüğe yazıldı


def test_rutbesiz_ikinci_kisi_oncekinin_rutbesini_alir():
    k = egm.kartlari_ayristir(_kart("/v", "Şehit Komiser Ali KAYA ve Veli DEMİR"), bolum="sehitlerimiz")
    assert [(x.ad, x.gorev, x.dis_kimlik) for x in k] == [("Ali", "Komiser", "/v#ali-kaya"),
                                                         ("Veli", "Komiser", "/v#veli-demir")]


def test_istihbarat_dosya_adli_gorsel_gorunmez_karakterli_hucre():
    k = egm.istihbarat_ayristir(oku("egm_istihbarat.html"))
    assert all(any(c.isalpha() for c in x.ad) for x in k)
    assert "istihbarat:" not in {x.dis_kimlik for x in k}
    hasan = next(x for x in k if x.soyad == "ÖZTÜRK")  # alt "hasan_ozturk.png", ilk satır yalnızca U+200B
    assert (hasan.ad, hasan.dis_kimlik) == ("Hasan", "istihbarat:hasan-ozturk")


def test_istihbarat_gercek_sayfa_tum_adlar_dolu():
    gercek = (Path(__file__).parents[1] / "docs/superpowers/plans/kaynaklar/veri/"
              "egm_istihbarat_istihbarat-sehitlerimiz.html")
    if not gercek.exists():
        pytest.skip("gerçek örnek yok")
    k = egm.istihbarat_ayristir(gercek.read_text(encoding="utf-8"))
    assert k and all(any(c.isalpha() for c in x.ad) for x in k)
    assert len({x.dis_kimlik for x in k}) == len(k)
    assert any((x.ad, x.soyad) == ("Hasan", "ÖZTÜRK") for x in k)


def test_ajax_ayni_sayfa_donerse_durur():
    ajax = oku("egm_ajax_dolu.html")
    g = SahteGetirici({("YNcLZaW4rMBeGR5FZn5E6A==", n): ajax for n in range(2, 50)})
    imlecler = [i for i, _ in egm.sayfalar(g, baslangic=None)]
    assert imlecler == ["sehitlerimiz:1", "sehitlerimiz:2", "ozelharekat:1", "istihbarat:1"]


def test_ajax_kartsiz_sayfada_durur():
    g = SahteGetirici({("YNcLZaW4rMBeGR5FZn5E6A==", 2): "<div>sonuç yok</div>",
                       ("YNcLZaW4rMBeGR5FZn5E6A==", 3): oku("egm_ajax_dolu.html")})
    imlecler = [i for i, _ in egm.sayfalar(g, baslangic=None)]
    assert imlecler == ["sehitlerimiz:1", "ozelharekat:1", "istihbarat:1"]


def test_ajax_sayfa_siniri_hata(monkeypatch):
    monkeypatch.setattr(egm, "MAKS_SAYFA", 5)

    class Sonsuz(SahteGetirici):
        def post_json(self, kod, url, govde, *, referer):
            n = govde["page"]
            return _kart(f"/p{n}", f"Şehit Polis Memuru Ali KAYA{n}")

    with pytest.raises(KaynakHatasi, match="5 sayfayı"):
        list(egm.sayfalar(Sonsuz({}), baslangic=None))


def test_kart_ve_istihbarat_fotografi():
    ilk = egm.kartlari_ayristir(oku("egm_liste.html"), bolum="sehitlerimiz")[0]
    assert ilk.fotograf_url == (
        "https://www.egm.gov.tr/kurumlar/egm.gov.tr/Sehit%20Görsel/ahmet_turkoglu.jpg?mode=resize&width=500")
    bekir = next(k for k in egm.istihbarat_ayristir(oku("egm_istihbarat.html")) if k.soyad == "KILIÇTEPE")
    assert bekir.fotograf_url == ("https://www.egm.gov.tr/kurumlar/egm.gov.tr/IcSite/istihbarat/Arsiv/"
                                  "SiteAssets/Sayfalar/Sehitlerimiz/bekir_kilictepe.png")


def test_cok_kisili_kartin_toplu_fotografi_atanmaz():
    html = ('<a class="news-card-horizontal" href="/sehitlerimiz-ali-veli">'
            '<div class="card-img"><img src="/toplu.jpg"></div>'
            '<h5 class="card-title">Şehit Polis Memurları Ali KAYA ve Veli DEMİR</h5></a>')
    kayitlar = egm.kartlari_ayristir(html, bolum="sehitlerimiz")
    assert len(kayitlar) == 2 and all(k.fotograf_url is None for k in kayitlar)
