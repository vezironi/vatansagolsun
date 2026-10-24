from datetime import date

from app import bannerlar as bn

URL = "https://ornek.test"


def test_her_banner_icin_tum_sekmeler():
    for b in bn.BANNERLAR:
        sekmeler = bn.kod_sekmeleri(b, URL)
        assert [s.kod for s in sekmeler] == ["html", "react", "vue", "svelte", "angular", "script"]
        for s in sekmeler[:-1]:
            assert f"{URL}/bannerlar" in s.icerik, (b.kod, s.kod)
            if b.tur == "sabit":
                assert ('role="note"' in s.icerik or b.stil == "kose") and "<iframe" not in s.icerik, (b.kod, s.kod)
                if b.stil == "klasik":
                    assert s.icerik.count("<svg") == 2 and "scaleX(-1)" in s.icerik, (b.kod, s.kod)
                    assert bn.ANMA_YAZISI in s.icerik
            else:
                assert f"{URL}/gomulu/guncel?bicim={b.bicim}&amp;renk={b.renk}" not in s.icerik  # ham & kalır
                assert f"{URL}/gomulu/guncel?bicim={b.bicim}&renk={b.renk}" in s.icerik, (b.kod, s.kod)
                assert "<iframe" in s.icerik


def test_bant_ve_kart_bicimleri():
    bant = bn.html_kodu(bn.banner_bul("kirmizi"), site_url=URL)
    assert "width:100%" in bant and "background:#e30a17" in bant
    kart = bn.html_kodu(bn.banner_bul("anma-kart"), site_url=URL)
    assert "width:300px" in kart and "height:250px" in kart and "flex-direction:column" in kart
    gk = bn.html_kodu(bn.banner_bul("guncel-kart"), site_url=URL)
    assert "width:300px" in gk and "max-width:100%" in gk  # dar kolonda oranını koruyarak küçülür
    assert "height:auto" in gk and "aspect-ratio:300 / 250" in gk
    gb = bn.html_kodu(bn.banner_bul("guncel-bant"), site_url=URL)
    assert "width:100%" in gb and "height:44px" in gb


def test_react_jsx():
    k = bn.react_kodu(bn.banner_bul("kirmizi"), site_url=URL)
    assert "export default function KirmiziBanner()" in k
    assert 'style={{ width: "100%", boxSizing: "border-box"' in k and 'style="' not in k
    assert 'viewBox="225 200 565 400"' in k and "<circle" in k and "/>" in k
    g = bn.react_kodu(bn.banner_bul("guncel-bant"), site_url=URL)
    assert "export default function GuncelBantBanner()" in g and "<iframe" in g and "/>" in g


def test_vue_svelte_angular():
    b = bn.banner_bul("koyu")
    assert bn.vue_kodu(b, site_url=URL).splitlines()[1] == "<template>"
    assert bn.svelte_kodu(b, site_url=URL).startswith("<!-- KoyuBanner.svelte")
    a = bn.angular_kodu(bn.banner_bul("guncel-kart"), site_url=URL)
    assert "selector: 'app-guncel-kart-banner'" in a and "export class GuncelKartBannerComponent" in a


def test_script_ve_bant_js():
    assert 'data-banner="guncel-kart"' in bn.script_kodu(bn.banner_bul("guncel-kart"), site_url=URL)
    js = bn.bant_js(URL)
    for kod in ("kirmizi", "koyu", "guncel-bant", "guncel-kart", "anma-kart"):
        assert f'"{kod}"' in js
    assert "data-banner" in js and "data-renk" in js and "insertBefore(el, s)" in js


def test_guncel_icerik_oncelik(session, sehit_ekle):
    bugun = date(2026, 10, 23)
    assert bn.guncel_icerik(session, bugun).mod == "anma"
    sehit_ekle(ad="Eski", soyad="Donum", gorev="Piyade Er", sehadet_tarihi=date(2016, 10, 23))
    i = bn.guncel_icerik(session, bugun)
    assert i.mod == "yildonumu" and i.kisiler[0].ad == "Piyade Er Eski DONUM"
    assert i.kisiler[0].ust_yazi == "Şehadetinin 10. yıl dönümü"
    sehit_ekle(ad="Yeni", soyad="Sehit", sehadet_tarihi=date(2026, 10, 20))
    i = bn.guncel_icerik(session, bugun)
    assert i.mod == "yeni" and [k.ad for k in i.kisiler] == ["Yeni SEHİT"] and i.yazi == bn.YENI_YAZISI
    sehit_ekle(ad="Bekleyen", soyad="Kayit", sehadet_tarihi=date(2026, 10, 22), durum="onay_bekliyor")
    assert [k.ad for k in bn.guncel_icerik(session, bugun).kisiler] == ["Yeni SEHİT"]


def test_yedi_gunden_eski_yeni_sayilmaz(session, sehit_ekle):
    sehit_ekle(ad="Gecen", soyad="Hafta", sehadet_tarihi=date(2026, 10, 16))
    assert bn.guncel_icerik(session, date(2026, 10, 23)).mod == "anma"


def test_yeni_stiller():
    url = URL
    fil = bn.html_kodu(bn.banner_bul("filigran"), site_url=url)
    assert "position:absolute" in fil and "opacity:0.22" in fil and "translateY(-50%)" in fil
    kur = bn.html_kodu(bn.banner_bul("kurdele"), site_url=url)
    assert kur.count("<path") == 2 and 'fill-rule="evenodd"' in kur and "background:#f5f2ea" in kur
    ser = bn.html_kodu(bn.banner_bul("serit"), site_url=url)
    assert "height:30px" in ser and "border-top:3px solid #e30a17" in ser
    pla = bn.html_kodu(bn.banner_bul("plaket"), site_url=url)
    assert "Ruhları şad olsun" in pla and bn.ALTIN in pla and "inset 0 0 0 7px" in pla
    roz = bn.html_kodu(bn.banner_bul("rozet"), site_url=url)
    assert "border-radius:50%" in roz and "width:140px" in roz
    # JSX'te tireli SVG özniteliği ve stil anahtarları
    rj = bn.react_kodu(bn.banner_bul("filigran"), site_url=url)
    assert "zIndex: " in rj and "position: " in rj


def test_rozet_script_bulundugu_yere():
    assert "bu satırın bulunduğu yere" in bn.script_kodu(bn.banner_bul("rozet"), site_url=URL)
    assert "b.bicim !== 'bant'" in bn.bant_js(URL)


def test_kose_kurdelesi_dort_kose():
    k = bn.banner_bul("kose-kurdele")
    assert [kod for kod, _ in bn.koseler(k)] == ["sag-ust", "sol-ust", "sag-alt", "sol-alt"]
    h = bn.html_kodu(k, site_url=URL, kose="sol-alt")
    assert "position:fixed" in h and "bottom:12px" in h and "left:12px" in h and "top:" not in h.split("style=")[1][:200]
    assert 'href="https://ornek.test/"' in h and 'title="Şehitlerimizi rahmetle anıyoruz"' in h
    assert "<path" in h and 'fill-rule="evenodd"' in h
    r = bn.react_kodu(k, site_url=URL, kose="sag-ust")
    assert 'position: "fixed"' in r and 'top: "12px"' in r and 'right: "12px"' in r and "zIndex" in r
    assert 'data-kose="sol-ust"' in bn.script_kodu(k, site_url=URL, kose="sol-ust")
    # önizleme kutuda mutlak konumlu
    assert "position:absolute" in bn.onizleme_html(k, "sag-alt")
    assert bn.koseler(bn.banner_bul("kirmizi")) == [("", "")]


def test_bant_js_kose_anahtarlari():
    js = bn.bant_js(URL)
    for kose in ("sag-ust", "sol-ust", "sag-alt", "sol-alt"):
        assert f'"kose-kurdele:{kose}"' in js
    assert "data-kose" in js and "document.body.appendChild(el)" in js
