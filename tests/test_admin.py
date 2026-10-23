import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

from app.admin import sifre_dogru, sifre_hashle


def test_panel_girissiz_yonlendirir(client):
    r = client.get("/panel", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel/giris"


def test_yanlis_sifre(client, ayarli_sifre):
    r = client.post("/panel/giris", data={"kullanici": "admin", "sifre": "yanlis"})
    assert r.status_code == 401 and "hatalı" in r.text


def test_yanlis_kullanici(client, ayarli_sifre):
    r = client.post("/panel/giris", data={"kullanici": "baska", "sifre": "test-sifre"})
    assert r.status_code == 401 and "hatalı" in r.text


def test_dogru_giris_ve_cikis(panel_client, csrf):
    assert panel_client.get("/panel").status_code == 200
    panel_client.post("/panel/cikis", data={"csrf": csrf(panel_client)})
    assert panel_client.get("/panel", follow_redirects=False).status_code == 303


def test_csrf_yoksa_403(panel_client):
    assert panel_client.post("/panel/cikis", data={"csrf": "sahte"}).status_code == 403


def test_csrf_alani_hic_yoksa_403(panel_client):
    assert panel_client.post("/panel/cikis").status_code == 403


def test_csrf_403_oturumu_kapatmaz(panel_client):
    panel_client.post("/panel/cikis", data={"csrf": "sahte"})
    assert panel_client.get("/panel").status_code == 200


def test_girissiz_cikis_giris_sayfasina_yonlendirir(client):
    r = client.post("/panel/cikis", data={"csrf": "x"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel/giris"


def test_bos_hash_ile_giris_kapali(client, monkeypatch, app):
    monkeypatch.setattr(app.state.settings, "admin_sifre_hash", "")
    r = client.post("/panel/giris", data={"kullanici": "admin", "sifre": ""})
    assert r.status_code == 401


def test_bos_hash_ile_hicbir_sifre_gecmez(client, monkeypatch, app):
    monkeypatch.setattr(app.state.settings, "admin_sifre_hash", "")
    r = client.post("/panel/giris", data={"kullanici": "admin", "sifre": "test-sifre"})
    assert r.status_code == 401
    assert client.get("/panel", follow_redirects=False).status_code == 303


def test_basarili_giris_panele_yonlendirir(client, ayarli_sifre):
    r = client.post(
        "/panel/giris",
        data={"kullanici": "admin", "sifre": "test-sifre"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == "/panel"


def test_giris_oturumu_yeniler(panel_client, csrf):
    eski = csrf(panel_client)
    panel_client.post(
        "/panel/giris", data={"kullanici": "admin", "sifre": "test-sifre"}, follow_redirects=False
    )
    yeni = csrf(panel_client)
    assert yeni != eski
    assert panel_client.post("/panel/cikis", data={"csrf": eski}).status_code == 403


def test_giris_sayfasi_giris_yapmisi_panele_gonderir(panel_client):
    r = panel_client.get("/panel/giris", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel"


def test_kaba_kuvvet_429(client, ayarli_sifre):
    kodlar = [
        client.post("/panel/giris", data={"kullanici": "admin", "sifre": "x"}).status_code
        for _ in range(11)
    ]
    assert kodlar[:10] == [401] * 10 and kodlar[10] == 429


def test_hash_ve_dogrulama():
    h = sifre_hashle("gizli")
    assert h != "gizli" and sifre_dogru("gizli", h)
    assert not sifre_dogru("baska", h)
    assert not sifre_dogru("gizli", "")
    assert not sifre_dogru("gizli", "bozuk-hash")
    assert not sifre_dogru("a" * 100, h)


def test_cli_sifre_olustur(monkeypatch, capsys):
    from app import cli

    cevaplar = iter(["gizli-sifre", "gizli-sifre"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_: next(cevaplar))
    assert cli.main(["sifre-olustur"]) == 0
    cikti = capsys.readouterr().out
    satir = next(s for s in cikti.splitlines() if s.startswith("ADMIN_SIFRE_HASH="))
    assert sifre_dogru("gizli-sifre", satir.split("=", 1)[1])


def test_cli_sifre_uyusmazligi(monkeypatch, capsys):
    from app import cli

    cevaplar = iter(["bir", "iki"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_: next(cevaplar))
    assert cli.main(["sifre-olustur"]) == 1
    assert "ADMIN_SIFRE_HASH" not in capsys.readouterr().out


def test_cli_modulu_calisir():
    r = subprocess.run(
        [sys.executable, "-m", "app.cli", "bilinmeyen"], capture_output=True, text=True
    )
    assert r.returncode != 0


@pytest.fixture
def zayif_app(session):
    from app.config import Settings
    from app.db import get_session
    from app.main import create_app

    ayarlar = Settings(
        _env_file=None,
        secret_key="degistir",
        admin_kullanici="admin",
        admin_sifre_hash=sifre_hashle("test-sifre"),
    )
    uygulama = create_app(ayarlar)
    uygulama.dependency_overrides[get_session] = lambda: session
    return uygulama


def test_varsayilan_secret_ile_sahte_cerez_reddedilir(zayif_app):
    import base64
    import json

    veri = base64.b64encode(json.dumps({"kullanici": "admin"}).encode())
    sahte = TimestampSigner("degistir").sign(veri).decode()
    istemci = TestClient(zayif_app)
    istemci.cookies.set("session", sahte)
    r = istemci.get("/panel", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel/giris"


def test_zayif_secret_ile_dogru_sifre_bile_reddedilir(zayif_app):
    istemci = TestClient(zayif_app)
    r = istemci.post("/panel/giris", data={"kullanici": "admin", "sifre": "test-sifre"})
    assert r.status_code == 401 and "SECRET_KEY" in r.text
    assert istemci.get("/panel", follow_redirects=False).status_code == 303


def test_kisa_secret_zayif_sayilir():
    from app.admin import secret_zayif_mi
    from app.config import Settings

    assert secret_zayif_mi(Settings(_env_file=None, secret_key="a" * 31))
    assert not secret_zayif_mi(Settings(_env_file=None, secret_key="a" * 32))


def test_zayif_secret_baslangicta_uyarir(caplog):
    from app.config import Settings
    from app.main import create_app

    with caplog.at_level("WARNING"):
        create_app(Settings(_env_file=None, secret_key="degistir"))
    assert "SECRET_KEY" in caplog.text
