from app.text import tr_lower, tr_upper, ad_duzenle, soyad_duzenle, katla, slug, gorunen_ad

def test_tr_buyuk_kucuk():
    assert tr_lower("IŞIK İLHAN") == "ışık ilhan"
    assert tr_upper("işık ılgaz") == "İŞIK ILGAZ"

def test_ad_duzenle():
    assert ad_duzenle("AHMET LÜTFİ") == "Ahmet Lütfi"
    assert ad_duzenle("ismail") == "İsmail"
    assert ad_duzenle("  ışıl  ") == "Işıl"

def test_soyad_duzenle():
    assert soyad_duzenle(" yılmaz ") == "YILMAZ"
    assert soyad_duzenle("şimşek") == "ŞİMŞEK"

def test_katla_esitler():
    assert katla("ŞAHİN") == katla("Şahin") == katla("sahin") == "sahin"
    assert katla("ISIK") == katla("Işık") == "isik"
    assert katla("Ahmet   Çağrı") == "ahmet cagri"

def test_slug():
    assert slug("Ahmet Yılmaz") == "ahmet-yilmaz"
    assert slug("İsmail — Aşçıoğullarından") == "ismail-asciogullarindan"

def test_gorunen_ad():
    assert gorunen_ad("Ahmet", "YILMAZ", None) == "Ahmet YILMAZ"
    assert gorunen_ad("İsmail", None, "Aşçıoğullarından") == "İsmail — Aşçıoğullarından"
    assert gorunen_ad("Mehmet", None, None) == "Mehmet"
