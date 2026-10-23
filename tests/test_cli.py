from datetime import date

from sqlalchemy import func, select

from app import cli
from app.dates import bugun
from app.models import Sehit


def test_ornek_kayitlar_dagilimi():
    kayitlar = cli.ornek_kayitlar(date(2026, 10, 23))
    yayinda = [k for k in kayitlar if k.durum == "yayinda"]
    assert len(yayinda) == 320 and len(kayitlar) == 325
    assert sum(k.durum == "onay_bekliyor" for k in kayitlar) == 5
    assert sum(k.tarih_hassasiyeti != "tam" for k in kayitlar) == 20
    bugunku = [k for k in yayinda if k.ay == 10 and k.gun == 23 and k.yil >= 2000]
    assert len(bugunku) >= 6
    assert all(k.kaynak_kodu == "ornek" for k in kayitlar)


def test_ornek_kayitlar_deterministik():
    a = [k.arama_metni for k in cli.ornek_kayitlar(date(2026, 10, 23))]
    b = [k.arama_metni for k in cli.ornek_kayitlar(date(2026, 10, 23))]
    assert a == b


def test_ornek_sil_yalniz_ornekleri_siler(session, sehit_ekle):
    gercek = sehit_ekle(kaynak_kodu="gercek")
    session.add_all(cli.ornek_kayitlar(bugun()))
    session.commit()
    assert cli.ornek_sil(session) == 325
    assert session.scalar(select(func.count()).select_from(Sehit)) == 1
    assert session.get(Sehit, gercek.id) is not None


def test_postgresql_icin_eminim_gerekir(monkeypatch, capsys):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "database_url", "postgresql+psycopg://x@yok/yok")
    assert cli.main(["ornek-veri"]) == 1
    assert "--eminim" in capsys.readouterr().err


def test_bos_env_degiskenleri_varsayilana_duser(monkeypatch):
    from app.config import Settings
    monkeypatch.setenv("OTURUM_HTTPS", "")
    monkeypatch.setenv("API_HARIC_KAYNAKLAR", "")
    ayar = Settings(_env_file=None)
    assert ayar.oturum_https is False and ayar.api_haric_kaynaklar == []
