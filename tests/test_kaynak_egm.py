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
    assert len(k) == 3 and all(x.tarih is None for x in k)
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
