"""Yeni şehit webhookları: kayıt, Discord embed / genel JSON gövdesi, güvenli gönderim.

Herkes /webhooks sayfasından adres bırakabilir; kayıt `onay_bekliyor` olarak düşer ve yönetici
panelden onaylayana kadar hiçbir istek gönderilmez (ziyaretçi sunucuya istek attıramaz). Onayda
bir deneme mesajı gider; başarılıysa webhook `aktif` olur.

Tetikleyici: panelde onaylanıp yayına giren ve şehadeti son `YENI_GUN_SAYISI` günde olan kayıt
(toplu aktarımla gelen geçmiş kayıtlar asla). Her kayıt bir kez duyurulur (`Sehit.webhook_duyurusu`).

Güvenlik (SSRF): yalnızca https; ad çözümlenir ve adreslerden biri bile genel internet dışındaysa
(yerel ağ, loopback, bulut meta veri adresi...) gönderilmez. İstek, doğrulanan IP'ye sabitlenerek
atılır (DNS yeniden bağlama hilesi işlemez); TLS sertifikası yine alan adına göre doğrulanır.
Yönlendirme izlenmez.
"""
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import secrets
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bannerlar import ANMA_EK, ANMA_YAZISI, YENI_GUN_SAYISI, YENI_YAZISI
from app.config import get_settings
from app.models import Durum, Hassasiyet, Kategori, Sehit, Webhook, WebhookDurumu, WebhookTuru
from app.schemas import SehitDetay

logger = logging.getLogger(__name__)

URL_EN_UZUN = 500
AD_EN_UZUN = 100
ILETISIM_EN_UZUN = 200
BEKLEYEN_EN_COK = 200  # onay bekleyen kayıt tavanı: form doldurularak tablo şişirilemesin
ZAMAN_ASIMI_SN = 10.0
HATA_SINIRI = 5  # art arda bu kadar başarısız gönderimde webhook kapanır
ES_ZAMANLI = 8
RENK = 0xE30A17
SITE_ADI = "Vatan Sağ Olsun"
IMZA_BASLIGI = "X-Vatansagolsun-Imza"
OLAY_BASLIGI = "X-Vatansagolsun-Olay"
DISCORD_SUNUCULARI = frozenset({
    "discord.com", "ptb.discord.com", "canary.discord.com",
    "discordapp.com", "ptb.discordapp.com", "canary.discordapp.com",
})
_DISCORD_YOLU = re.compile(r"/api(?:/v\d+)?/webhooks/\d+/[A-Za-z0-9_-]+/?")
_HEDEF_GITTI = {401, 403, 404}  # Discord: webhook silinmiş ya da anahtar geçersiz; denemeye değmez

# Testler bunları değiştirir: ad çözümleyici ve httpx taşıyıcısı.
COZUMLE = socket.getaddrinfo
TASIYICI: httpx.BaseTransport | None = None


class WebhookHatasi(Exception):
    """Kullanıcıya gösterilebilecek Türkçe hata."""


def _simdi() -> datetime:
    return datetime.now(timezone.utc)


def tur_bul(url: str) -> WebhookTuru:
    p = urlsplit(url)
    if (p.hostname or "").lower() not in DISCORD_SUNUCULARI:
        return WebhookTuru.genel
    if not _DISCORD_YOLU.fullmatch(p.path):
        raise WebhookHatasi("Discord adresi bir webhook adresi değil (…/api/webhooks/… biçiminde olmalı).")
    return WebhookTuru.discord


def _guvenli_ipler(sunucu: str, port: int) -> list[str]:
    try:
        bilgiler = COZUMLE(sunucu, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, OSError):
        raise WebhookHatasi("Adresin sunucusu bulunamadı.") from None
    ipler = list(dict.fromkeys(b[4][0] for b in bilgiler))
    if not ipler:
        raise WebhookHatasi("Adresin sunucusu bulunamadı.")
    for ip in ipler:
        adres = ipaddress.ip_address(ip.split("%")[0])
        if not adres.is_global or adres.is_multicast:
            raise WebhookHatasi("Bu adres genel internette değil (yerel ya da özel ağ adresi); kabul edilmez.")
    return ipler


def adres_dogrula(ham: str) -> tuple[str, WebhookTuru]:
    """Adresi denetler; (düzenlenmiş adres, tür) döner, uygun değilse WebhookHatasi."""
    url = (ham or "").strip()
    if not url:
        raise WebhookHatasi("Lütfen webhook adresini yazın.")
    if len(url) > URL_EN_UZUN:
        raise WebhookHatasi(f"Adres en fazla {URL_EN_UZUN} karakter olabilir.")
    try:
        p = urlsplit(url)
        port = p.port or 443
    except ValueError:
        raise WebhookHatasi("Adres geçersiz.") from None
    if p.scheme.lower() != "https":
        raise WebhookHatasi("Yalnızca https:// ile başlayan adresler kabul edilir.")
    if not p.hostname or p.username is not None or p.password is not None:
        raise WebhookHatasi("Adres geçersiz.")
    tur = tur_bul(url)
    _guvenli_ipler(p.hostname, port)
    duzgun = urlunsplit(("https", p.netloc.lower(), p.path or "/", p.query, ""))
    return duzgun, tur


def gonder(url: str, govde: bytes, basliklar: dict[str, str]) -> httpx.Response:
    """Gövdeyi, adresin doğrulanmış IP'sine sabitlenmiş tek bir POST ile gönderir."""
    p = urlsplit(url)
    port = p.port or 443
    ip = _guvenli_ipler(p.hostname or "", port)[0]
    sunucu = f"[{ip}]" if ":" in ip else ip
    hedef = urlunsplit(("https", f"{sunucu}:{port}", p.path or "/", p.query, ""))
    host = p.hostname if port == 443 else f"{p.hostname}:{port}"
    ua = f"vatansagolsun-webhook/1.0 (+{get_settings().site_url})"
    with httpx.Client(transport=TASIYICI, timeout=ZAMAN_ASIMI_SN, follow_redirects=False) as istemci:
        return istemci.post(
            hedef, content=govde,
            headers={"Host": host, "Content-Type": "application/json", "User-Agent": ua, **basliklar},
            extensions={"sni_hostname": p.hostname},  # TLS: SNI ve sertifika alan adına göre
        )


# --- gövdeler -------------------------------------------------------------------------------

def _site() -> str:
    return get_settings().site_url.rstrip("/")


def gorsel_adresleri(site: str) -> dict[str, str]:
    return {
        "banner": f"{site}/static/webhook/bayrak-banner.png",
        "ikon": f"{site}/static/webhook/bayrak-ikon.png",
    }


def _kirp(metin: str, sinir: int) -> str:
    return metin if len(metin) <= sinir else metin[: sinir - 1].rstrip() + "…"


def _tarih_metni(sehit: Sehit) -> str:
    if sehit.tarih_hassasiyeti == Hassasiyet.tam and sehit.sehadet_tarihi:
        return sehit.sehadet_tarihi.strftime("%d.%m.%Y")
    return str(sehit.yil) if sehit.yil else ""


def _http_mi(url: str | None) -> bool:
    return bool(url) and urlsplit(url).scheme in ("http", "https")


def discord_govdesi(sehit: Sehit, site: str) -> dict:
    g = gorsel_adresleri(site)
    tarih = _tarih_metni(sehit)
    # Olay anlatımı yoksa kısa bir cümle; yer adı alanlarda verilir (Türkçe ek üretmek güvenilmez).
    aciklama = sehit.sehadet_olayi or (f"{tarih} tarihinde şehit düştü." if tarih else "Şehit düştü.")
    alanlar = [
        {"name": ad, "value": _kirp(deger, 1024), "inline": True}
        for ad, deger in (
            ("Şehadet tarihi", tarih), ("Şehadet yeri", sehit.sehadet_yeri),
            ("Memleket", sehit.memleket), ("Kurum", sehit.kurum),
        ) if deger
    ]
    embed = {
        "author": {"name": SITE_ADI, "url": site, "icon_url": g["ikon"]},
        "title": _kirp(" ".join(filter(None, [sehit.gorev, sehit.gorunen_ad])), 256),
        "url": site + sehit.url,
        "description": _kirp(aciklama, 2000),
        "color": RENK,
        "fields": alanlar,
        "image": {"url": g["banner"]},
        "footer": {"text": f"{ANMA_YAZISI} · {ANMA_EK}", "icon_url": g["ikon"]},
        "timestamp": _simdi().isoformat(timespec="seconds"),
    }
    if _http_mi(sehit.fotograf_url):
        embed["thumbnail"] = {"url": sehit.fotograf_url}
    return {
        "username": SITE_ADI,
        "avatar_url": g["ikon"],
        "content": f"**Şehidimiz var.** {YENI_YAZISI}",
        "embeds": [embed],
        "allowed_mentions": {"parse": []},  # kayıt metni @everyone gibi bir bahsetme üretemesin
    }


def genel_govde(sehit: Sehit, site: str) -> dict:
    veri = SehitDetay.model_validate(sehit).model_dump(mode="json")
    veri["url"] = site + sehit.url
    return {"olay": "yeni_sehit", "zaman": _simdi().isoformat(timespec="seconds"), "site": site,
            "mesaj": YENI_YAZISI, "sehit": veri}


DENEME_OLAYI = "yeni_sehit_deneme"
DENEME_UYARISI = "🧪 **Deneme mesajı** — gerçek bir duyuru değildir."


def ornek_sehit() -> Sehit:
    """Örnekler ve deneme gönderimleri için uydurma kayıt (veritabanına yazılmaz)."""
    return Sehit(id=0, ad="Ahmet", soyad="YILMAZ", gorev="Piyade Uzman Çavuş", kategori=Kategori.asker,
                 tarih_hassasiyeti=Hassasiyet.tam, sehadet_tarihi=date(2026, 10, 24), yil=2026,
                 memleket="Sivas", kurum="Türk Silahlı Kuvvetleri", sehadet_yeri="Hakkâri",
                 sehadet_olayi="Örnek: Hakkâri'de terör örgütüne yönelik operasyonda şehit düştü.",
                 slug="ahmet-yilmaz", kaynaklar=[])


def yeni_sehit_denemesi(tur: WebhookTuru, sehit: Sehit, site: str) -> dict:
    """Gerçek "yeni şehit" gövdesi, deneme olduğu açıkça işaretlenmiş hâliyle.

    Discord'da mesajın başına uyarı eklenir; JSON'da olay adı değişir ki alıcı kaydı işlemesin.
    """
    if tur == WebhookTuru.discord:
        govde = discord_govdesi(sehit, site)
        govde["content"] = f"{DENEME_UYARISI}\n{govde['content']}"
        return govde
    return {**genel_govde(sehit, site), "olay": DENEME_OLAYI, "deneme": True}


def deneme_govdesi(tur: WebhookTuru, site: str) -> dict:
    metin = "Bu webhook onaylandı. Yeni bir şehidimiz yayına alındığında buraya bildirim gelecek."
    if tur == WebhookTuru.genel:
        return {"olay": "deneme", "zaman": _simdi().isoformat(timespec="seconds"), "site": site, "mesaj": metin}
    g = gorsel_adresleri(site)
    return {
        "username": SITE_ADI, "avatar_url": g["ikon"], "allowed_mentions": {"parse": []},
        "embeds": [{
            "author": {"name": SITE_ADI, "url": site, "icon_url": g["ikon"]},
            "title": "Webhook bağlandı", "description": metin, "color": RENK,
            "image": {"url": g["banner"]},
            "footer": {"text": f"{ANMA_YAZISI} · {ANMA_EK}", "icon_url": g["ikon"]},
        }],
    }


def imza(anahtar: str, govde: bytes) -> str:
    return "sha256=" + hmac.new(anahtar.encode(), govde, hashlib.sha256).hexdigest()


# --- gönderim ---------------------------------------------------------------------------------

@dataclass(frozen=True)
class _Hedef:
    """Webhook satırının iş parçacığına güvenle verilebilen kopyası (ORM nesnesi paylaşılmaz)."""
    id: int
    url: str
    tur: WebhookTuru
    imza_anahtari: str


def _teslim_et(hedef: _Hedef, govde: dict, olay: str) -> tuple[int | None, str]:
    """(HTTP kodu ya da None, kısa sonuç metni). Asla fırlatmaz."""
    ham = json.dumps(govde, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    basliklar = {OLAY_BASLIGI: olay}
    if hedef.tur == WebhookTuru.genel:
        basliklar[IMZA_BASLIGI] = imza(hedef.imza_anahtari, ham)
    try:
        yanit = gonder(hedef.url, ham, basliklar)
    except WebhookHatasi as hata:
        return None, str(hata)
    except httpx.HTTPError as hata:
        return None, f"bağlantı hatası: {type(hata).__name__}"
    except Exception as hata:  # noqa: BLE001 - tek webhook diğerlerini düşürmesin
        logger.exception("webhook %s gönderiminde beklenmeyen hata", hedef.id)
        return None, f"beklenmeyen hata: {type(hata).__name__}"
    if 200 <= yanit.status_code < 300:
        return yanit.status_code, f"başarılı (HTTP {yanit.status_code})"
    return yanit.status_code, f"HTTP {yanit.status_code}"


def _sonucu_isle(webhook: Webhook, kod: int | None, mesaj: str) -> bool:
    basarili = kod is not None and 200 <= kod < 300
    webhook.son_gonderim = _simdi()
    webhook.son_sonuc = mesaj[:300]
    if basarili:
        webhook.ardisik_hata = 0
        webhook.gonderim_sayisi = (webhook.gonderim_sayisi or 0) + 1
        return True
    webhook.ardisik_hata = (webhook.ardisik_hata or 0) + 1
    if webhook.durum == WebhookDurumu.aktif and (
        (webhook.tur == WebhookTuru.discord and kod in _HEDEF_GITTI) or webhook.ardisik_hata >= HATA_SINIRI
    ):
        webhook.durum = WebhookDurumu.kapali
        webhook.son_sonuc = f"{mesaj} — kendiliğinden kapatıldı"[:300]
    return False


def _hedef(w: Webhook) -> _Hedef:
    return _Hedef(w.id, w.url, WebhookTuru(w.tur), w.imza_anahtari)


def yeni_sehit_mi(sehit: Sehit, bugun_: date) -> bool:
    """Duyurulmaya uygun mu: yayında, isimli, şehadeti son YENI_GUN_SAYISI günde, daha önce duyurulmamış."""
    return (
        Durum(sehit.durum) == Durum.yayinda and not sehit.isimsiz and sehit.webhook_duyurusu is None
        and Hassasiyet(sehit.tarih_hassasiyeti) == Hassasiyet.tam and sehit.sehadet_tarihi is not None
        and bugun_ - timedelta(days=YENI_GUN_SAYISI - 1) <= sehit.sehadet_tarihi <= bugun_
    )


def duyuru_hazirla(s: Session, sehit: Sehit, bugun_: date) -> bool:
    """Uygunsa kaydı "duyuruldu" işaretleyip True döner; gönderimi çağıran arka planda başlatır.

    İşaret gönderimden önce konur: ikinci onay ya da yarım kalan gönderim kaydı iki kez duyurmaz.
    """
    if not yeni_sehit_mi(sehit, bugun_):
        return False
    sehit.webhook_duyurusu = _simdi()
    s.commit()
    return True


def duyur(session_factory, sehit_id: int) -> int:
    """Kaydı tüm aktif webhooklara gönderir; başarılı gönderim sayısını döner. Arka planda çalışır."""
    try:
        with session_factory() as s:
            sehit = s.get(Sehit, sehit_id)
            webhooklar = list(s.scalars(select(Webhook).where(Webhook.durum == WebhookDurumu.aktif)))
            if sehit is None or not webhooklar:
                return 0
            site = _site()
            govdeler = {WebhookTuru.discord: discord_govdesi(sehit, site), WebhookTuru.genel: genel_govde(sehit, site)}
            hedefler = [_hedef(w) for w in webhooklar]
            with ThreadPoolExecutor(max_workers=ES_ZAMANLI) as havuz:
                sonuclar = list(havuz.map(lambda h: _teslim_et(h, govdeler[h.tur], "yeni_sehit"), hedefler))
            basarili = sum(_sonucu_isle(w, kod, mesaj) for w, (kod, mesaj) in zip(webhooklar, sonuclar))
            s.commit()
            logger.info("şehit %s duyurusu: %d/%d webhook başarılı", sehit_id, basarili, len(webhooklar))
            return basarili
    except Exception:  # noqa: BLE001 - arka plan işi; hata günlüğe yazılır
        logger.exception("şehit %s webhook duyurusu çöktü", sehit_id)
        return 0


# --- kayıt ve yönetim -----------------------------------------------------------------------

def _ozet(anahtar: str) -> str:
    return hashlib.sha256(anahtar.encode()).hexdigest()


@dataclass
class YeniKayit:
    webhook: Webhook
    silme_anahtari: str


def kayit_ekle(s: Session, *, url: str, ad: str | None, iletisim: str | None) -> YeniKayit:
    duzgun, tur = adres_dogrula(url)
    ad = (ad or "").strip() or None
    iletisim = (iletisim or "").strip() or None
    if ad and len(ad) > AD_EN_UZUN:
        raise WebhookHatasi(f"Ad en fazla {AD_EN_UZUN} karakter olabilir.")
    if iletisim and len(iletisim) > ILETISIM_EN_UZUN:
        raise WebhookHatasi(f"İletişim bilgisi en fazla {ILETISIM_EN_UZUN} karakter olabilir.")
    if s.scalar(select(Webhook.id).where(Webhook.url == duzgun)) is not None:
        raise WebhookHatasi("Bu adres zaten kayıtlı.")
    bekleyen = s.scalar(select(func.count(Webhook.id)).where(Webhook.durum == WebhookDurumu.onay_bekliyor))
    if bekleyen >= BEKLEYEN_EN_COK:
        raise WebhookHatasi("Şu anda onay bekleyen çok fazla webhook var; lütfen daha sonra tekrar deneyin.")
    silme = secrets.token_urlsafe(24)
    webhook = Webhook(url=duzgun, tur=tur, ad=ad, iletisim=iletisim, durum=WebhookDurumu.onay_bekliyor,
                      silme_anahtari_ozeti=_ozet(silme), imza_anahtari=secrets.token_hex(32),
                      ardisik_hata=0, gonderim_sayisi=0)
    s.add(webhook)
    s.commit()
    return YeniKayit(webhook, silme)


def anahtarla_sil(s: Session, anahtar: str) -> bool:
    anahtar = (anahtar or "").strip()
    if not anahtar or len(anahtar) > 100:
        return False
    webhook = s.scalar(select(Webhook).where(Webhook.silme_anahtari_ozeti == _ozet(anahtar)))
    if webhook is None:
        return False
    s.delete(webhook)
    s.commit()
    return True


def onayla(s: Session, webhook: Webhook) -> tuple[bool, str]:
    """Deneme mesajı gönderir; başarılıysa webhook aktif olur, değilse durumu değişmez."""
    kod, mesaj = _teslim_et(_hedef(webhook), deneme_govdesi(WebhookTuru(webhook.tur), _site()), "deneme")
    basarili = _sonucu_isle(webhook, kod, mesaj)
    if basarili:
        webhook.durum = WebhookDurumu.aktif
    s.commit()
    return basarili, webhook.son_sonuc or ""


def ornek_gonder(s: Session, webhook: Webhook, sehit: Sehit | None = None) -> tuple[bool, str]:
    """"Yeni şehit varmış gibi" deneme gönderimi; webhook'un durumunu değiştirmez (onaylamaz).

    Sonuç ve hata sayacı gerçek gönderimdeki gibi işlenir: silinmiş bir Discord webhook'u kapanır.
    """
    tur = WebhookTuru(webhook.tur)
    govde = yeni_sehit_denemesi(tur, sehit or ornek_sehit(), _site())
    kod, mesaj = _teslim_et(_hedef(webhook), govde, DENEME_OLAYI)
    basarili = _sonucu_isle(webhook, kod, mesaj)
    s.commit()
    return basarili, webhook.son_sonuc or ""


def gizli_adres(webhook: Webhook) -> str:
    """Panelde gösterim: Discord anahtarı ve sorgu parametreleri gizlenir."""
    p = urlsplit(webhook.url)
    if webhook.tur == WebhookTuru.discord:
        parcalar = p.path.rstrip("/").split("/")
        return f"{p.hostname}/api/webhooks/{parcalar[-2]}/•••"
    yol = p.path if len(p.path) <= 40 else p.path[:39] + "…"
    return f"{p.netloc}{yol}" + ("?…" if p.query else "")
