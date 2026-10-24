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


def test_bildir_hiz_siniri(client):
    kodlar = [client.post("/bildir", data={"mesaj": "x"}).status_code for _ in range(6)]
    assert kodlar[:5] == [200] * 5 and kodlar[5] == 429


def test_hakkinda_iletisim(client):
    assert "İletişim" in client.get("/hakkinda").text


def test_anma_bandi_navbarin_ustunde(client):
    h = client.get("/hakkinda").text
    assert 'class="bant"' in h and "Şehitlerimizi rahmet, minnet ve saygıyla anıyoruz" in h
    assert h.index('class="bant"') < h.index("<header>")
    assert h.count('class="ay-yildiz') == 2 and 'class="ay-yildiz ters"' in h


def test_anma_bandi_panelde_de_var(client):
    h = client.get("/panel/giris").text
    assert h.index('class="bant"') < h.index("<header>")


def test_bannerlar_sayfasi_ve_menu(client):
    h = client.get("/").text
    assert '<a href="/bannerlar">Bannerlar</a>' in h
    r = client.get("/bannerlar")
    assert r.status_code == 200
    t = r.text
    for ad in ("Güncel bant", "Güncel kart (300×250)", "Kırmızı anma bandı", "Koyu anma bandı", "Anma kartı (300×250)"):
        assert ad in t, ad
    assert '<iframe src="/gomulu/guncel?bicim=bant&renk=kirmizi"' in t  # önizleme
    for ad in ("HTML", "React", "Vue", "Svelte", "Angular", "Tek satır script"):
        assert f">{ad}</button>" in t, ad
    assert "&lt;div role=&#34;note&#34;" in t or "&lt;div role=&quot;note&quot;" in t  # kod kaçışlı gösterilir
    assert "http://testserver/bant.js" in t


def test_bant_js_servis(client):
    r = client.get("/bant.js")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/javascript")
    assert "Şehitlerimizi rahmet" in r.text


def _sabit_gun_gomulu(monkeypatch):
    monkeypatch.setattr("app.site.bugun", lambda: date(2026, 10, 23))


def test_gomulu_guncel_anma_modu(client, monkeypatch):
    _sabit_gun_gomulu(monkeypatch)
    r = client.get("/gomulu/guncel", params={"bicim": "kart", "renk": "koyu"})
    assert r.status_code == 200 and 'class="kart"' in r.text
    assert "Şehitlerimizi rahmet, minnet ve saygıyla anıyoruz" in r.text and "setInterval" not in r.text
    assert r.headers.get("x-frame-options") is None
    assert client.get("/gomulu/guncel", params={"bicim": "xx", "renk": "yy"}).status_code == 200


def test_gomulu_guncel_yil_donumu_doner(client, sehit_ekle, monkeypatch):
    _sabit_gun_gomulu(monkeypatch)
    sehit_ekle(ad="Ali", soyad="Kaya", gorev="Piyade Er", sehadet_tarihi=date(2016, 10, 23))
    sehit_ekle(ad="Veli", soyad="Er", sehadet_tarihi=date(2011, 10, 23))
    t = client.get("/gomulu/guncel").text
    assert 'class="bant"' in t and "Şehadetinin 10. yıl dönümü" in t and "Piyade Er Ali KAYA" in t
    assert "Rahmet ve minnetle anıyoruz." in t and "setInterval" in t and "Veli ER" in t


def test_gomulu_guncel_yeni_sehit_onceliklidir(client, sehit_ekle, monkeypatch):
    _sabit_gun_gomulu(monkeypatch)
    sehit_ekle(ad="Ali", soyad="Kaya", sehadet_tarihi=date(2016, 10, 23))
    sehit_ekle(ad="Yeni", soyad="Asker", sehadet_tarihi=date(2026, 10, 22))
    t = client.get("/gomulu/guncel").text
    assert "Şehidimiz" in t and "Yeni ASKER" in t and "Ali KAYA" not in t
    assert "başsağlığı" in t and "setInterval" not in t  # tek kişi: dönmez


def test_gomulu_guncel_json_kacisi(client, sehit_ekle, monkeypatch):
    _sabit_gun_gomulu(monkeypatch)
    sehit_ekle(ad="A</script><b>", soyad="X", sehadet_tarihi=date(2026, 10, 22))
    sehit_ekle(ad="B", soyad="Y", sehadet_tarihi=date(2026, 10, 21))
    t = client.get("/gomulu/guncel").text
    betik = t[t.index("<script>"):]
    assert "</script><b>" not in betik.split("</script>", 1)[0]


def test_bannerlar_kose_secici(client):
    t = client.get("/bannerlar").text
    assert 'role="radiogroup"' in t and ">Sol alt</button>" in t
    assert 'id="varyant-kose-kurdele-sol-alt"' in t and 'id="kod-kose-kurdele-sol-alt-html"' in t
    assert t.count('class="varyant"') >= 14  # 10 bannerın her biri + köşe kurdelesinin 4 köşesi


def test_muzik_calar_sol_altta(client, monkeypatch):
    from app.config import get_settings

    # Yerel .env'deki MUZIK_* ayarları testi etkilemesin: varsayılanlar açıkça kurulur.
    for alan, deger in (("muzik_aktif", True), ("muzik_dosyasi", "/public/kolaydegildir.mp3"),
                        ("muzik_basligi", "Duman — Kolay Değildir"), ("muzik_baslangic_sesi", 0.4)):
        monkeypatch.setattr(get_settings(), alan, deger)
    t = client.get("/hakkinda").text
    assert 'id="muzik"' in t and 'data-ses="0.4"' in t
    assert '<audio id="muzik-ses-dosyasi" src="/public/kolaydegildir.mp3" preload="auto" loop>' in t
    assert "Duman — Kolay Değildir" in t and 'src="/static/muzik.js?v=' in t
    assert 'id="muzik-ses"' in t and 'value="40"' in t and 'id="muzik-oynat"' in t and 'id="muzik-sessiz"' in t
    assert "youtube" not in t.lower()
    js = client.get("/static/muzik.js")
    assert js.status_code == 200 and "ses.play()" in js.text and "youtube" not in js.text.lower()
    assert "pointerdown" in js.text and "durdurdu" in js.text  # ilk etkileşimde başlar, duraklatma hatırlanır
    assert 'id="muzik-panel"' not in t  # minimal: ayrı panel yok


def test_public_klasoru_sunulur(client):
    from pathlib import Path
    import app.main as m
    dosya = Path(m.__file__).resolve().parent.parent / "public" / "kolaydegildir.mp3"
    if dosya.exists():
        r = client.get("/public/kolaydegildir.mp3", headers={"Range": "bytes=0-99"})
        assert r.status_code in (200, 206) and r.headers["content-type"].startswith("audio/")


def test_muzik_calar_kapatilabilir(client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "muzik_aktif", False)
    assert 'id="muzik"' not in client.get("/hakkinda").text


def test_statik_dosyalar_surumlu(client):
    import re
    for sayfa in ("/hakkinda", "/panel/giris"):
        t = client.get(sayfa).text
        surum = re.search(r'href="/static/site\.css\?v=([0-9a-f]{10})"', t)
        assert surum, sayfa  # içerik değişince adres de değişir: CDN/tarayıcı eski CSS'e takılmaz
        assert client.get(f"/static/site.css?v={surum[1]}").status_code == 200
    assert 'href="/static/panel.css?v=' in client.get("/panel/giris").text


def test_muzik_calar_panelde_yok(client):
    assert 'id="muzik"' not in client.get("/panel/giris").text


def test_sehit_sayfasi_fotograf_yer_ve_olay(client, sehit_ekle):
    s = sehit_ekle(sehadet_yeri="Hakkâri", sehadet_olayi="Çatışmada <b>şehit</b> oldu.",
                   fotograf_url="https://x/a.jpg")
    h = client.get(s.url).text
    assert 'src="https://x/a.jpg"' in h and "Hakkâri" in h
    assert "Çatışmada &lt;b&gt;şehit&lt;/b&gt; oldu." in h


def test_sehit_sayfasi_ayrinti_yoksa_bolum_yok(client, sehit_ekle):
    h = client.get(sehit_ekle().url).text
    assert 'class="foto"' not in h and "Şehadeti" not in h and "Şehadet yeri" not in h


def test_ana_sayfa_modalinda_fotograf_ve_olay_alani(client):
    h = client.get("/").text
    assert 'id="m-foto"' in h and 'id="m-olay"' in h


def test_canli_arama_kancalari_ve_temizle_dugmesi(client):
    h = client.get("/").text
    assert 'id="yillar"' in h and 'id="sayim"' in h and 'id="sonuclar"' in h
    assert 'class="ara-temizle" type="button" aria-label="Aramayı temizle" hidden' in h
    h = client.get("/", params={"q": "ahmet"}).text
    assert 'aria-label="Aramayı temizle">' in h  # arama varken temizle düğmesi görünür


def test_ozel_acilir_menu_betigi_her_sayfada(client):
    for yol in ("/", "/yil-donumleri", "/hakkinda"):
        assert "secim.js" in client.get(yol).text
