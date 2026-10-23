from datetime import date

def test_istatistik(client, sehit_ekle, monkeypatch):
    monkeypatch.setattr("app.api.bugun", lambda: date(2026, 10, 23))
    sehit_ekle(sehadet_tarihi=date(2026, 3, 1)); sehit_ekle(sehadet_tarihi=date(2011, 3, 1))
    assert client.get("/api/istatistik").json() == {"toplam": 2, "bu_yil": 1, "yil": 2026}

def test_sehitler_listesi_alanlari(client, sehit_ekle):
    s = sehit_ekle(ad="Ömer", soyad="Şahin", sehadet_tarihi=date(2016, 7, 15))
    j = client.get("/api/sehitler", params={"yil": 2016}).json()
    assert j["toplam"] == 1 and j["sayfa"] == 1 and j["adet"] == 25
    k = j["kayitlar"][0]
    assert (k["ad"], k["soyad"], k["sehadet_yili"], k["gorunen_ad"]) == ("Ömer", "ŞAHİN", 2016, "Ömer ŞAHİN")
    assert k["url"] == s.url

def test_sehitler_gecersiz_parametreler(client):
    assert client.get("/api/sehitler", params={"adet": 101}).status_code == 422
    assert client.get("/api/sehitler", params={"sayfa": 0}).status_code == 422
    assert client.get("/api/sehitler", params={"yil": "dun"}).status_code == 422
    assert client.get("/api/sehitler", params={"yil": "2000-oncesi"}).status_code == 200

def test_detay_onay_bekleyen_404(client, sehit_ekle):
    s = sehit_ekle(durum="onay_bekliyor")
    assert client.get(f"/api/sehitler/{s.id}").status_code == 404

def test_bugun(client, sehit_ekle, monkeypatch):
    monkeypatch.setattr("app.api.bugun", lambda: date(2026, 10, 23))
    sehit_ekle(sehadet_tarihi=date(2011, 10, 23))
    j = client.get("/api/bugun").json()
    assert j["tarih"] == "10-23" and j["kayitlar"][0]["yil_donumu"] == 15
    assert client.get("/api/bugun", params={"tarih": "13-40"}).status_code == 422
    assert client.get("/api/bugun", params={"tarih": "02-29"}).status_code == 200

def test_detay_alanlari_ve_yok_404(client, sehit_ekle):
    s = sehit_ekle(kurum="Kara Kuvvetleri")
    j = client.get(f"/api/sehitler/{s.id}").json()
    assert j["kurum"] == "Kara Kuvvetleri" and j["kaynaklar"] == []
    assert client.get("/api/sehitler/99999").status_code == 404

def test_istek_siniri_429(session):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.db import get_session
    from app.main import create_app
    a = create_app(Settings(istek_siniri="2/minute", database_url="sqlite://"))
    a.dependency_overrides[get_session] = lambda: session
    c = TestClient(a)
    kodlar = [c.get("/api/istatistik").status_code for _ in range(3)]
    assert kodlar == [200, 200, 429]


def test_cok_buyuk_id_ve_sayfa_422(client):
    assert client.get("/api/sehitler/99999999999999999999").status_code == 422
    assert client.get("/api/sehitler/2147483648").status_code == 422
    assert client.get("/api/sehitler", params={"sayfa": "99999999999999999999"}).status_code == 422
    assert client.get("/api/sehitler", params={"sayfa": 1_000_001}).status_code == 422
    assert client.get("/api/sehitler/2147483647").status_code == 404
