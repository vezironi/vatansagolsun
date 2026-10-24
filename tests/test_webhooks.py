import hashlib
import hmac
import json
import re
import socket
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from app import webhooks
from app.dates import bugun
from app.models import Durum, Sehit, Webhook, WebhookDurumu, WebhookTuru

DISCORD = "https://discord.com/api/webhooks/123456789012345678/AbC-dEf_123"
GENEL = "https://ornek.com.tr/kanca?kaynak=vso"
GENEL_IP = "93.184.215.14"


def _cozumleyici(tablo: dict[str, list[str]]):
    def cozumle(sunucu, port, type=0):  # noqa: A002 - socket.getaddrinfo imzası
        if sunucu not in tablo:
            raise socket.gaierror("bulunamadı")
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))
                for ip in tablo[sunucu]]
    return cozumle


class Kayitci:
    """Sahte taşıyıcı: gelen istekleri saklar, sırayla verilen kodlarla yanıtlar."""

    def __init__(self, *kodlar: int):
        self.kodlar, self.istekler = list(kodlar), []

    def __call__(self, istek: httpx.Request) -> httpx.Response:
        self.istekler.append(istek)
        return httpx.Response(self.kodlar.pop(0) if self.kodlar else 204)


@pytest.fixture(autouse=True)
def ag(monkeypatch):
    """Gerçek ağa asla çıkılmaz: ad çözümleme ve HTTP sahte; varsayılan olarak her istek 204."""
    monkeypatch.setattr(webhooks, "COZUMLE", _cozumleyici({
        "discord.com": ["162.159.135.232"], "ptb.discord.com": ["162.159.136.232"], "ornek.com.tr": [GENEL_IP],
        "ic.ornek.com.tr": ["10.0.0.5"], "karma.ornek.com.tr": [GENEL_IP, "127.0.0.1"],
        "v6.ornek.com.tr": ["::1"], "meta.ornek.com.tr": ["169.254.169.254"],
    }))
    kayitci = Kayitci()
    monkeypatch.setattr(webhooks, "TASIYICI", httpx.MockTransport(kayitci))
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "site_url", "https://vatansagolsun.org")
    return kayitci


def _yanitlar(monkeypatch, *kodlar) -> Kayitci:
    kayitci = Kayitci(*kodlar)
    monkeypatch.setattr(webhooks, "TASIYICI", httpx.MockTransport(kayitci))
    return kayitci


def _webhook(session, url=DISCORD, durum=WebhookDurumu.aktif, **kw) -> Webhook:
    alanlar = dict(silme_anahtari_ozeti="x" * 64, imza_anahtari="k" * 64, ardisik_hata=0, gonderim_sayisi=0)
    w = Webhook(url=url, tur=webhooks.tur_bul(url), durum=durum, **{**alanlar, **kw})
    session.add(w)
    session.commit()
    return w


def _yeni(sehit_ekle, **kw) -> Sehit:
    v = dict(ad="Mustafa", soyad="ASLAN", gorev="Piyade Uzman Çavuş", sehadet_tarihi=bugun(),
             durum="onay_bekliyor", memleket="Gaziantep", sehadet_yeri="Hakkâri")
    v.update(kw)
    return sehit_ekle(**v)


# --- adres doğrulama ------------------------------------------------------------------------

def test_discord_ve_genel_adres_turu():
    assert webhooks.adres_dogrula(DISCORD) == (DISCORD, WebhookTuru.discord)
    assert webhooks.adres_dogrula("https://ptb.discord.com/api/v10/webhooks/1/x")[1] == WebhookTuru.discord
    assert webhooks.adres_dogrula(GENEL) == (GENEL, WebhookTuru.genel)
    assert webhooks.adres_dogrula("  HTTPS://Ornek.com.tr/kanca#parca ")[0] == "https://ornek.com.tr/kanca"


@pytest.mark.parametrize("url, parca", [
    ("http://ornek.com.tr/kanca", "https://"),
    ("ftp://ornek.com.tr/kanca", "https://"),
    ("https://ic.ornek.com.tr/kanca", "genel internette değil"),
    ("https://karma.ornek.com.tr/kanca", "genel internette değil"),  # adreslerden biri bile yerelse
    ("https://v6.ornek.com.tr/kanca", "genel internette değil"),
    ("https://meta.ornek.com.tr/latest", "genel internette değil"),  # bulut meta veri adresi
    ("https://yok.ornek.com.tr/kanca", "bulunamadı"),
    ("https://kul:sifre@ornek.com.tr/kanca", "geçersiz"),
    ("https://discord.com/channels/1/2", "webhook adresi değil"),
    ("https://ornek.com.tr/" + "a" * 600, "en fazla"),
    ("", "yazın"),
])
def test_uygunsuz_adresler_reddedilir(url, parca):
    with pytest.raises(webhooks.WebhookHatasi, match=parca):
        webhooks.adres_dogrula(url)


def test_gonderim_dogrulanan_ipye_sabitlenir_ve_alan_adi_korunur(ag):
    webhooks.gonder(GENEL, b"{}", {})
    istek = ag.istekler[0]
    assert istek.url.host == GENEL_IP and istek.url.path == "/kanca" and istek.url.query == b"kaynak=vso"
    assert istek.headers["host"] == "ornek.com.tr"  # sanal sunucu ve TLS adı alan adı
    assert istek.extensions["sni_hostname"] == "ornek.com.tr"


def test_gonderim_aninda_yerele_donen_ad_reddedilir(monkeypatch, ag):
    # Kayıt sırasında genel IP'ye çözülen ad, gönderimde yerel IP'ye dönerse istek atılmaz.
    monkeypatch.setattr(webhooks, "COZUMLE", _cozumleyici({"ornek.com.tr": ["192.168.1.1"]}))
    with pytest.raises(webhooks.WebhookHatasi):
        webhooks.gonder(GENEL, b"{}", {})
    assert ag.istekler == []


# --- gövdeler -------------------------------------------------------------------------------

def test_discord_embed_yazar_alt_bilgi_icerik_ve_gorseller(sehit_ekle):
    s = _yeni(sehit_ekle, fotograf_url="https://www.egm.gov.tr/a.jpg", sehadet_olayi="Çatışmada şehit düştü.")
    g = webhooks.discord_govdesi(s, "https://vatansagolsun.org")
    e = g["embeds"][0]
    assert g["content"].startswith("**Şehidimiz var.**") and g["allowed_mentions"] == {"parse": []}
    assert e["author"]["name"] == "Vatan Sağ Olsun" and e["author"]["icon_url"].endswith("/static/webhook/bayrak-ikon.png")
    assert e["footer"]["text"] == "Şehitlerimizi rahmet, minnet ve saygıyla anıyoruz · Vatan sağ olsun"
    assert e["image"]["url"] == "https://vatansagolsun.org/static/webhook/bayrak-banner.png"  # büyük: bayrak
    assert e["thumbnail"]["url"] == "https://www.egm.gov.tr/a.jpg"  # küçük: şehidin fotoğrafı
    assert e["title"] == "Piyade Uzman Çavuş Mustafa ASLAN" and e["url"] == "https://vatansagolsun.org" + s.url
    assert e["description"] == "Çatışmada şehit düştü." and e["color"] == 0xE30A17
    assert {a["name"]: a["value"] for a in e["fields"]} == {
        "Şehadet tarihi": bugun().strftime("%d.%m.%Y"), "Şehadet yeri": "Hakkâri", "Memleket": "Gaziantep"}


def test_discord_fotograf_yoksa_kucuk_gorsel_yok_ve_varsayilan_aciklama(sehit_ekle):
    s = _yeni(sehit_ekle)
    e = webhooks.discord_govdesi(s, "https://x")["embeds"][0]
    assert "thumbnail" not in e and e["description"] == f"{bugun():%d.%m.%Y} tarihinde şehit düştü."


def test_genel_govde_nesne_ve_imza(sehit_ekle, session, ag):
    s = _yeni(sehit_ekle, durum="yayinda")
    w = _webhook(session, GENEL)
    govde = webhooks.genel_govde(s, "https://vatansagolsun.org")
    assert govde["olay"] == "yeni_sehit" and govde["sehit"]["gorunen_ad"] == "Mustafa ASLAN"
    assert govde["sehit"]["url"] == "https://vatansagolsun.org" + s.url and govde["sehit"]["sehadet_yeri"] == "Hakkâri"
    webhooks._teslim_et(webhooks._hedef(w), govde, "yeni_sehit")
    istek = ag.istekler[0]
    beklenen = "sha256=" + hmac.new(("k" * 64).encode(), istek.content, hashlib.sha256).hexdigest()
    assert istek.headers[webhooks.IMZA_BASLIGI] == beklenen
    assert istek.headers[webhooks.OLAY_BASLIGI] == "yeni_sehit" and json.loads(istek.content) == govde


# --- tetikleme ------------------------------------------------------------------------------

def test_yeni_sehit_tanimi(sehit_ekle):
    gun = bugun()
    assert webhooks.yeni_sehit_mi(_yeni(sehit_ekle, durum="yayinda"), gun)
    assert webhooks.yeni_sehit_mi(_yeni(sehit_ekle, ad="B", durum="yayinda", sehadet_tarihi=gun - timedelta(days=6)), gun)
    assert not webhooks.yeni_sehit_mi(_yeni(sehit_ekle, ad="C", durum="yayinda", sehadet_tarihi=gun - timedelta(days=7)), gun)
    assert not webhooks.yeni_sehit_mi(_yeni(sehit_ekle, ad="D", durum="onay_bekliyor"), gun)
    assert not webhooks.yeni_sehit_mi(_yeni(sehit_ekle, ad="E", durum="yayinda", isimsiz=True), gun)
    assert not webhooks.yeni_sehit_mi(_yeni(sehit_ekle, ad="F", durum="yayinda", tarih_hassasiyeti="yil",
                                            sehadet_tarihi=None, yil=gun.year), gun)


def test_duyur_yalnizca_aktiflere_gider_ve_sonucu_yazar(sehit_ekle, session, ag):
    s = _yeni(sehit_ekle, durum="yayinda")
    aktif_d, aktif_g = _webhook(session, DISCORD), _webhook(session, GENEL)
    _webhook(session, "https://discord.com/api/webhooks/9/bekleyen", durum=WebhookDurumu.onay_bekliyor)
    _webhook(session, "https://discord.com/api/webhooks/8/kapali", durum=WebhookDurumu.kapali)
    assert webhooks.duyur(sessionmaker(session.get_bind()), s.id) == 2
    assert len(ag.istekler) == 2
    assert {i.headers["host"] for i in ag.istekler} == {"discord.com", "ornek.com.tr"}
    session.expire_all()
    assert aktif_d.gonderim_sayisi == aktif_g.gonderim_sayisi == 1 and aktif_d.son_sonuc.startswith("başarılı")


def test_discord_404_webhooku_kapatir_genel_5_hatada_kapanir(sehit_ekle, session, monkeypatch):
    s = _yeni(sehit_ekle, durum="yayinda")
    d, g = _webhook(session, DISCORD), _webhook(session, GENEL, ardisik_hata=webhooks.HATA_SINIRI - 1)
    _yanitlar(monkeypatch, 404, 500)
    webhooks.duyur(sessionmaker(session.get_bind()), s.id)
    session.expire_all()
    assert d.durum == WebhookDurumu.kapali and "kendiliğinden kapatıldı" in d.son_sonuc
    assert g.durum == WebhookDurumu.kapali and g.ardisik_hata == webhooks.HATA_SINIRI


def test_tek_hata_webhooku_kapatmaz(sehit_ekle, session, monkeypatch):
    s = _yeni(sehit_ekle, durum="yayinda")
    g = _webhook(session, GENEL)
    _yanitlar(monkeypatch, 503)
    webhooks.duyur(sessionmaker(session.get_bind()), s.id)
    session.expire_all()
    assert g.durum == WebhookDurumu.aktif and g.ardisik_hata == 1 and g.son_sonuc == "HTTP 503"


# --- herkese açık sayfa ---------------------------------------------------------------------

def test_sayfa_navbarda_ve_ornekler_gorunur(client):
    assert '<a href="/webhooks">Webhooks</a>' in client.get("/").text
    h = client.get("/webhooks").text
    assert "Webhook ekle" in h and "bayrak-banner.png" in h and "&#34;olay&#34;: &#34;yeni_sehit&#34;" in h


def test_eklenen_webhook_onay_bekler_ve_hic_istek_atilmaz(client, session, ag):
    r = client.post("/webhooks", data={"url": DISCORD, "ad": "Duyurular", "iletisim": "a@b.c"})
    assert r.status_code == 200 and "onay bekliyor" in r.text
    w = session.query(Webhook).one()
    assert (w.durum, w.tur, w.ad) == (WebhookDurumu.onay_bekliyor, WebhookTuru.discord, "Duyurular")
    assert ag.istekler == []  # ziyaretçi sunucumuza istek attıramaz
    anahtar = re.search(r'<pre class="anahtar"><code>([^<]+)</code>', r.text).group(1)
    assert w.silme_anahtari_ozeti == hashlib.sha256(anahtar.encode()).hexdigest()  # anahtarın kendisi saklanmaz
    assert "İmza anahtarınız" not in r.text  # Discord'da imza yok

    assert client.post("/webhooks", data={"url": DISCORD}).status_code == 400  # aynı adres
    assert client.post("/webhooks/sil", data={"anahtar": "yanlis"}).status_code == 400
    assert "silindi" in client.post("/webhooks/sil", data={"anahtar": anahtar}).text
    assert session.query(Webhook).count() == 0


def test_genel_webhook_icin_imza_anahtari_gosterilir(client, session):
    r = client.post("/webhooks", data={"url": GENEL})
    assert "İmza anahtarınız" in r.text and session.query(Webhook).one().imza_anahtari in r.text


def test_uygunsuz_adres_formda_hata(client, session):
    r = client.post("/webhooks", data={"url": "https://ic.ornek.com.tr/x", "ad": "Ad"})
    assert r.status_code == 400 and "genel internette değil" in r.text and 'value="Ad"' in r.text
    assert session.query(Webhook).count() == 0


def test_onay_bekleyen_tavani(client, session, monkeypatch):
    monkeypatch.setattr(webhooks, "BEKLEYEN_EN_COK", 1)
    assert client.post("/webhooks", data={"url": DISCORD}).status_code == 200
    r = client.post("/webhooks", data={"url": GENEL})
    assert r.status_code == 400 and "çok fazla" in r.text


# --- panel ----------------------------------------------------------------------------------

def test_panelde_onaylayinca_deneme_gider_ve_aktif_olur(panel_client, csrf, session, ag):
    w = _webhook(session, DISCORD, durum=WebhookDurumu.onay_bekliyor, ad="Kanal")
    h = panel_client.get("/panel/webhooklar").text
    assert "Kanal" in h and "AbC-dEf_123" not in h and "/api/webhooks/123456789012345678/•••" in h  # anahtar gizli
    r = panel_client.post(f"/panel/webhooklar/{w.id}/onayla", data={"csrf": csrf(panel_client)})
    assert r.status_code == 200 and "webhook aktif" in r.text
    session.refresh(w)
    assert w.durum == WebhookDurumu.aktif
    assert json.loads(ag.istekler[0].content)["embeds"][0]["title"] == "Webhook bağlandı"


def test_panelde_deneme_basarisizsa_onay_bekler(panel_client, csrf, session, monkeypatch):
    w = _webhook(session, GENEL, durum=WebhookDurumu.onay_bekliyor)
    _yanitlar(monkeypatch, 500)
    r = panel_client.post(f"/panel/webhooklar/{w.id}/onayla", data={"csrf": csrf(panel_client)})
    assert "gönderilemedi: HTTP 500" in r.text
    session.refresh(w)
    assert w.durum == WebhookDurumu.onay_bekliyor


def test_panelde_reddet_ve_sil(panel_client, csrf, session):
    w = _webhook(session, GENEL, durum=WebhookDurumu.onay_bekliyor)
    panel_client.post(f"/panel/webhooklar/{w.id}/reddet", data={"csrf": csrf(panel_client)})
    session.refresh(w)
    assert w.durum == WebhookDurumu.reddedildi
    panel_client.post(f"/panel/webhooklar/{w.id}/sil", data={"csrf": csrf(panel_client)})
    assert session.query(Webhook).count() == 0
    assert panel_client.post("/panel/webhooklar/999/sil", data={"csrf": csrf(panel_client)}).status_code == 404


def test_panel_webhook_islemleri_csrf_ister(panel_client, session):
    w = _webhook(session, GENEL, durum=WebhookDurumu.onay_bekliyor)
    assert panel_client.post(f"/panel/webhooklar/{w.id}/onayla", data={"csrf": "yanlis"}).status_code == 403


def test_yeni_sehit_onaylaninca_bir_kez_duyurulur(app, panel_client, csrf, session, sehit_ekle, ag):
    app.state.session_factory = sessionmaker(session.get_bind())
    _webhook(session, DISCORD)
    s = _yeni(sehit_ekle)
    panel_client.post(f"/panel/sehit/{s.id}/onayla", data={"csrf": csrf(panel_client)})
    assert len(ag.istekler) == 1  # TestClient arka plan görevini yanıttan sonra çalıştırır
    assert json.loads(ag.istekler[0].content)["embeds"][0]["title"] == "Piyade Uzman Çavuş Mustafa ASLAN"
    session.refresh(s)
    assert s.webhook_duyurusu is not None
    # yayından kaldırılıp yeniden onaylansa da ikinci kez gitmez
    panel_client.post(f"/panel/sehit/{s.id}/kaldir", data={"csrf": csrf(panel_client)})
    panel_client.post(f"/panel/sehit/{s.id}/onayla", data={"csrf": csrf(panel_client)})
    assert len(ag.istekler) == 1


def test_kaydet_ve_onayla_da_duyurur(app, panel_client, csrf, session, sehit_ekle, ag):
    app.state.session_factory = sessionmaker(session.get_bind())
    _webhook(session, GENEL)
    s = _yeni(sehit_ekle)
    form = {"csrf": csrf(panel_client), "ad": "Mustafa", "soyad": "ASLAN", "kategori": "asker",
            "tarih_hassasiyeti": "tam", "sehadet_tarihi": bugun().isoformat(), "kaynak_kodu": "haber",
            "islem": "onayla"}
    panel_client.post(f"/panel/sehit/{s.id}", data=form)
    assert len(ag.istekler) == 1 and json.loads(ag.istekler[0].content)["olay"] == "yeni_sehit"


def test_eski_tarihli_kaydin_onayi_duyurulmaz(app, panel_client, csrf, session, sehit_ekle, ag):
    app.state.session_factory = sessionmaker(session.get_bind())
    _webhook(session, DISCORD)
    s = _yeni(sehit_ekle, sehadet_tarihi=date(2016, 7, 15))
    panel_client.post(f"/panel/sehit/{s.id}/onayla", data={"csrf": csrf(panel_client)})
    session.refresh(s)
    assert ag.istekler == [] and s.webhook_duyurusu is None and s.durum == Durum.yayinda


def test_toplu_aktarim_duyurmaz(session, ag):
    from app import aktarim
    from app.kaynaklar import HamKayit
    from app.models import Hassasiyet
    _webhook(session, DISCORD)
    aktarim.kayit_aktar(session, HamKayit(kaynak_kodu="egm", dis_kimlik="/x", ad="Ali", soyad="KAYA",
                                          tarih=bugun(), hassasiyet=Hassasiyet.tam, yil=bugun().year))
    session.commit()
    assert ag.istekler == []


# --- deneme şehit mesajı -------------------------------------------------------------------

def test_panelden_ornek_kayitla_deneme_sehit_mesaji(panel_client, csrf, session, ag):
    w = _webhook(session, DISCORD)
    assert "Deneme şehit mesajı gönder" in panel_client.get("/panel/webhooklar").text
    r = panel_client.post(f"/panel/webhooklar/{w.id}/ornek", data={"csrf": csrf(panel_client)})
    assert "Deneme şehit mesajı gönderildi: örnek kayıt" in r.text
    govde = json.loads(ag.istekler[0].content)
    assert govde["content"].startswith(webhooks.DENEME_UYARISI) and "**Şehidimiz var.**" in govde["content"]
    e = govde["embeds"][0]
    assert e["title"] == "Piyade Uzman Çavuş Ahmet YILMAZ" and e["image"]["url"].endswith("bayrak-banner.png")
    assert ag.istekler[0].headers[webhooks.OLAY_BASLIGI] == webhooks.DENEME_OLAYI
    session.refresh(w)
    assert w.durum == WebhookDurumu.aktif and w.gonderim_sayisi == 1


def test_deneme_gercek_kayitla_ve_fotografla(panel_client, csrf, session, sehit_ekle, ag):
    w = _webhook(session, DISCORD)
    s = _yeni(sehit_ekle, fotograf_url="https://www.egm.gov.tr/a.jpg")
    panel_client.post(f"/panel/webhooklar/{w.id}/ornek", data={"csrf": csrf(panel_client), "sehit_id": str(s.id)})
    e = json.loads(ag.istekler[0].content)["embeds"][0]
    assert e["title"] == "Piyade Uzman Çavuş Mustafa ASLAN" and e["thumbnail"]["url"] == "https://www.egm.gov.tr/a.jpg"
    session.refresh(s)
    assert s.webhook_duyurusu is None  # deneme, kaydı "duyuruldu" saymaz


def test_deneme_json_olay_adi_alicinin_islememesi_icin_farkli(panel_client, csrf, session, ag):
    w = _webhook(session, GENEL, durum=WebhookDurumu.onay_bekliyor)
    panel_client.post(f"/panel/webhooklar/{w.id}/ornek", data={"csrf": csrf(panel_client)})
    govde = json.loads(ag.istekler[0].content)
    assert govde["olay"] == "yeni_sehit_deneme" and govde["deneme"] is True and govde["sehit"]["ad"] == "Ahmet"
    session.refresh(w)
    assert w.durum == WebhookDurumu.onay_bekliyor  # deneme onaylamaz


@pytest.mark.parametrize("kayit_no, ileti", [("abc", "bir sayı olmalı"), ("99999", "bulunamadı")])
def test_deneme_gecersiz_kayit_no(panel_client, csrf, session, ag, kayit_no, ileti):
    w = _webhook(session, DISCORD)
    r = panel_client.post(f"/panel/webhooklar/{w.id}/ornek", data={"csrf": csrf(panel_client), "sehit_id": kayit_no})
    assert ileti in r.text and ag.istekler == []


def test_deneme_basarisizsa_hata_gosterilir(panel_client, csrf, session, monkeypatch):
    w = _webhook(session, DISCORD)
    _yanitlar(monkeypatch, 404)
    r = panel_client.post(f"/panel/webhooklar/{w.id}/ornek", data={"csrf": csrf(panel_client)})
    assert "gönderilemedi: HTTP 404" in r.text
    session.refresh(w)
    assert w.durum == WebhookDurumu.kapali  # silinmiş Discord webhook'u kapanır
