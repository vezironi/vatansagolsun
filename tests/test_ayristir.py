from datetime import date
import pytest
from app.models import Hassasiyet as H, Kategori as K
from app.kaynaklar.ayristir import tarih_coz, isim_ayir, kategori_bul, soyadli_mi

@pytest.mark.parametrize("metin,beklenen", [
    ("22.07.2015", (date(2015, 7, 22), H.tam, 2015)),
    ("5.10.2015", (date(2015, 10, 5), H.tam, 2015)),
    ("2010-06-21", (date(2010, 6, 21), H.tam, 2010)),
    ("23 Aralık 2015", (date(2015, 12, 23), H.tam, 2015)),
    ("20 Kasım 2019", (date(2019, 11, 20), H.tam, 2019)),
    ("5 ekim 2015", (date(2015, 10, 5), H.tam, 2015)),
    ("17 Agustos 2016", (date(2016, 8, 17), H.tam, 2016)),
    ("1915", (None, H.yil, 1915)),
    ("", (None, H.bilinmiyor, None)),
    ("-", (None, H.bilinmiyor, None)),
    (None, (None, H.bilinmiyor, None)),
    ("31.02.2016", (None, H.bilinmiyor, None)),
    ("bilinmiyor", (None, H.bilinmiyor, None)),
])
def test_tarih_coz(metin, beklenen):
    assert tarih_coz(metin) == beklenen

def test_isim_ayir_unvanli():
    assert isim_ayir("Şehit Polis Memuru Ahmet TÜRKOĞLU", soyadli=True) == ("Ahmet", "TÜRKOĞLU", "Polis Memuru")
    assert isim_ayir("ULŞ. UZM. ÇVŞ. ABDURRAHMAN HİLAL", soyadli=True) == ("Abdurrahman", "HİLAL", "Uzman Çavuş")
    assert isim_ayir("Tayfun BAŞ", soyadli=True) == ("Tayfun", "BAŞ", None)
    assert isim_ayir("AHMET LÜTFİ", soyadli=False) == ("Ahmet Lütfi", None, None)
    assert isim_ayir("Ali Rıza Kaya", soyadli=True) == ("Ali Rıza", "KAYA", None)

def test_isim_ayir_ek_durumlar():
    assert isim_ayir("POLİS MEMURU Ali VELİ", soyadli=True) == ("Ali", "VELİ", "Polis Memuru")
    assert isim_ayir("Kıdemli Başpolis Memuru Can DEMİR", soyadli=True) == ("Can", "DEMİR", "Kıdemli Başpolis Memuru")
    assert isim_ayir("Komiser Yardımcısı Ece AY", soyadli=True) == ("Ece", "AY", "Komiser Yardımcısı")
    assert isim_ayir("Sözleşmeli Er Veli KAYA", soyadli=True) == ("Veli", "KAYA", "Sözleşmeli Er")
    assert isim_ayir("MUSTAFA", soyadli=False) == ("Mustafa", None, None)
    assert isim_ayir("Er", soyadli=True) == ("Er", None, None)

def test_kategori_bul():
    assert kategori_bul("Polis", "POLİS ŞEHİDİ") == K.polis
    assert kategori_bul("Jandarma Uzman Çavuş") == K.jandarma
    assert kategori_bul(None, "Milli Eğitim Bakanlığı Öğretmen") == K.ogretmen
    assert kategori_bul("Sivil Şehit / Memur") == K.diger
    assert kategori_bul("Er / Erbaş", "BİRİNCİ DÜNYA SAVAŞI") == K.asker

def test_soyadli_mi():
    assert soyadli_mi(2015, None) is True
    assert soyadli_mi(1915, None) is False
    assert soyadli_mi(None, "BİRİNCİ DÜNYA SAVAŞI (1914-1918) ÇANAKKALE CEPHESİ") is False
    assert soyadli_mi(None, "TERÖRLE MÜCADELE") is True
