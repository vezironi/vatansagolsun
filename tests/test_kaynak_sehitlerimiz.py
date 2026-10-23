from datetime import date
from pathlib import Path

import pytest

from app.kaynaklar import KaynakHatasi, KaynakIzniYok
from app.kaynaklar import sehitlerimiz as sh
from app.models import Kategori as K

F = Path(__file__).parent / "fixtures/kaynaklar"
oku = lambda ad: (F / ad).read_text(encoding="utf-8")


def test_kayit():
    h = sh.kayit_ayristir(oku("sh_kayit.html"), "/sehit/mustafa-aslan-116814")
    assert (h.ad, h.soyad, h.tarih, h.dis_kimlik) == ("Mustafa", "ASLAN", date(2026, 10, 14), "116814")
    assert h.kaynak_adi == "sehitlerimiz.org.tr — Türkiye Şehit Arşivi"
    assert h.kaynak_url == "https://sehitlerimiz.org.tr/sehit/mustafa-aslan-116814"


def test_kayit_alanlari():
    h = sh.kayit_ayristir(oku("sh_kayit.html"), "https://sehitlerimiz.org.tr/sehit/mustafa-aslan-116814")
    assert h.kaynak_kodu == "sehitlerimiz" and h.kaynak_url == "https://sehitlerimiz.org.tr/sehit/mustafa-aslan-116814"
    assert (h.gorev, h.baba_adi, h.memleket, h.kurum) == ("Piyade Uzman Çavuş", "Abdurrahman", "Gaziantep", "Türk Silahlı Kuvvetleri")
    assert (h.donem, h.kategori, h.yil) == ("Pençe-Kilit Harekâtı (2026)", K.asker, 2026)


def test_kayit_json_ld_yoksa_dl_den():
    html = oku("sh_kayit.html")
    bas = html.index('<script type="application/ld+json">')
    html = html[:bas] + html[html.index("</head>"):]
    h = sh.kayit_ayristir(html, "/sehit/mustafa-aslan-116814")
    assert (h.ad, h.soyad, h.tarih, h.gorev, h.memleket) == ("Mustafa", "ASLAN", date(2026, 10, 14), "Piyade Uzman Çavuş", "Gaziantep")


def test_kayit_ad_yoksa_hata():
    with pytest.raises(KaynakHatasi):
        sh.kayit_ayristir("<html><body><p>yok</p></body></html>", "/sehit/x-1")


def test_kayit_id():
    assert sh.kayit_id("/sehit/mustafa-aslan-116814") == 116814
    assert sh.kayit_id("https://sehitlerimiz.org.tr/sehit/yusuf-cavus-116820?x=1") == 116820
    with pytest.raises(KaynakHatasi):
        sh.kayit_id("/sehit/adsiz")


def test_yil_listesi():
    yollar, devam = sh.yil_listesi_ayristir(oku("sh_yil.html"))
    assert len(yollar) == 3 and devam is True
    assert yollar[0] == "/sehit/abdil-kadir-celik-112982"
    assert sh.yil_listesi_ayristir(oku("sh_yil_son.html"))[1] is False


def test_son_eklenenler():
    yollar = sh.son_eklenenler_ayristir(oku("sh_arsiv.html"))
    assert [sh.kayit_id(y) for y in yollar] == [116826, 116825, 116824]


class G:
    """Sahte Getirici: yol -> html ya da hata."""
    def __init__(s, sayfalar=None):
        s.cagrilar = []
        s.sayfalar = sayfalar or {}

    def metin(s, kod, url, params=None):
        assert kod == "sehitlerimiz"
        s.cagrilar.append((url, params))
        yanit = s.sayfalar.get((url, (params or {}).get("sayfa")), s.sayfalar.get(url))
        if isinstance(yanit, Exception):
            raise yanit
        if yanit is None:
            return oku("sh_arsiv.html") if url.endswith("/arsiv") else oku("sh_kayit.html")
        return yanit


def test_yeni_kayitlar():
    g = G()
    yollar = sh.son_eklenenler_ayristir(oku("sh_arsiv.html"))
    en_buyuk = max(sh.kayit_id(y) for y in yollar)
    kayitlar, yeni_max = sh.yeni_kayitlar(g, son_id=en_buyuk - 1)
    assert len(kayitlar) == 1 and yeni_max == en_buyuk
    assert sh.yeni_kayitlar(G(), son_id=en_buyuk) == ([], en_buyuk)
    # eskiden yeniye: son_id'den büyük hepsi çekilir
    g2 = G()
    kayitlar, yeni_max = sh.yeni_kayitlar(g2, son_id=0)
    assert len(kayitlar) == 3 and yeni_max == en_buyuk
    assert [u.rsplit("-", 1)[1] for u, _ in g2.cagrilar[1:]] == ["116824", "116825", "116826"]


def test_yeni_kayitlar_bozuk_kayit_imleci_ilerletmez():
    g = G({"https://sehitlerimiz.org.tr/sehit/nejdet-bayar-116825": KaynakHatasi("500")})
    kayitlar, yeni_max = sh.yeni_kayitlar(g, son_id=116823)
    assert len(kayitlar) == 2 and yeni_max == 116824
    with pytest.raises(KaynakIzniYok):
        sh.yeni_kayitlar(G({"https://sehitlerimiz.org.tr/sehit/okan-guney-116824": KaynakIzniYok("kapalı")}), son_id=0)


YIL = "https://sehitlerimiz.org.tr/yil/{}"
KAYIT = lambda y: "https://sehitlerimiz.org.tr" + y


def test_sayfalar_yil_ve_imlec():
    g = G({(YIL.format(2001), 1): oku("sh_yil.html"), (YIL.format(2001), 2): oku("sh_yil_son.html"),
           (YIL.format(2002), 1): oku("sh_yil_son.html")})
    sonuc = list(sh.sayfalar(g, baslangic=None, yillar=range(2001, 2003)))
    assert [i for i, _ in sonuc] == ["2001:1", "2001:2", "2002:1"]
    assert [len(k) for _, k in sonuc] == [3, 3, 3]
    assert all(h.kaynak_kodu == "sehitlerimiz" for _, k in sonuc for h in k)
    g2 = G({(YIL.format(2001), 2): oku("sh_yil_son.html"), (YIL.format(2002), 1): oku("sh_yil_son.html")})
    assert [i for i, _ in sh.sayfalar(g2, baslangic="2001:1", yillar=range(2001, 2003))] == ["2001:2", "2002:1"]
    assert not any(u == YIL.format(2001) and p == {"sayfa": 1} for u, p in g2.cagrilar)


def test_sayfalar_404_yili_atlar():
    g = G({(YIL.format(2001), 1): KaynakHatasi("404", durum_kodu=404), (YIL.format(2002), 1): oku("sh_yil_son.html")})
    assert [i for i, _ in sh.sayfalar(g, baslangic=None, yillar=range(2001, 2003))] == ["2002:1"]


def test_sayfalar_liste_hatasi_olumcul():
    g = G({(YIL.format(2001), 1): KaynakHatasi("500", durum_kodu=None)})
    with pytest.raises(KaynakHatasi):
        list(sh.sayfalar(g, baslangic=None, yillar=range(2001, 2002)))
    g = G({(YIL.format(2001), 1): KaynakHatasi("403", durum_kodu=403)})
    with pytest.raises(KaynakHatasi):
        list(sh.sayfalar(g, baslangic=None, yillar=range(2001, 2002)))


def test_sayfalar_tek_kayit_hatasi_atlanir():
    g = G({(YIL.format(2001), 1): oku("sh_yil_son.html"),
           KAYIT("/sehit/abdulalim-celikten-116006"): KaynakHatasi("500"),
           KAYIT("/sehit/abdulhamit-anli-115992"): "<html><body>bozuk</body></html>"})
    (imlec, kayitlar), = sh.sayfalar(g, baslangic=None, yillar=range(2001, 2002))
    assert imlec == "2001:1" and len(kayitlar) == 1


def test_sayfalar_izin_hatasi_olumcul():
    g = G({(YIL.format(2001), 1): oku("sh_yil_son.html"), KAYIT("/sehit/abdulalim-celikten-116006"): KaynakIzniYok("kapalı")})
    with pytest.raises(KaynakIzniYok):
        list(sh.sayfalar(g, baslangic=None, yillar=range(2001, 2002)))


def test_sayfalar_gecersiz_imlec():
    with pytest.raises(KaynakHatasi):
        list(sh.sayfalar(G(), baslangic="x", yillar=range(2001, 2002)))
