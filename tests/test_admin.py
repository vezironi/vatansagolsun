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


# --- Task 8: onay iş akışı ---
from datetime import date  # noqa: E402

from app.models import Kaynak  # noqa: E402


def _form(csrf_degeri, **ek):
    form = {"csrf": csrf_degeri, "ad": "mehmet", "soyad": "kaya", "kategori": "polis",
            "tarih_hassasiyeti": "tam", "sehadet_tarihi": "2026-10-20", "kaynak_kodu": "haber"}
    form.update(ek)
    return form


def test_bekleyenler_listesi(panel_client, sehit_ekle):
    sehit_ekle(ad="Bekleyen", soyad="Kişi", durum="onay_bekliyor", resmi_teyit=False, isimsiz=False)
    sehit_ekle(ad="Yayinda", soyad="Kişi")
    h = panel_client.get("/panel").text
    assert "Bekleyen KİŞİ" in h and "Resmî teyit yok" in h and "Yayinda KİŞİ" not in h


def test_isimsiz_rozeti(panel_client, sehit_ekle):
    sehit_ekle(ad="Adsiz", soyad=None, lakap="Kahraman", durum="onay_bekliyor", isimsiz=True)
    assert "İsimsiz" in panel_client.get("/panel").text


def test_kaynak_metni_kisaltilir_ve_kacirilir(panel_client, sehit_ekle, session):
    s = sehit_ekle(durum="onay_bekliyor")
    session.add_all([
        Kaynak(sehit=s, kaynak_adi="Haber", url="https://ornek.com/x",
               metin="<script>alert(1)</script>" + "a" * 400),
        Kaynak(sehit=s, kaynak_adi="Kotu", url="javascript:alert(2)", metin="m"),
    ])
    session.commit()
    h = panel_client.get("/panel").text
    assert "<script>alert(1)" not in h and "&lt;script&gt;" in h
    assert 'href="https://ornek.com/x"' in h
    assert 'href="javascript' not in h
    onek = len("<script>alert(1)</script>")  # ilk 300 karakterin içinde
    assert "a" * (300 - onek) in h and "a" * (300 - onek + 1) not in h


def test_onayla_yayina_alir(panel_client, csrf, sehit_ekle, client):
    s = sehit_ekle(durum="onay_bekliyor", sehadet_tarihi=date(2016, 1, 1))
    panel_client.post(f"/panel/sehit/{s.id}/onayla", data={"csrf": csrf(panel_client)})
    assert client.get(f"/api/sehitler/{s.id}").status_code == 200


def test_reddet_ve_kaldir(panel_client, csrf, sehit_ekle, client):
    a = sehit_ekle(durum="onay_bekliyor")
    b = sehit_ekle()
    panel_client.post(f"/panel/sehit/{a.id}/reddet", data={"csrf": csrf(panel_client)})
    panel_client.post(f"/panel/sehit/{b.id}/kaldir", data={"csrf": csrf(panel_client)})
    assert client.get(f"/api/sehitler/{a.id}").status_code == 404
    assert client.get(f"/api/sehitler/{b.id}").status_code == 404


@pytest.mark.parametrize("eylem", ["onayla", "reddet", "kaldir"])
def test_islem_yonlendirir_csrf_ve_404(panel_client, csrf, sehit_ekle, eylem):
    s = sehit_ekle(durum="onay_bekliyor")
    r = panel_client.post(f"/panel/sehit/{s.id}/{eylem}", data={"csrf": csrf(panel_client)},
                          follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel"
    assert panel_client.post(f"/panel/sehit/{s.id}/{eylem}", data={"csrf": "x"}).status_code == 403
    assert panel_client.post(f"/panel/sehit/99999/{eylem}",
                             data={"csrf": csrf(panel_client)}).status_code == 404


def test_girissiz_panel_rotalari(client, sehit_ekle):
    s = sehit_ekle(durum="onay_bekliyor")
    for yol in ("/panel/yayinda", "/panel/sehit/yeni", f"/panel/sehit/{s.id}"):
        assert client.get(yol, follow_redirects=False).status_code == 303
    r = client.post(f"/panel/sehit/{s.id}/onayla", data={"csrf": "x"}, follow_redirects=False)
    assert r.status_code == 303


def test_duzenle_ve_hata(panel_client, csrf, sehit_ekle, session):
    s = sehit_ekle(durum="onay_bekliyor")
    form = _form(csrf(panel_client))
    r = panel_client.post(f"/panel/sehit/{s.id}", data=form, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/panel/sehit/{s.id}"
    session.refresh(s)
    assert (s.ad, s.soyad, s.kategori, s.gun) == ("Mehmet", "KAYA", "polis", 20)
    form["sehadet_tarihi"] = ""
    r = panel_client.post(f"/panel/sehit/{s.id}", data=form)
    assert r.status_code == 400 and "zorunlu" in r.text


def test_hatali_girdiler_400(panel_client, csrf, sehit_ekle):
    s = sehit_ekle(durum="onay_bekliyor")
    for ek in ({"sehadet_tarihi": "20-10-2026"}, {"yil": "abc"}, {"dogum_yili": "²"},
               {"kategori": "yok"}, {"ad": ""}):
        r = panel_client.post(f"/panel/sehit/{s.id}", data=_form(csrf(panel_client), **ek))
        assert r.status_code == 400, ek


def test_duzenle_formu_ve_404(panel_client, sehit_ekle):
    s = sehit_ekle(durum="onay_bekliyor")
    h = panel_client.get(f"/panel/sehit/{s.id}").text
    assert 'name="ad"' in h and "Kaydet ve onayla" in h
    assert panel_client.get("/panel/sehit/99999").status_code == 404
    assert panel_client.get("/panel/sehit/yeni").status_code == 200


def test_kaydet_ve_onayla(panel_client, csrf, sehit_ekle, client):
    s = sehit_ekle(durum="onay_bekliyor")
    form = _form(csrf(panel_client), islem="onayla", resmi_teyit="on")
    r = panel_client.post(f"/panel/sehit/{s.id}", data=form, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel"
    assert client.get(f"/api/sehitler/{s.id}").json()["ad"] == "Mehmet"


def test_yeni_kayit(panel_client, csrf, session):
    from app.models import Durum, Sehit

    form = _form(csrf(panel_client), kaynak_kodu="")
    r = panel_client.post("/panel/sehit/yeni", data=form, follow_redirects=False)
    assert r.status_code == 303
    s = session.query(Sehit).one()
    assert s.durum == Durum.onay_bekliyor and s.kaynak_kodu == "panel"
    assert r.headers["location"] == f"/panel/sehit/{s.id}"
    assert panel_client.post("/panel/sehit/yeni",
                             data=_form(csrf(panel_client), ad="")).status_code == 400


def test_yayindakiler_arama(panel_client, sehit_ekle):
    sehit_ekle(ad="Şahin", soyad="Demir")
    sehit_ekle(ad="Veli", soyad="Kaya")
    sehit_ekle(ad="Bekleyen", soyad="Demir", durum="onay_bekliyor")
    h = panel_client.get("/panel/yayinda", params={"q": "sahin"}).text
    assert "Şahin DEMİR" in h and "Veli" not in h and "Bekleyen" not in h
