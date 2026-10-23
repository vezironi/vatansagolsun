import subprocess
import sys

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


def test_bos_hash_ile_giris_kapali(client):
    r = client.post("/panel/giris", data={"kullanici": "admin", "sifre": ""})
    assert r.status_code == 401


def test_bos_hash_ile_hicbir_sifre_gecmez(client):
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


def test_giris_eski_oturum_verisini_siler(client, ayarli_sifre):
    client.get("/panel/giris")
    client.post("/panel/giris", data={"kullanici": "admin", "sifre": "test-sifre"})
    assert client.get("/panel").status_code == 200
    assert "csrf" not in client.get("/panel/giris", follow_redirects=False).text


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
