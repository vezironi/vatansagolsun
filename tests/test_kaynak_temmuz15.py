import json
from datetime import date
from pathlib import Path

import pytest

from app.kaynaklar import KaynakHatasi, temmuz15
from app.models import Hassasiyet, Kategori

FIXTURES = Path(__file__).parent / "fixtures/kaynaklar"
LISTE = (FIXTURES / "temmuz15_liste.html").read_text(encoding="utf-8")
BILGI = json.loads((FIXTURES / "temmuz15_bilgi.json").read_text(encoding="utf-8"))


def test_liste_ayristir():
    ogeler = temmuz15.liste_ayristir(LISTE)
    assert [o.id for o in ogeler] == [1, 3, 9, 55]  # kimliğe göre sıralı, boş data-id atlanır
    akif = next(o for o in ogeler if o.id == 3)
    assert (akif.ad, akif.dogum, akif.sehadet, akif.meslek) == ("AKİF ALTAY", "1963", "15 Temmuz 2016", "Polis")


def _kayit(kimlik, bilgi=None):
    oge = next(o for o in temmuz15.liste_ayristir(LISTE) if o.id == kimlik)
    return temmuz15.kayit_olustur(oge, BILGI[str(kimlik)] if bilgi is None else bilgi)


def test_polis_kaydi():
    k = _kayit(3)
    assert (k.ad, k.soyad, k.tarih, k.hassasiyet, k.dogum_yili) == (
        "Akif", "ALTAY", date(2016, 7, 15), Hassasiyet.tam, 1963)
    assert k.kategori == Kategori.polis and k.gorev == "Polis"
    assert (k.memleket, k.kurum) == ("Burdur", "Özel Harekat Şube Müdürlüğü")
    assert (k.kaynak_kodu, k.dis_kimlik) == ("temmuz15", "temmuz15:3")
    assert k.kaynak_url == "https://15temmuzsehitleri.com/tr/sehitlerimiz-111"
    assert k.kaynak_adi == "15 Temmuz Şehitleri (15temmuzsehitleri.com)"


def test_asker_ve_sivil_kategorisi():
    assert _kayit(55).kategori == Kategori.asker
    ogrenci = _kayit(1)
    assert ogrenci.kategori == Kategori.diger and ogrenci.gorev == "Öğrenci"
    assert ogrenci.metin.startswith("Babasının ısrarına aldırmadı")  # HTML ve varlıklar çözülür


def test_15_temmuzdan_onceki_tarih_yil_olur():
    # Kaynakta "16 Temmuz 1954" yazıyor (doğum yılıyla karışmış); tarih güvenilmez.
    k = _kayit(9)
    assert (k.tarih, k.hassasiyet, k.yil) == (None, Hassasiyet.yil, 2016)
    assert k.kategori == Kategori.diger  # şehadet yeri "Jandarma Genel Komutanlığı" kategori belirlemez


def test_bilgi_yoksa_liste_verisi_kullanilir():
    k = _kayit(3, bilgi={})
    assert (k.ad, k.soyad, k.tarih, k.dogum_yili, k.gorev) == ("Akif", "ALTAY", date(2016, 7, 15), 1963, "Polis")
    assert k.kategori == Kategori.polis and k.memleket is None and k.metin is None


class SahteGetirici:
    def __init__(self, bozuk=()):
        self.cagrilar = []
        self.bozuk = set(bozuk)

    def metin(self, kod, url, *, params=None):
        self.cagrilar.append((kod, url, None))
        return LISTE

    def json(self, kod, url, *, params=None):
        self.cagrilar.append((kod, url, params["Id"]))
        if params["Id"] in self.bozuk:
            raise KaynakHatasi("HTTP 404", durum_kodu=404)
        return BILGI[str(params["Id"])]


def test_sayfalar_parcali_ve_kaldigi_yerden(monkeypatch):
    monkeypatch.setattr(temmuz15, "PARCA", 3)
    g = SahteGetirici()
    out = list(temmuz15.sayfalar(g, baslangic=None))
    assert [(i, [k.dis_kimlik for k in ks]) for i, ks in out] == [
        ("9", ["temmuz15:1", "temmuz15:3", "temmuz15:9"]), ("55", ["temmuz15:55"])]
    assert g.cagrilar[0] == ("temmuz15", "https://15temmuzsehitleri.com/tr/sehitlerimiz-111", None)
    assert [c[1] for c in g.cagrilar[1:]] == ["https://15temmuzsehitleri.com/TR/f/HeroInfo"] * 4

    g = SahteGetirici()
    out = list(temmuz15.sayfalar(g, baslangic="9"))
    assert [(i, [k.dis_kimlik for k in ks]) for i, ks in out] == [("55", ["temmuz15:55"])]
    assert [c[2] for c in g.cagrilar] == [None, 55]


def test_bilgi_4xx_ise_liste_verisiyle_devam():
    out = list(temmuz15.sayfalar(SahteGetirici(bozuk={3}), baslangic=None))
    akif = next(k for _, ks in out for k in ks if k.dis_kimlik == "temmuz15:3")
    assert akif.soyad == "ALTAY" and akif.memleket is None


def test_ag_hatasi_aktarimi_durdurur():
    class AgHatali(SahteGetirici):
        def json(self, kod, url, *, params=None):
            raise KaynakHatasi("ağ hatası")

    with pytest.raises(KaynakHatasi):
        list(temmuz15.sayfalar(AgHatali(), baslangic=None))


def test_fotograf_sehadet_yeri_ve_olayi():
    k = _kayit(1)
    assert k.fotograf_url == (
        "https://15temmuzsehitleri.com/Content/images/Kahramanlarimiz/Abdullah-tayyip-olcok/abdullah-tayyip-olcok.png")
    assert k.sehadet_yeri == "15 Temmuz Şehitler Köprüsü"
    # sitenin yarıda kestiği biyografi son tam cümlede biter; tam metin kaynakta kalır
    assert k.sehadet_olayi.startswith("Babasının ısrarına aldırmadı")
    assert k.sehadet_olayi.endswith("hukuk fakültesine girecekti.")
    assert k.metin.endswith("sokağa")


def test_ayrinti_yoksa_bos():
    k = _kayit(3, {})
    assert (k.sehadet_yeri, k.sehadet_olayi) == (None, None)
    assert k.fotograf_url.endswith("/Akif-Altay/akif-altay.png")
