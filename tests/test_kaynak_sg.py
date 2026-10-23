from datetime import date
from pathlib import Path

from app.kaynaklar import sg
from app.models import Kategori

HTML = (Path(__file__).parent / "fixtures/kaynaklar/sg.html").read_text(encoding="utf-8")


def test_sg():
    k = sg.ayristir(HTML)
    assert len(k) == 3
    hakan = next(x for x in k if x.soyad == "KARATAŞ")
    assert (hakan.ad, hakan.tarih, hakan.kurum) == ("Hakan", date(2019, 11, 20), "Sahil Güvenlik Komutanlığı")
    assert hakan.kategori == Kategori.asker and hakan.kaynak_kodu == "sg"
    assert hakan.dis_kimlik == "/kurumlar/sg.gov.tr/sehitlerimiz/pdf/HakanKaratas.pdf"
    assert hakan.kaynak_adi == "Sahil Güvenlik Komutanlığı"
    assert hakan.kaynak_url == "https://www.sg.gov.tr/sehitlerimiz"


def test_pdf_yoksa_ad_kimligi_ve_bozuklar():
    html = (
        '<div class="manager-vertical-card"><div class="manager-sm-card-body">'
        '<span class="manager-name">Ali Rıza YÜCEL</span><p>-</p></div></div>'
        '<div class="manager-vertical-card"><div class="manager-sm-card-body"><p>1 Ocak 2000</p></div></div>'
    )
    k = sg.ayristir(html)
    assert len(k) == 1 and k[0].dis_kimlik == "sg:ali-riza-yucel" and k[0].tarih is None


class SahteGetirici:
    def __init__(self):
        self.cagrilar = []

    def metin(self, kod, url, *, params=None):
        self.cagrilar.append((kod, url))
        return HTML


def test_sayfalar():
    g = SahteGetirici()
    out = list(sg.sayfalar(g, baslangic=None))
    assert [i for i, _ in out] == ["1"] and len(out[0][1]) == 3
    assert g.cagrilar == [("sg", "https://www.sg.gov.tr/sehitlerimiz")]
    assert list(sg.sayfalar(SahteGetirici(), baslangic="1")) == []
