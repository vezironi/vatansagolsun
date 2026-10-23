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
    deger = satir.split("=", 1)[1]
    # .env/compose için tek tırnak içinde basılır ('$' değişken sayılmasın)
    assert deger.startswith("'") and deger.endswith("'")
    assert sifre_dogru("gizli-sifre", deger[1:-1])


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


def test_birlestir_rotasi(panel_client, csrf, sehit_ekle, session):
    hedef = sehit_ekle(memleket=None); fazla = sehit_ekle(memleket="Van", durum="onay_bekliyor")
    r = panel_client.post(f"/panel/sehit/{fazla.id}/birlestir",
                          data={"csrf": csrf(panel_client), "hedef_id": hedef.id}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/panel/sehit/{hedef.id}"
    session.refresh(hedef)
    assert hedef.memleket == "Van"
    assert panel_client.post(f"/panel/sehit/{hedef.id}/birlestir",
                             data={"csrf": csrf(panel_client), "hedef_id": hedef.id}).status_code == 400


def test_birlestir_gecersiz_girdiler(panel_client, csrf, sehit_ekle):
    s = sehit_ekle()
    url = f"/panel/sehit/{s.id}/birlestir"
    for hedef in ("", "abc", "١٢", "99999", "-1"):
        r = panel_client.post(url, data={"csrf": csrf(panel_client), "hedef_id": hedef})
        assert r.status_code == 400 and "hedef" in r.text.lower()
    assert panel_client.post(url, data={"csrf": csrf(panel_client)}).status_code == 400
    assert panel_client.post("/panel/sehit/99999/birlestir",
                             data={"csrf": csrf(panel_client), "hedef_id": s.id}).status_code == 404
    assert panel_client.post(url, data={"csrf": "x", "hedef_id": s.id}).status_code == 403


def test_birlestir_bildirimi_hedefe_tasir(panel_client, csrf, sehit_ekle, session):
    from app import repo
    from app.models import Bildirim

    hedef = sehit_ekle(); fazla = sehit_ekle()
    repo.bildirim_ekle(session, mesaj="x", iletisim=None, sehit_id=fazla.id)
    panel_client.post(f"/panel/sehit/{fazla.id}/birlestir",
                      data={"csrf": csrf(panel_client), "hedef_id": hedef.id})
    assert session.query(Bildirim).one().sehit_id == hedef.id


def test_bildirimler(panel_client, csrf, client, session):
    from app.models import Bildirim
    client.post("/bildir", data={"mesaj": "İsim yanlış yazılmış"})
    assert "İsim yanlış yazılmış" in panel_client.get("/panel/bildirimler").text
    b = session.query(Bildirim).one()
    panel_client.post(f"/panel/bildirimler/{b.id}/kapat", data={"csrf": csrf(panel_client)})
    assert "İsim yanlış yazılmış" not in panel_client.get("/panel/bildirimler").text


def test_bildirimler_kacis_ve_koruma(panel_client, csrf, client, session, sehit_ekle):
    from app import repo
    s = sehit_ekle()
    repo.bildirim_ekle(session, mesaj="<script>alert(1)</script>", iletisim="<b>x</b>", sehit_id=s.id)
    h = panel_client.get("/panel/bildirimler").text
    assert "<script>alert(1)</script>" not in h and "&lt;script&gt;" in h
    assert "<b>x</b>" not in h and f"/panel/sehit/{s.id}" in h
    assert "/panel/bildirimler" in panel_client.get("/panel").text
    assert panel_client.post("/panel/bildirimler/99999/kapat",
                             data={"csrf": csrf(panel_client)}).status_code == 404
    assert panel_client.post("/panel/bildirimler/1/kapat", data={"csrf": "x"}).status_code == 403
    client.cookies.clear()
    r = client.get("/panel/bildirimler", follow_redirects=False)
    assert r.status_code == 303


def test_panel_cok_buyuk_id_ve_sayfa_500_vermez(panel_client, csrf):
    token = csrf(panel_client)
    buyuk = "99999999999999999999"
    assert panel_client.get(f"/panel/sehit/{buyuk}").status_code == 404
    assert panel_client.post(f"/panel/sehit/{buyuk}/onayla", data={"csrf": token}).status_code == 404
    assert panel_client.post(f"/panel/sehit/{buyuk}/reddet", data={"csrf": token}).status_code == 404
    assert panel_client.post(f"/panel/bildirimler/{buyuk}/kapat", data={"csrf": token}).status_code == 404
    assert panel_client.get("/panel/sehit/2147483648").status_code == 404
    assert panel_client.get("/panel/yayinda", params={"sayfa": buyuk}).status_code == 200


def test_giris_formu_zayif_secret_dongu_yok(panel_client, app, monkeypatch):
    assert panel_client.get("/panel/giris", follow_redirects=False).status_code == 303
    monkeypatch.setattr(app.state.settings, "secret_key", "kisa")
    assert panel_client.get("/panel/giris", follow_redirects=False).status_code == 200


def test_uzun_ad_400(panel_client, csrf):
    r = panel_client.post("/panel/sehit/yeni", data={
        "csrf": csrf(panel_client), "ad": "a" * 201, "tarih_hassasiyeti": "bilinmiyor",
    })
    assert r.status_code == 400


def test_uzun_slug_sigar(session):
    from app.models import Sehit
    s = Sehit(ad="a" * 200, soyad="b" * 200, lakap="c" * 200, kaynak_kodu="t",
              tarih_hassasiyeti="bilinmiyor")
    s.alanlari_yenile()
    assert len(s.slug) <= 300


def test_bildirim_saati_istanbul(panel_client, session):
    from datetime import datetime
    from app.models import Bildirim
    session.add(Bildirim(mesaj="x", tarih=datetime(2026, 1, 1, 21, 30)))  # naive = UTC
    session.commit()
    assert "02.01.2026 00:30" in panel_client.get("/panel/bildirimler").text


def test_panel_duzenlemesi_elle_duzenlendi_isaretler(panel_client, csrf, sehit_ekle, session):
    from app.models import Sehit

    s = sehit_ekle(durum="onay_bekliyor")
    assert s.elle_duzenlendi is False
    panel_client.post(f"/panel/sehit/{s.id}", data=_form(csrf(panel_client)), follow_redirects=False)
    session.refresh(s)
    assert s.elle_duzenlendi is True
    panel_client.post("/panel/sehit/yeni", data=_form(csrf(panel_client), kaynak_kodu=""), follow_redirects=False)
    yeni = session.query(Sehit).order_by(Sehit.id.desc()).first()
    assert yeni.elle_duzenlendi is True


def test_kaydet_ve_onayla_da_isaretler(panel_client, csrf, sehit_ekle, session):
    s = sehit_ekle(durum="onay_bekliyor")
    panel_client.post(f"/panel/sehit/{s.id}", data=_form(csrf(panel_client), islem="onayla"), follow_redirects=False)
    session.refresh(s)
    assert s.elle_duzenlendi is True


# --- Task 6: toplayıcı durum sayfası ---

def _toplayici_satirlari(session):
    from datetime import datetime, timezone
    from app.models import KaynakDurumu
    session.add_all([
        KaynakDurumu(kaynak_kodu="egm_toplayici", son_durum="basarili", eklenen=3, birlesen=1, atlanan=2, hatali=0,
                     son_calisma=datetime(2026, 10, 23, 9, 0, tzinfo=timezone.utc)),
        KaynakDurumu(kaynak_kodu="hurriyet", son_durum="hata", son_mesaj="API anahtarı yok",
                     eklenen=0, birlesen=0, atlanan=0, hatali=0,
                     son_calisma=datetime(2026, 10, 23, 9, 0, tzinfo=timezone.utc)),
    ])
    session.commit()


def test_toplayici_sayfasi_girissiz_yonlendirir(client):
    r = client.get("/panel/toplayici", follow_redirects=False)
    assert r.status_code == 303
    r = client.post("/panel/toplayici/simdi", data={"csrf": "x"}, follow_redirects=False)
    assert r.status_code == 303


def test_toplayici_sayfasi_satirlari_gosterir(panel_client, session):
    _toplayici_satirlari(session)
    r = panel_client.get("/panel/toplayici")
    assert r.status_code == 200
    assert "egm" in r.text and "hurriyet" in r.text
    assert "API anahtarı yok" in r.text
    assert "12:00" in r.text  # 09:00 UTC = 12:00 İstanbul
    assert "Bugünkü analiz" in r.text


def test_toplayici_sayfasi_anahtari_asla_gostermez(panel_client, app, monkeypatch):
    monkeypatch.setattr(app.state.settings, "anthropic_api_key", "sk-ant-gizli-deger-123")
    r = panel_client.get("/panel/toplayici")
    assert "yapılandırıldı" in r.text
    assert "sk-ant" not in r.text and "gizli-deger" not in r.text
    for alan in ("anthropic_api_key", "openai_api_key", "gemini_api_key"):
        monkeypatch.setattr(app.state.settings, alan, "")
    for ad in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(ad, raising=False)
    assert "anahtar yok" in panel_client.get("/panel/toplayici").text


def test_toplayici_sayaci_gosterilir(panel_client, session, app):
    from app.dates import bugun
    from app.models import KaynakDurumu
    session.add(KaynakDurumu(kaynak_kodu="analiz_sayaci", imlec=f"{bugun().isoformat()}:7"))
    session.commit()
    assert f"7 / {app.state.settings.gunluk_analiz_siniri}" in panel_client.get("/panel/toplayici").text


def test_simdi_calistir_zamanlayicisiz_409(panel_client, csrf):
    r = panel_client.post("/panel/toplayici/simdi", data={"csrf": csrf(panel_client)})
    assert r.status_code == 409
    assert "ZAMANLAYICI_AKTIF" in r.text and "python -m app.cli topla" in r.text


def test_simdi_calistir_csrf_yoksa_403(panel_client):
    assert panel_client.post("/panel/toplayici/simdi", data={"csrf": "yanlis"}).status_code == 403


def test_simdi_calistir_isi_tetikler(panel_client, csrf, app):
    class Is:
        next_run_time = None

        def modify(self, **k):
            self.k = k

    class Z:
        timezone = __import__("zoneinfo").ZoneInfo("Europe/Istanbul")
        is_ = Is()

        def get_job(self, id):
            assert id == "toplayici"
            return self.is_

    app.state.zamanlayici = Z()
    r = panel_client.post("/panel/toplayici/simdi", data={"csrf": csrf(panel_client)}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/panel/toplayici")
    assert Z.is_.k["next_run_time"].tzinfo is not None
    assert "Toplayıcı başlatıldı" in panel_client.get(r.headers["location"]).text
    assert "Toplayıcı başlatıldı" not in panel_client.get("/panel/toplayici").text


def test_ana_panel_toplayici_hatasi_uyarir(panel_client, session):
    assert "Toplayıcıda hata var" not in panel_client.get("/panel").text
    from app.models import KaynakDurumu
    session.add(KaynakDurumu(kaynak_kodu="sabah", son_durum="hata", son_mesaj="x"))
    session.commit()
    assert "Toplayıcıda hata var" in panel_client.get("/panel").text


def test_ana_panel_alakasiz_hatada_uyarmaz(panel_client, session):
    from app.models import KaynakDurumu
    session.add(KaynakDurumu(kaynak_kodu="kahramanlar", son_durum="hata", son_mesaj="x"))
    session.commit()
    assert "Toplayıcıda hata var" not in panel_client.get("/panel").text


def _kilit_tut(session):
    from datetime import datetime, timezone
    from app.models import KaynakDurumu
    from app.toplayici import KILIT_KODU
    session.add(KaynakDurumu(kaynak_kodu=KILIT_KODU, imlec=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             eklenen=0, birlesen=0, atlanan=0, hatali=0))
    session.commit()


def test_simdi_calistir_zaten_calisiyorsa_tetiklemez(panel_client, csrf, app, session):
    class Is:
        next_run_time = None
        k = None

        def modify(self, **k):
            self.k = k

    class Z:
        timezone = __import__("zoneinfo").ZoneInfo("Europe/Istanbul")
        is_ = Is()

        def get_job(self, id):
            return self.is_

    app.state.zamanlayici = Z()
    _kilit_tut(session)
    r = panel_client.post("/panel/toplayici/simdi", data={"csrf": csrf(panel_client)}, follow_redirects=False)
    assert r.status_code == 303 and Z.is_.k is None
    sayfa = panel_client.get(r.headers["location"]).text
    assert "Toplayıcı zaten çalışıyor; bittiğinde tekrar deneyin" in sayfa and "Toplayıcı başlatıldı" not in sayfa
    assert "toplayici_kilidi" not in sayfa


def test_toplayici_sayaclari_toplam_olarak_etiketlenir(panel_client):
    sayfa = panel_client.get("/panel/toplayici").text
    for ad in ("Eklenen", "Birleşen", "Atlanan", "Hatalı"):
        assert f"{ad} (toplam)" in sayfa


def test_izni_kaldirilmis_kaynagin_eski_hatasi_uyarmaz(panel_client, session, app, monkeypatch):
    from app.models import KaynakDurumu
    session.add_all([KaynakDurumu(kaynak_kodu="aa", son_durum="hata", son_mesaj="eski aa hatası"),
                     KaynakDurumu(kaynak_kodu="egm_toplayici", son_durum="hata", son_mesaj="eski egm hatası")])
    session.commit()
    monkeypatch.setattr(app.state.settings, "kaynak_izinleri", ["sg", "hurriyet"])
    assert "Toplayıcıda hata var" not in panel_client.get("/panel").text
    sayfa = panel_client.get("/panel/toplayici").text
    assert "eski aa hatası" not in sayfa and "eski egm hatası" not in sayfa and "hurriyet" in sayfa
    monkeypatch.setattr(app.state.settings, "kaynak_izinleri", ["egm"])  # egm izinliyse egm_toplayici sayılır
    assert "Toplayıcıda hata var" in panel_client.get("/panel").text
    assert "eski egm hatası" in panel_client.get("/panel/toplayici").text


def test_toplayici_analiz_saglayicilari_tablosu(panel_client, app, session, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from app.models import KaynakDurumu

    ayar = app.state.settings
    for ad in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(ad, raising=False)
    monkeypatch.setattr(ayar, "analiz_sirasi", ["openai", "gemini", "claude"])
    monkeypatch.setattr(ayar, "openai_api_key", "sk-openai-gizli-111")
    monkeypatch.setattr(ayar, "gemini_api_key", "")
    monkeypatch.setattr(ayar, "anthropic_api_key", "sk-ant-gizli-222")
    an = datetime.now(timezone.utc) - timedelta(hours=1)
    session.add(KaynakDurumu(kaynak_kodu="analiz_openai", tamamlandi=False, eklenen=0, birlesen=0, atlanan=0,
                             hatali=0, son_calisma=an, son_durum="tukendi", imlec=an.isoformat()))
    session.commit()
    t = panel_client.get("/panel/toplayici").text
    assert "Analiz sağlayıcıları" in t
    assert ayar.openai_modeli in t and ayar.gemini_modeli in t and ayar.analiz_modeli in t
    assert t.index("openai") < t.index("gemini") < t.index("claude")
    bitis = (an + timedelta(hours=24)).astimezone(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")
    assert f"tükendi — {bitis}'e kadar" in t
    assert "kullanılabilir" in t
    assert "gizli" not in t


def test_toplayici_bilinmeyen_saglayici_satiri(panel_client, app, monkeypatch):
    monkeypatch.setattr(app.state.settings, "analiz_sirasi", ["mistral"])
    t = panel_client.get("/panel/toplayici").text
    assert "mistral" in t and "bilinmeyen sağlayıcı" in t
