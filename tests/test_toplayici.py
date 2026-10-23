from datetime import date, datetime, timedelta

import pytest

from app import toplayici
from app.analiz import AnalizHatasi, HaberAnalizi, Kisi
from app.dates import TZ
from app.kaynaklar import haber
from app.kaynaklar.haber import HaberOgesi, Makale
from app.models import Durum, KaynakDurumu, Kaynak, Sehit

SIMDI = datetime(2026, 10, 23, 14, 0, tzinfo=TZ)


class SahteGetirici:
    def __init__(self):
        self.cagrilar = []

    def metin(self, kod, url):
        self.cagrilar.append(url)
        return "<html></html>"


class SahteAnalizci:
    def __init__(self, *cevaplar):
        self.cevaplar = list(cevaplar)
        self.cagri = 0

    def analiz_et(self, *, baslik, govde, yayin):
        self.cagri += 1
        c = self.cevaplar.pop(0) if self.cevaplar else analiz()
        if isinstance(c, Exception):
            raise c
        return c


def analiz(kisiler=None, **kw):
    v = dict(sehit_haberi=True, yeni_olay=True, resmi_kurum_duyurusu=True, isimsiz_sayisi=0,
             kisiler=[Kisi(ad="ali", soyad="kaya", kategori="asker", sehadet_tarihi="2026-10-22")]
             if kisiler is None else kisiler, olay_ozeti="Olay.")
    v.update(kw)
    return HaberAnalizi(**v)


def oge(n, saat_once=1.0, baslik="Şehit haberi", gun_once=0):
    yayin = SIMDI - timedelta(days=gun_once, hours=saat_once)
    return HaberOgesi("hurriyet", str(n), f"https://x/{n}", baslik, "", yayin)


@pytest.fixture
def ortam(monkeypatch):
    class O:
        ogeler = []
    monkeypatch.setattr(haber, "ogeleri_getir", lambda g, k: list(O.ogeler))
    monkeypatch.setattr(haber, "makale_ayristir", lambda html, k: Makale("Başlık", "Gövde", None))
    return O


def tara(s, ortam, ogeler, analizci, g=None):
    ortam.ogeler = ogeler
    return toplayici.haber_kaynagi_tara(s, "hurriyet", g or SahteGetirici(), analizci, simdi=SIMDI)


def imlec(s):
    return datetime.fromisoformat(s.get(KaynakDurumu, "hurriyet").imlec)


def test_ilk_calisma_yalnizca_bugun(session, ortam):
    dun, bugun = oge(1, gun_once=1), oge(2, saat_once=2)
    a = SahteAnalizci()
    d = tara(session, ortam, [bugun, dun], a)
    assert a.cagri == 1 and imlec(session) == bugun.yayin and d.eklenen == 1


def test_imlecten_sonrasi_ve_uc_gun_telafi(session, ortam):
    session.add(KaynakDurumu(kaynak_kodu="hurriyet", imlec=(SIMDI - timedelta(days=5)).isoformat(),
                             eklenen=0, birlesen=0, atlanan=0, hatali=0))
    session.commit()
    eski, yeni = oge(1, gun_once=4), oge(2, gun_once=2, baslik="Şehit 2")
    a = SahteAnalizci()
    tara(session, ortam, [yeni, eski], a)
    assert a.cagri == 1 and imlec(session) == yeni.yayin


def test_ayni_sehit_iki_haberde_tek_kayit(session, ortam):
    a = SahteAnalizci(analiz(), analiz())
    tara(session, ortam, [oge(1, 3), oge(2, 2)], a)
    assert session.query(Sehit).count() == 1
    s = session.query(Sehit).one()
    assert s.durum == Durum.onay_bekliyor and session.query(Kaynak).count() == 2
    assert s.ad == "Ali" and s.soyad == "KAYA"


def test_yayindaki_kayda_sadece_kaynak_eklenir(session, ortam, sehit_ekle):
    s = sehit_ekle(ad="Ali", soyad="KAYA", sehadet_tarihi=date(2026, 10, 22))
    d = tara(session, ortam, [oge(1)], SahteAnalizci())
    assert session.query(Sehit).count() == 1 and s.durum == Durum.yayinda
    assert len(s.kaynaklar) == 1 and d.birlesen == 1


def test_reddedilen_dirilmez(session, ortam, sehit_ekle):
    s = sehit_ekle(ad="Ali", soyad="KAYA", sehadet_tarihi=date(2026, 10, 22), durum="reddedildi")
    tara(session, ortam, [oge(1)], SahteAnalizci())
    assert s.durum == Durum.reddedildi and session.query(Sehit).count() == 1


def test_isimsiz_taslak(session, ortam):
    tara(session, ortam, [oge(1)], SahteAnalizci(analiz(kisiler=[], isimsiz_sayisi=2)))
    s = session.query(Sehit).one()
    assert s.isimsiz and s.durum == Durum.onay_bekliyor
    assert "2" in session.query(Kaynak).one().metin


def test_anma_haberi_kayit_uretmez(session, ortam):
    o = oge(1)
    tara(session, ortam, [o], SahteAnalizci(analiz(yeni_olay=False)))
    assert session.query(Sehit).count() == 0 and imlec(session) == o.yayin


def test_analiz_hatasi_imleci_tutar(session, ortam):
    o1, o2, o3 = oge(1, 3), oge(2, 2), oge(3, 1)
    d = tara(session, ortam, [o3, o2, o1], SahteAnalizci(analiz(), AnalizHatasi("x")))
    assert imlec(session) == o1.yayin and d.son_durum == "hata" and session.query(Sehit).count() == 1
    a = SahteAnalizci(analiz(), analiz())
    tara(session, ortam, [o3, o2, o1], a)
    assert a.cagri == 2 and imlec(session) == o3.yayin


def test_anahtar_yok_istek_yok(session, ortam):
    g = SahteGetirici()
    d = tara(session, ortam, [oge(1)], None, g)
    assert g.cagrilar == [] and d.son_mesaj == "API anahtarı yok" and d.son_durum == "hata"
    assert d.imlec is None


def test_gunluk_sinir(session, ortam, monkeypatch):
    monkeypatch.setattr(toplayici.get_settings(), "gunluk_analiz_siniri", 1)
    o1, o2 = oge(1, 3), oge(2, 2)
    a = SahteAnalizci(analiz())
    d = tara(session, ortam, [o2, o1], a)
    assert a.cagri == 1 and imlec(session) == o1.yayin and d.son_mesaj == "günlük analiz sınırı"


def test_sehit_gecmeyen_haber_analiz_edilmez(session, ortam):
    o = oge(1, baslik="Hava durumu")
    a = SahteAnalizci()
    tara(session, ortam, [o], a)
    assert a.cagri == 0 and imlec(session) == o.yayin


def test_toplayici_kayitlari_resmi_teyit_bayragi(session, ortam):
    tara(session, ortam, [oge(1)], SahteAnalizci(analiz(resmi_kurum_duyurusu=False)))
    assert session.query(Sehit).one().resmi_teyit is False


def test_izin_yok(session, ortam, monkeypatch):
    monkeypatch.setattr(toplayici.get_settings(), "kaynak_izinleri", ["egm"])
    g = SahteGetirici()
    d = tara(session, ortam, [oge(1)], SahteAnalizci(), g)
    assert d.son_mesaj == "izin yok" and g.cagrilar == []


def test_analiz_sayaci_gun_degisince_sifirlanir(session):
    assert toplayici.analiz_sayaci_artir(session, date(2026, 10, 22), 1)
    assert not toplayici.analiz_sayaci_artir(session, date(2026, 10, 22), 1)
    assert toplayici.analiz_sayaci_artir(session, date(2026, 10, 23), 1)
