import json
from datetime import date
from pathlib import Path

import pytest

from app.kaynaklar import KaynakHatasi, kahramanlar as kh
from app.models import Hassasiyet as H, Kategori as K

F = Path(__file__).parent / "fixtures/kaynaklar"


def _k(**alan):
    k = {"ad": "ALİ", "rutbe": "Er / Erbaş", "sehadet_tarihi": "", "harp": "X", "baba_adi": "", "lakap": "",
         "dogum_yili": "", "memleketi": "", "il_filtresi": "", "sayfa": 0}
    k.update(alan)
    return k


def test_modern_polis():
    h = kh.kayit_cevir({"ad":"Tayfun BAŞ","rutbe":"Polis","sehadet_tarihi":"14.06.2026","harp":"POLİS ŞEHİDİ","baba_adi":"","lakap":"","dogum_yili":"","memleketi":"","il_filtresi":"","sayfa":0})
    assert (h.ad, h.soyad, h.tarih, h.kategori, h.memleket) == ("Tayfun", "BAŞ", date(2026, 6, 14), K.polis, None)
    assert (h.kaynak_kodu, h.kaynak_adi, h.kaynak_url) == ("kahramanlar", "kahramanlar.org.tr", "https://kahramanlar.org.tr/")


def test_osmanli_tek_isim():
    h = kh.kayit_cevir({"ad":"MUSTAFA","rutbe":"Er / Erbaş","sehadet_tarihi":"","harp":"BİRİNCİ DÜNYA SAVAŞI (1914-1918) ÇANAKKALE CEPHESİ","baba_adi":"HASAN","lakap":"","dogum_yili":"1885","memleketi":"KASTAMONU ARAÇ","il_filtresi":"KASTAMONU","sayfa":0})
    assert (h.ad, h.soyad, h.hassasiyet, h.baba_adi, h.dogum_yili, h.memleket) == ("Mustafa", None, H.bilinmiyor, "Hasan", 1885, "Kastamonu Araç")
    assert h.yil is None and h.gorev == "Er / Erbaş" and h.donem.startswith("BİRİNCİ DÜNYA")


def test_msb_yil_parantezden():
    h = kh.kayit_cevir({"ad":"ULŞ. UZM. ÇVŞ. ABDURRAHMAN HİLAL","rutbe":"Uzman Çavuş","sehadet_tarihi":"","harp":"MSB GÜNCEL ŞEHİT VE VEFAT DUYURULARI (2026)","baba_adi":"","lakap":"","dogum_yili":"","memleketi":"TÜRKİYE","il_filtresi":"MSB","sayfa":0})
    assert (h.ad, h.soyad, h.gorev, h.hassasiyet, h.yil, h.memleket) == ("Abdurrahman", "HİLAL", "Uzman Çavuş", H.yil, 2026, None)


def test_ayni_kayit_ayni_kimlik():
    k = _k()
    assert kh.kayit_cevir(dict(k)).dis_kimlik == kh.kayit_cevir(dict(k)).dis_kimlik
    assert kh.kayit_cevir(dict(k)).dis_kimlik.startswith("kh:") and len(kh.kayit_cevir(dict(k)).dis_kimlik) == 23
    assert kh.kayit_cevir(_k(ad="VELİ")).dis_kimlik != kh.kayit_cevir(_k()).dis_kimlik


def test_bos_ad_none():
    assert kh.kayit_cevir(_k(ad="")) is None
    assert kh.kayit_cevir(_k(ad="  -  ")) is None


def test_tire_bos_sayilir():
    h = kh.kayit_cevir(_k(baba_adi="-", dogum_yili="-", memleketi="-", lakap="-"))
    assert (h.baba_adi, h.dogum_yili, h.memleket, h.lakap) == (None, None, None, None)


def test_lakap_unvan_atilir_eski_donemde_tutulur():
    polis = kh.kayit_cevir(_k(ad="FEYYAZ YUMUŞAK", rutbe="Polis", sehadet_tarihi="22.07.2015", harp="TERÖRLE MÜCADELE", lakap="ŞEHİT POLİS", memleketi="TÜRKİYE"))
    assert (polis.ad, polis.soyad, polis.lakap, polis.memleket, polis.kategori) == ("Feyyaz", "YUMUŞAK", None, None, K.polis)
    pasa = kh.kayit_cevir(_k(ad="İSMAİL", rutbe="General", harp="OSMANLI-RUS SAVAŞI (1877-1878/93 HARBİ)", lakap="ALİPAŞA"))
    assert (pasa.ad, pasa.soyad, pasa.lakap, pasa.yil) == ("İsmail", None, "Alipaşa", None)


def test_yil_yalniz_dort_haneli_parantez():
    assert kh.kayit_cevir(_k(harp="PENÇE-KİLİT HAREKATI (2024)")).yil == 2024
    h = kh.kayit_cevir(_k(harp="BİRİNCİ DÜNYA SAVAŞI (1914-1918)"))
    assert (h.yil, h.hassasiyet) == (None, H.bilinmiyor)


def test_tarih_yilin_onune_gecer():
    h = kh.kayit_cevir(_k(sehadet_tarihi="5 Ekim 2015", harp="X (2020)"))
    assert (h.tarih, h.hassasiyet, h.yil) == (date(2015, 10, 5), H.tam, 2015)


def test_dogum_yili_sayi_degilse_none():
    assert kh.kayit_cevir(_k(dogum_yili="1885?")).dogum_yili is None


def test_fixture_kayitlari_cevrilir():
    veri = json.loads((F / "kh_sayfa.json").read_text(encoding="utf-8"))["data"]
    kayitlar = [kh.kayit_cevir(k) for k in veri]
    assert all(kayitlar) and len({h.dis_kimlik for h in kayitlar}) == len(veri)
    koroglu = next(h for h in kayitlar if h.soyad == "KÖROĞLU")
    # "P. UZM. ÇVŞ." baştaki tüm kısaltmalar sırayla açılır (P11 kararı)
    assert (koroglu.ad, koroglu.gorev, koroglu.kategori, koroglu.yil, koroglu.lakap) == ("Ahmet", "Piyade Uzman Çavuş", K.asker, 2024, None)
    assert (koroglu.baba_adi, koroglu.dogum_yili, koroglu.memleket) == ("Ömer", 1994, "Giresun Çanakçı")
    omer = next(h for h in kayitlar if h.soyad == "HALİSDEMİR")
    assert (omer.ad, omer.gorev) == ("Ömer", "Piyade Astsubay Kıdemli Başçavuş")
    alper = next(h for h in kayitlar if h.soyad == "KOCA")
    assert (alper.ad, alper.gorev) == ("Alper", "Piyade Çavuş")
    sivil = next(h for h in kayitlar if h.soyad == "GÜRSOY")
    assert (sivil.kategori, sivil.memleket) == (K.diger, "Kırşehir")


def test_sayfalar_has_more():
    yanitlar = {1: json.loads((F / "kh_sayfa.json").read_text(encoding="utf-8")), 2: json.loads((F / "kh_son.json").read_text(encoding="utf-8"))}
    cagrilar = []

    class G:
        def json(self, kod, url, params=None):
            cagrilar.append((kod, url, params))
            return yanitlar[params["page"]]
    assert [i for i, _ in kh.sayfalar(G(), baslangic=None)] == ["1", "2"]
    assert cagrilar[0] == ("kahramanlar", "https://kahramanlar.org.tr/api.php", {"page": 1, "limit": 50})
    assert [i for i, _ in kh.sayfalar(G(), baslangic="1")] == ["2"]
    sayfalar = dict(kh.sayfalar(G(), baslangic=None))
    assert len(sayfalar["1"]) == 6 and len(sayfalar["2"]) == 1


def test_sayfalar_bozuk_kayit_atlanir():
    class G:
        def json(self, kod, url, params=None):
            return {"data": [_k(ad=""), "bozuk", _k(ad="VELİ")], "has_more": False}
    (imlec, kayitlar), = kh.sayfalar(G(), baslangic=None)
    assert [h.ad for h in kayitlar] == ["Veli"]


def test_sayfalar_gecersiz_imlec_ve_bozuk_yanit():
    with pytest.raises(KaynakHatasi):
        list(kh.sayfalar(None, baslangic="x"))

    class G:
        def json(self, kod, url, params=None):
            return {"hata": 1}
    with pytest.raises(KaynakHatasi):
        list(kh.sayfalar(G(), baslangic=None))


def test_bos_data_has_more_olsa_da_durur():
    cagrilar = []

    class G:
        def json(self, kod, url, params=None):
            cagrilar.append(params["page"])
            if params["page"] > 3:
                raise AssertionError("boş sayfadan sonra istek atılmamalı")
            return {"data": [_k()] if params["page"] == 1 else [], "has_more": True}
    assert [i for i, _ in kh.sayfalar(G(), baslangic=None)] == ["1"]
    assert cagrilar == [1, 2]


def test_dogum_yili_yalniz_dort_ascii_rakam():
    assert kh.kayit_cevir(_k(dogum_yili="1885")).dogum_yili == 1885
    assert kh.kayit_cevir(_k(dogum_yili="١٨٨٥")).dogum_yili is None  # Arapça-Hint rakamları
    assert kh.kayit_cevir(_k(dogum_yili="18²")).dogum_yili is None  # üst simge: isdigit() True idi
    assert kh.kayit_cevir(_k(dogum_yili="85")).dogum_yili is None
