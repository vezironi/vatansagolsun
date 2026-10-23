from datetime import date

def _sabit_gun(monkeypatch):
    monkeypatch.setattr("app.site.bugun", lambda: date(2026, 10, 23))

def test_ana_sayfa_bugun_kutusu_ve_sayac(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    sehit_ekle(ad="Hasan", soyad="Tekin", sehadet_tarihi=date(2011, 10, 23))
    h = client.get("/").text
    assert "Bugün, 23 Ekim" in h and "Hasan TEKİN" in h and "15. yıl dönümü" in h
    assert 'data-hedef="1"' in h  # toplam sayaç
    assert h.index("Bugün, 23 Ekim") < h.index("Toplam Şehit")

def test_bugun_kutusu_bossa_gizli(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    sehit_ekle(sehadet_tarihi=date(2011, 5, 5))
    assert "Bugün, 23 Ekim" not in client.get("/").text

def test_tablo_varsayilan_bu_yil_ve_arama(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    sehit_ekle(ad="Ali", soyad="Kaya", sehadet_tarihi=date(2026, 2, 2))
    sehit_ekle(ad="Veli", soyad="Şahin", sehadet_tarihi=date(2016, 2, 2))
    h = client.get("/").text
    assert "Ali KAYA" in h and "Veli ŞAHİN" not in h
    h = client.get("/", params={"yil": "tumu", "q": "sahin"}).text
    assert "Veli ŞAHİN" in h and "Ali KAYA" not in h

def test_eski_kayitlar_ciziliyor(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    sehit_ekle(ad="İsmail", soyad=None, lakap="Aşçıoğullarından", tarih_hassasiyeti="bilinmiyor", sehadet_tarihi=None)
    sehit_ekle(ad="Mehmet", soyad=None, tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=1915)
    r = client.get("/", params={"yil": "2000-oncesi"})
    assert r.status_code == 200
    assert "İsmail — Aşçıoğullarından" in r.text and "1915" in r.text

def test_onay_bekleyen_sayfada_yok(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    sehit_ekle(ad="Gizli", soyad="Kayit", sehadet_tarihi=date(2026, 10, 23), durum="onay_bekliyor")
    assert "Gizli" not in client.get("/").text

def test_gecersiz_parametre_varsayilana_duser(client, monkeypatch):
    _sabit_gun(monkeypatch)
    assert client.get("/", params={"yil": "abc", "sayfa": "-3"}).status_code == 200

def test_ozel_kaydirma_cubugu_css(client):
    css = client.get("/static/site.css").text
    assert "::-webkit-scrollbar-thumb:hover" in css and "scrollbar-color" in css

def test_sayfalama_yil_ve_aramayi_korur(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    for i in range(30):
        sehit_ekle(ad=f"Kisi{i}", soyad="Aksoy", sehadet_tarihi=date(2026, 1, 1))
    h = client.get("/", params={"q": "aksoy", "sayfa": "2"}).text
    assert 'class="pager"' in h and "yil=2026" in h and "q=aksoy" in h

def test_asiri_buyuk_sayfa_ve_ascii_disi_rakam_500_vermez(client, monkeypatch):
    _sabit_gun(monkeypatch)
    assert client.get("/", params={"sayfa": "9" * 30}).status_code == 200
    assert client.get("/", params={"sayfa": "999999"}).status_code == 200
    assert client.get("/", params={"sayfa": "²"}).status_code == 200
    assert client.get("/", params={"yil": "²"}).status_code == 200
    assert client.get("/", params={"yil": "9" * 30}).status_code == 200
