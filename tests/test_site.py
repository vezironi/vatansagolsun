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


def test_sehit_sayfasi_ve_yonlendirme(client, sehit_ekle):
    s = sehit_ekle(ad="Hasan", soyad="Tekin")
    r = client.get(s.url)
    assert r.status_code == 200 and "<title>Hasan TEKİN — vatansagolsun</title>" in r.text
    r = client.get(f"/sehit/yanlis-{s.id}", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == s.url


def test_sehit_sayfasi_onay_bekleyen_404(client, sehit_ekle):
    s = sehit_ekle(durum="onay_bekliyor")
    assert client.get(f"/sehit/x-{s.id}").status_code == 404
    assert client.get("/sehit/abc").status_code == 404


def test_sehit_sayfasi_kotu_id_404(client):
    assert client.get("/sehit/x-" + "9" * 40).status_code == 404
    assert client.get("/sehit/x-١٢٣").status_code == 404


def test_sehit_kaynak_linkleri_sadece_http(client, sehit_ekle, session):
    from app.models import Kaynak
    s = sehit_ekle()
    session.add(Kaynak(sehit_id=s.id, url="javascript:alert(1)", baslik="Kötü", kaynak_adi="x"))
    session.add(Kaynak(sehit_id=s.id, url="https://ornek.gov.tr/a", baslik="İyi", kaynak_adi="y"))
    session.commit()
    h = client.get(s.url).text
    assert 'href="https://ornek.gov.tr/a"' in h and "javascript:" not in h


def test_yil_donumleri_sayfasi(client, sehit_ekle):
    sehit_ekle(ad="Cem", soyad="Uçar", sehadet_tarihi=date(2016, 7, 15))
    assert "Cem UÇAR" in client.get("/yil-donumleri", params={"ay": 7, "gun": 15}).text
    assert client.get("/yil-donumleri", params={"ay": 13, "gun": 99}).status_code == 200
    assert client.get("/yil-donumleri", params={"ay": "9" * 50, "gun": "١"}).status_code == 200


def test_hakkinda(client):
    h = client.get("/hakkinda").text
    assert "sehitlerimiz.org.tr — Türkiye Şehit Arşivi" in h and "resmî toplam değildir" in h


def test_bildir(client, session):
    from app.models import Bildirim
    r = client.post("/bildir", data={"mesaj": "Tarih yanlış", "iletisim": ""})
    assert "Teşekkürler" in r.text
    assert session.query(Bildirim).one().mesaj == "Tarih yanlış"
    assert "Teşekkürler" not in client.post("/bildir", data={"mesaj": "  "}).text


def test_bildir_uzun_ve_sehit_id(client, session, sehit_ekle):
    from app.models import Bildirim
    assert "Teşekkürler" not in client.post("/bildir", data={"mesaj": "a" * 2001}).text
    assert session.query(Bildirim).count() == 0
    s = sehit_ekle()
    assert client.get("/bildir", params={"sehit": "9" * 40}).status_code == 200
    client.post("/bildir", data={"mesaj": "x", "sehit": str(s.id)})
    client.post("/bildir", data={"mesaj": "y", "sehit": "abc"})
    assert [b.sehit_id for b in session.query(Bildirim).order_by(Bildirim.id)] == [s.id, None]
