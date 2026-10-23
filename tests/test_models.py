from datetime import date


def test_alanlari_yenile_tam_tarih(sehit_ekle):
    s = sehit_ekle(ad="AHMET LÜTFİ", soyad="şimşek", memleket="Sivas", sehadet_tarihi=date(2011, 10, 23))
    assert (s.ad, s.soyad) == ("Ahmet Lütfi", "ŞİMŞEK")
    assert (s.yil, s.ay, s.gun) == (2011, 10, 23)
    assert s.slug == "ahmet-lutfi-simsek"
    assert "simsek" in s.arama_metni and "sivas" in s.arama_metni
    assert s.url == f"/sehit/ahmet-lutfi-simsek-{s.id}"


def test_alanlari_yenile_sadece_yil(sehit_ekle):
    s = sehit_ekle(tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=1915)
    assert (s.yil, s.ay, s.gun, s.sehadet_tarihi) == (1915, None, None, None)


def test_soyadsiz_lakapli(sehit_ekle):
    s = sehit_ekle(ad="İSMAİL", soyad=None, lakap="AŞÇIOĞULLARINDAN", tarih_hassasiyeti="bilinmiyor", sehadet_tarihi=None)
    assert s.gorunen_ad == "İsmail — Aşçıoğullarından"
    assert s.yil is None


def test_bos_slug_yedegi(sehit_ekle):
    s = sehit_ekle(ad="???", soyad=None)
    assert s.slug == "sehit"
    assert s.url == f"/sehit/sehit-{s.id}"


def test_bos_soyad_none_olur(sehit_ekle):
    s = sehit_ekle(soyad="   ")
    assert s.soyad is None


def test_varsayilanlar_ve_zaman(sehit_ekle):
    s = sehit_ekle(durum="onay_bekliyor")
    assert s.durum == "onay_bekliyor"
    assert s.resmi_teyit is False and s.isimsiz is False
    assert s.olusturma is not None


def test_isim_anahtari(sehit_ekle):
    s = sehit_ekle(ad="ÖMER", soyad="şahin")
    assert s.isim_anahtari == "omer sahin"
    t = sehit_ekle(ad="İsmail", soyad=None, lakap="Aşçıoğullarından")
    assert t.isim_anahtari == "ismail asciogullarindan"


def test_kaynak_dis_kimlik_tekil(session, sehit_ekle):
    import pytest
    from sqlalchemy.exc import IntegrityError
    from app.models import Kaynak
    s = sehit_ekle()
    s.kaynaklar.append(Kaynak(kaynak_adi="EGM", kaynak_kodu="egm", dis_kimlik="/a"))
    s.kaynaklar.append(Kaynak(kaynak_adi="EGM", kaynak_kodu="egm", dis_kimlik="/a"))
    with pytest.raises(IntegrityError):
        session.commit()
