from datetime import date
from app import repo
from app.models import Durum

def test_istatistik_sadece_yayinda(session, sehit_ekle):
    sehit_ekle(sehadet_tarihi=date(2026, 3, 1))
    sehit_ekle(sehadet_tarihi=date(2016, 3, 1))
    sehit_ekle(sehadet_tarihi=date(2026, 4, 1), durum="onay_bekliyor")
    sehit_ekle(sehadet_tarihi=date(2026, 4, 2), durum="reddedildi")
    assert repo.istatistik(session, date(2026, 10, 23)) == repo.Istatistik(toplam=2, bu_yil=1, yil=2026)

def test_listele_siralama_ve_tarihsizler_sonda(session, sehit_ekle):
    a = sehit_ekle(sehadet_tarihi=date(2011, 1, 1))
    b = sehit_ekle(tarih_hassasiyeti="bilinmiyor", sehadet_tarihi=None)
    c = sehit_ekle(sehadet_tarihi=date(2016, 5, 5))
    d = sehit_ekle(tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=1915)
    assert [x.id for x in repo.listele(session).kayitlar] == [c.id, a.id, d.id, b.id]

def test_listele_2000_oncesi_tarihsizleri_icerir(session, sehit_ekle):
    sehit_ekle(sehadet_tarihi=date(2011, 1, 1))
    eski = sehit_ekle(tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=1915)
    bilinmeyen = sehit_ekle(tarih_hassasiyeti="bilinmiyor", sehadet_tarihi=None)
    ids = {x.id for x in repo.listele(session, yil="2000-oncesi").kayitlar}
    assert ids == {eski.id, bilinmeyen.id}

def test_listele_turkce_arama(session, sehit_ekle):
    s = sehit_ekle(ad="Ömer", soyad="Şahin", memleket="Muş")
    sehit_ekle(ad="Ali", soyad="Kaya")
    for q in ["sahin", "ŞAHİN", "Şahin", "omer sahin", "mus"]:
        assert [x.id for x in repo.listele(session, q=q).kayitlar] == [s.id], q

def test_listele_sayfalama(session, sehit_ekle):
    for i in range(30):
        sehit_ekle(sehadet_tarihi=date(2016, 1, 1))
    s2 = repo.listele(session, sayfa=2, adet=25)
    assert s2.toplam == 30 and len(s2.kayitlar) == 5
    assert repo.listele(session, sayfa=99).kayitlar == []

def test_yil_donumu_kurallari(session, sehit_ekle):
    ok = sehit_ekle(sehadet_tarihi=date(2011, 10, 23))
    sehit_ekle(sehadet_tarihi=date(1998, 10, 23))                       # 2000 öncesi
    sehit_ekle(tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=2011)  # tarih tam değil
    sehit_ekle(sehadet_tarihi=date(2016, 10, 23), durum="onay_bekliyor")
    assert [x.id for x in repo.yil_donumu(session, 10, 23, artik_yil=False)] == [ok.id]

def test_yil_donumu_29_subat(session, sehit_ekle):
    s = sehit_ekle(sehadet_tarihi=date(2016, 2, 29))
    assert [x.id for x in repo.yil_donumu(session, 2, 28, artik_yil=False)] == [s.id]
    assert repo.yil_donumu(session, 2, 28, artik_yil=True) == []

def test_api_haric_kaynak(session, sehit_ekle, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "api_haric_kaynaklar", ["sehitlerimiz"])
    gizli = sehit_ekle(kaynak_kodu="sehitlerimiz")
    acik = sehit_ekle(kaynak_kodu="egm")
    assert [x.id for x in repo.listele(session, api=True).kayitlar] == [acik.id]
    assert repo.getir(session, gizli.id, api=True) is None
    assert repo.getir(session, gizli.id) is not None  # sitede görünür

def test_getir_onay_bekleyen_sizmaz(session, sehit_ekle):
    s = sehit_ekle(durum="onay_bekliyor")
    assert repo.getir(session, s.id) is None
    assert repo.getir(session, s.id, sadece_yayinda=False).id == s.id

def test_birlestir(session, sehit_ekle):
    from app.models import Kaynak
    hedef = sehit_ekle(memleket=None)
    fazla = sehit_ekle(memleket="Van", durum="onay_bekliyor")
    fazla.kaynaklar.append(Kaynak(kaynak_adi="Hürriyet", url="https://x"))
    session.commit()
    sonuc = repo.birlestir(session, hedef, fazla)
    assert sonuc.memleket == "Van" and len(sonuc.kaynaklar) == 1
    assert repo.getir(session, fazla.id, sadece_yayinda=False) is None

def test_sehitveri_dogrulama():
    import pytest
    from app.schemas import SehitVeri
    with pytest.raises(ValueError):
        SehitVeri(ad="Ali", kategori="asker", kaynak_kodu="panel", tarih_hassasiyeti="tam", sehadet_tarihi=None)
