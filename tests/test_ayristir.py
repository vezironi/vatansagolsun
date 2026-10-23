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
    # Yalnızca önekten oluşan metin: ad boş (eskiden "en az bir sözcük ad kalır" koruması vardı).
    assert isim_ayir("Er", soyadli=True) == ("", None, "Er")

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


# --- son inceleme: I2/I3/I4 ---

from app.kaynaklar.ayristir import kisileri_ayir, metin_temizle  # noqa: E402


def test_metin_temizle():
    assert metin_temizle("​") == ""
    assert metin_temizle(" Hasan ​ÖZTÜRK﻿ ⁠‌‍ ") == "Hasan ÖZTÜRK"
    assert metin_temizle(None) == ""
    assert tarih_coz("​08.10.2026 ") == (date(2026, 10, 8), H.tam, 2026)


@pytest.mark.parametrize("ham,beklenen", [
    ("P. ASB. KD. BÇVŞ. ÖMER HALİSDEMİR", ("Ömer", "HALİSDEMİR", "Piyade Astsubay Kıdemli Başçavuş")),
    ("J. UZM. ÇVŞ. AHMET KAYA", ("Ahmet", "KAYA", "Jandarma Uzman Çavuş")),
    ("HV. PLT. BNB. İBRAHİM BOLAT", ("İbrahim", "BOLAT", "Hava Pilot Binbaşı")),
    ("P. SÖZ. ER İLKER AĞÇAY", ("İlker", "AĞÇAY", "Piyade Sözleşmeli Er")),
    ("ULŞ. UZM.ÇVŞ. ABDURRAHMAN HİLAL", ("Abdurrahman", "HİLAL", "Uzman Çavuş")),
    ("Şehidimiz Polis Memuru Hamdullah KIRTAY", ("Hamdullah", "KIRTAY", "Polis Memuru")),
    ("Şehidimiz 4.sınıf Emniyet Müdürü Tufan ŞAHİN", ("Tufan", "ŞAHİN", "4. Sınıf Emniyet Müdürü")),
    ("Şehit 2. Sınıf Ali VELİ", ("Ali", "VELİ", "2. Sınıf Emniyet Müdürü")),
    ("Şehit Emniyet Müdür Yardımcısı Can AY", ("Can", "AY", "Emniyet Müdür Yardımcısı")),
    ("Şehit Polis Memuru", ("", None, "Polis Memuru")),
    ("Şehit", ("", None, None)),
    ("​", ("", None, None)),
])
def test_isim_ayir_rutbe_birlestirme(ham, beklenen):
    assert isim_ayir(ham, soyadli=True) == beklenen


def test_kisileri_ayir():
    assert kisileri_ayir("Şehit Polis Memuru Vedat KAYA Şehit Polis Memuru Sedat YABALAK") == [
        "Şehit Polis Memuru Vedat KAYA", "Şehit Polis Memuru Sedat YABALAK"]
    assert kisileri_ayir("Şehidimiz Polis Memuru Hamdullah KIRTAY") == ["Şehidimiz Polis Memuru Hamdullah KIRTAY"]
    assert kisileri_ayir("Şehidimiz 4.sınıf Emniyet Müdürü Tufan ŞAHİN") == [
        "Şehidimiz 4. sınıf Emniyet Müdürü Tufan ŞAHİN"]
    assert kisileri_ayir("Polis Memuru Ali KAYA ve Veli DEMİR - Can AY") == [
        "Polis Memuru Ali KAYA", "Veli DEMİR", "Can AY"]
    # sondaki rütbe sözcüğü soyaddır ("ER", "BEKÇİ"), yeni kişi değil
    assert kisileri_ayir("Şehit Polis Memuru Ahmet ER") == ["Şehit Polis Memuru Ahmet ER"]
    assert kisileri_ayir("Şehit Polis Memuru") == ["Şehit Polis Memuru"]
    assert kisileri_ayir("​") == []
