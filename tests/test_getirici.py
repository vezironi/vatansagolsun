import httpx, pytest
from app.kaynaklar import KaynakHatasi, KaynakIzniYok
from app.kaynaklar.getirici import Getirici

def _getirici(handler, **kw):
    uykular = []
    g = Getirici(transport=httpx.MockTransport(handler), uyku=uykular.append,
                 saat=kw.pop("saat", lambda: 0.0), izinler=kw.pop("izinler", ["egm"]), araligi_sn=2.0)
    return g, uykular

def test_izinsiz_kaynaga_istek_yok():
    cagrilar = []
    g, _ = _getirici(lambda r: cagrilar.append(r) or httpx.Response(200), izinler=["egm"])
    with pytest.raises(KaynakIzniYok):
        g.metin("sehitlerimiz", "https://sehitlerimiz.org.tr/arsiv")
    assert cagrilar == []

def test_robots_yasagi():
    def h(r):
        if r.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /ara\n")
        return httpx.Response(200, text="ok")
    g, _ = _getirici(h)
    with pytest.raises(KaynakHatasi):
        g.metin("egm", "https://x.test/ara?q=1")
    assert g.metin("egm", "https://x.test/sehitlerimiz") == "ok"

def test_hiz_siniri_bekler():
    zaman = iter([0.0, 0.5, 0.5])
    g, uykular = _getirici(lambda r: httpx.Response(404 if r.url.path == "/robots.txt" else 200, text="ok"),
                           saat=lambda: next(zaman, 10.0))
    g.metin("egm", "https://x.test/a"); g.metin("egm", "https://x.test/b")
    assert any(abs(u - 1.5) < 1e-6 for u in uykular)

def test_429_yeniden_dener_sonra_hata():
    g, uykular = _getirici(lambda r: httpx.Response(404 if r.url.path == "/robots.txt" else 429))
    with pytest.raises(KaynakHatasi):
        g.metin("egm", "https://x.test/a")
    assert [u for u in uykular if u >= 30] == [30, 60, 120]

def test_ua_ve_post_json():
    gorulen = {}
    def h(r):
        if r.url.path == "/robots.txt":
            return httpx.Response(404)
        gorulen.update(ua=r.headers["user-agent"], ct=r.headers.get("content-type"), ref=r.headers.get("referer"), govde=r.content)
        return httpx.Response(200, text="<div></div>")
    g, _ = _getirici(h)
    assert g.post_json("egm", "https://x.test/p", {"page": 2}, referer="https://x.test/s") == "<div></div>"
    assert "vatansagolsun-aktarim/1.0" in gorulen["ua"] and gorulen["ct"].startswith("application/json")
    assert gorulen["ref"] == "https://x.test/s" and b'"page"' in gorulen["govde"]
