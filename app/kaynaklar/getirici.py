"""Nazik HTTP istemcisi: kaynak sitelere tüm ağ erişimi buradan geçer."""
import time
import urllib.robotparser
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.kaynaklar import KaynakHatasi, KaynakIzniYok

YENIDEN_DENEME_BEKLEMELERI = (30, 60, 120)


class Getirici:
    def __init__(
        self,
        *,
        araligi_sn: float | None = None,
        transport: httpx.BaseTransport | None = None,
        uyku: Callable[[float], None] = time.sleep,
        saat: Callable[[], float] = time.monotonic,
        izinler: list[str] | None = None,
    ) -> None:
        ayarlar = get_settings()
        self._araligi = ayarlar.istek_araligi_sn if araligi_sn is None else araligi_sn
        self._izinler = list(ayarlar.kaynak_izinleri if izinler is None else izinler)
        self._uyku = uyku
        self._saat = saat
        self._ua = f"Mozilla/5.0 (compatible; vatansagolsun-aktarim/1.0; +{ayarlar.site_url})"
        self._istemci = httpx.Client(
            transport=transport, timeout=30.0, headers={"User-Agent": self._ua}, follow_redirects=True
        )
        self._son_istek: dict[str, float] = {}
        self._robotlar: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def metin(self, kaynak_kodu: str, url: str, *, params: dict | None = None) -> str:
        return self._yap(kaynak_kodu, "GET", url, params=params).text

    def json(self, kaynak_kodu: str, url: str, *, params: dict | None = None) -> Any:
        return self._yap(kaynak_kodu, "GET", url, params=params).json()

    def post_json(self, kaynak_kodu: str, url: str, govde: dict, *, referer: str) -> str:
        return self._yap(kaynak_kodu, "POST", url, json=govde, headers={"Referer": referer}).text

    def _yap(self, kaynak_kodu: str, yontem: str, url: str, **kw: Any) -> httpx.Response:
        if kaynak_kodu not in self._izinler:
            raise KaynakIzniYok(f"{kaynak_kodu!r} kaynağı izin listesinde yok; istek atılmadı")
        self._robots_denetle(url)
        yanit = self._istek(yontem, url, **kw)
        if yanit.status_code >= 400:
            raise KaynakHatasi(f"{url} HTTP {yanit.status_code} döndü")
        return yanit

    def _robots_denetle(self, url: str) -> None:
        parca = urlsplit(url)
        kok = f"{parca.scheme}://{parca.netloc}"
        if kok not in self._robotlar:
            yanit = self._istek("GET", f"{kok}/robots.txt")
            if yanit.status_code >= 400:
                self._robotlar[kok] = None  # robots.txt yok/okunamadı: serbest
            else:
                robot = urllib.robotparser.RobotFileParser()
                robot.parse(yanit.text.splitlines())
                self._robotlar[kok] = robot
        robot = self._robotlar[kok]
        if robot is not None and not robot.can_fetch(self._ua, url):
            raise KaynakHatasi(f"robots.txt {url} adresini yasaklıyor")

    def _istek(self, yontem: str, url: str, **kw: Any) -> httpx.Response:
        """Hız sınırıyla tek istek; 429/5xx/ağ hatasında 30-60-120 sn ile yeniden dener.

        Yeniden denemeye değmeyen yanıtlar (2xx-4xx, 429 hariç) çağırana döner.
        """
        for bekleme in (*YENIDEN_DENEME_BEKLEMELERI, None):
            self._hiz_bekle(urlsplit(url).netloc)
            try:
                yanit = self._istemci.request(yontem, url, **kw)
            except httpx.TransportError as hata:
                yanit, neden = None, f"ağ hatası: {hata}"
            else:
                if yanit.status_code != 429 and yanit.status_code < 500:
                    return yanit
                neden = f"HTTP {yanit.status_code}"
            if bekleme is None:
                raise KaynakHatasi(f"{url} {len(YENIDEN_DENEME_BEKLEMELERI)} yeniden denemeden sonra alınamadı ({neden})")
            self._uyku(bekleme)
        raise AssertionError("ulaşılamaz")  # pragma: no cover

    def _hiz_bekle(self, sunucu: str) -> None:
        simdi = self._saat()
        bekle = 0.0
        if sunucu in self._son_istek:
            fark = simdi - self._son_istek[sunucu]
            if fark < self._araligi:
                bekle = self._araligi - fark
                self._uyku(bekle)
        self._son_istek[sunucu] = simdi + bekle
