from datetime import date

from app import aktarim
from app.kaynaklar import HamKayit
from app.models import Durum, Hassasiyet as H, KaynakDurumu, Sehit


def test_zamanlayici_kapaliyken_kurulmaz(app):
    from app.zamanlayici import zamanlayici_kur
    assert zamanlayici_kur(app.state.session_factory) is None


def test_zamanlayici_acikken_12_saatlik_is_kurar(app, monkeypatch):
    from app.config import get_settings
    from app.zamanlayici import zamanlayici_kur
    monkeypatch.setattr(get_settings(), "zamanlayici_aktif", True)
    z = zamanlayici_kur(app.state.session_factory)
    try:
        assert z is not None and not z.running  # başlatma lifespan'ın işi
        (is_,) = z.get_jobs()
        assert is_.trigger.interval.total_seconds() == 12 * 3600
        assert is_.max_instances == 1 and is_.coalesce is True
        assert str(z.timezone) == "Europe/Istanbul"
    finally:
        if z.running:
            z.shutdown(wait=False)


def test_kontrol_izin_yoksa_istek_atmaz(session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["egm"])

    class G:
        def metin(self, *a, **k):
            raise AssertionError("istek atılmamalı")

    d = aktarim.sehitlerimiz_kontrol(session, G())
    assert d.son_mesaj == "izin yok"


def test_kontrol_ilk_calisma_imlec_kurar_sonra_onaya_dusurur(session, monkeypatch):
    from app.config import get_settings
    from app.kaynaklar import sehitlerimiz as sh
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["sehitlerimiz"])
    durum = {"max": 100}

    def sahte_yeni(g, *, son_id):
        if durum["max"] > son_id:
            return [HamKayit(kaynak_kodu="sehitlerimiz", dis_kimlik=str(durum["max"]), ad="Ali", soyad="Kaya",
                             tarih=date(2026, 10, 20), hassasiyet=H.tam, yil=2026, kaynak_adi=sh.KAYNAK_ADI)], durum["max"]
        return [], son_id

    monkeypatch.setattr(sh, "yeni_kayitlar", sahte_yeni)
    monkeypatch.setattr(sh, "en_buyuk_id", lambda g: 100, raising=False)
    aktarim.sehitlerimiz_kontrol(session, object())          # ilk: imleç=100, kayıt yok
    assert session.query(Sehit).count() == 0
    assert session.get(KaynakDurumu, "sehitlerimiz_kontrol").imlec == "100"
    durum["max"] = 101
    d = aktarim.sehitlerimiz_kontrol(session, object())
    s = session.query(Sehit).one()
    assert s.durum == Durum.onay_bekliyor
    assert d.imlec == "101"


def test_kontrol_hata_durumu_yazar_ve_imlec_ilerlemez(session, monkeypatch):
    from app.config import get_settings
    from app.kaynaklar import KaynakHatasi, sehitlerimiz as sh
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["sehitlerimiz"])
    kontrol = aktarim.kaynak_durumu(session, "sehitlerimiz_kontrol")
    kontrol.imlec = "50"
    session.commit()

    def patla(g, *, son_id):
        raise KaynakHatasi("ağ yok")

    monkeypatch.setattr(sh, "yeni_kayitlar", patla)
    d = aktarim.sehitlerimiz_kontrol(session, object())
    assert d.son_durum == "hata" and "ağ yok" in d.son_mesaj
    assert d.imlec == "50"


# --- son inceleme: M3 ---

def test_zamanlayici_verilen_ayarlari_kullanir(app):
    from app.config import Settings
    from app.zamanlayici import zamanlayici_kur
    ayar = Settings(_env_file=None, zamanlayici_aktif=True)
    z = zamanlayici_kur(app.state.session_factory, ayar)  # genel ayar kapalı (autouse fikstür)
    assert z is not None and not z.running
    assert zamanlayici_kur(app.state.session_factory, Settings(_env_file=None, zamanlayici_aktif=False)) is None


def test_create_app_kendi_ayarlarini_zamanlayiciya_verir(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main
    from app.config import Settings
    alinan = []
    monkeypatch.setattr(main, "zamanlayici_kur", lambda fabrika, ayar=None: alinan.append(ayar))
    ayar = Settings(_env_file=None, database_url="sqlite://", zamanlayici_aktif=True)
    with TestClient(main.create_app(ayar)):
        pass
    assert alinan == [ayar]


def test_testlerde_zamanlayici_genel_ayari_kapali():
    from app.config import get_settings
    assert get_settings().zamanlayici_aktif is False
