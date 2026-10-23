"""Paylaşılabilir anma bannerları ve farklı ön yüz çatıları için gömme kodları.

Her banner tek bir öğe ağacından (`_El`) üretilir; aynı ağaç hem HTML (Vue, Svelte, Angular
şablonları da bunu kullanır) hem React JSX olarak yazılır, böylece tüm sürümler birebir aynı
çizimi verir. Stiller satır içidir: bannerı ekleyen sitede bizim CSS dosyamız bulunmaz.

İki tür vardır:
- sabit: anma yazısı; kod doğrudan sayfaya gömülür.
- guncel: yeni şehit / yıl dönümü / anma içeriği her gün değiştiği için bizim sitemizdeki
  `/gomulu/guncel` sayfası bir iframe ile gösterilir.
"""
import json
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app import repo

ANMA_YAZISI = "Şehitlerimizi rahmet, minnet ve saygıyla anıyoruz"
ANMA_EK = "Vatan sağ olsun"
YENI_YAZISI = "Allah'tan rahmet, ailesine ve aziz milletimize başsağlığı diliyoruz."
YILDONUMU_YAZISI = "Rahmet ve minnetle anıyoruz."
YENI_GUN_SAYISI = 7  # şehadeti son 7 günde olan kayıtlar "yeni şehit" sayılır

# Türk bayrağı oranları (bayrak SVG'sinden kırpılmış görünüm kutusu).
SVG_KUTU = "225 200 565 400"
YILDIZ = "583.334,400 764.235,458.779 652.431,304.894 652.431,495.106 764.235,341.221"
SERIF = "Georgia, 'Times New Roman', serif"
KART_EN, KART_BOY = 300, 250
BANT_BOY = 44


@dataclass(frozen=True)
class Renk:
    kod: str
    ad: str
    zemin: str
    yazi: str
    vurgu: str | None = None  # koyu zeminde alt/çerçeve çizgisi


RENKLER = {
    "kirmizi": Renk("kirmizi", "Kırmızı", "#e30a17", "#ffffff"),
    "koyu": Renk("koyu", "Koyu", "#0d0f12", "#e9e6df", vurgu="#e30a17"),
}


@dataclass(frozen=True)
class Banner:
    kod: str
    ad: str
    aciklama: str
    tur: str  # "sabit" | "guncel"
    bicim: str  # "bant" | "kart" | "rozet" (önizleme yerleşimi ve script'in ekleme yeri)
    renk: str  # RENKLER anahtarı
    stil: str = "klasik"  # sabit bannerın çizimi: klasik | filigran | kurdele | serit | plaket | rozet


BANNERLAR = [
    Banner("guncel-bant", "Güncel bant", "Yeni şehit varsa yalnızca onun adı; yoksa bugün yıl dönümü olan şehitlerin adları "
           "tek tek değişerek görünür; ikisi de yoksa anma yazısı. Sayfanın üstüne ya da altına.",
           "guncel", "bant", "kirmizi"),
    Banner("guncel-kart", "Güncel kart (300×250)", "Güncel bandın kenar çubuğu ve yazı arası için kart biçimi.",
           "guncel", "kart", "koyu"),
    Banner("kirmizi", "Kırmızı anma bandı", "Sitenin üstünde kullandığımız bant: kırmızı zemin, beyaz yazı ve ay-yıldız.",
           "sabit", "bant", "kirmizi"),
    Banner("koyu", "Koyu anma bandı", "Yas ve anma günleri için koyu zemin, beyaz ay-yıldız ve kırmızı vurgu.",
           "sabit", "bant", "koyu"),
    Banner("anma-kart", "Anma kartı (300×250)", "Kenar çubuğu, yazı arası ya da sayfa sonu için kart biçiminde anma.",
           "sabit", "kart", "kirmizi"),
    Banner("filigran", "Filigran bant", "Kırmızı zemin, ortada yazı, sağda büyük ve yarı saydam ay-yıldız filigranı.",
           "sabit", "bant", "kirmizi", stil="filigran"),
    Banner("kurdele", "Yas kurdelesi bandı", "Açık zemin, koyu yazı ve iki uçta siyah yas kurdelesi; sade ve ağırbaşlı.",
           "sabit", "bant", "kirmizi", stil="kurdele"),
    Banner("serit", "İnce şerit", "30 px yüksekliğinde, koyu zemin ve üstte kırmızı çizgi; içeriği bölmeden duyurur.",
           "sabit", "bant", "koyu", stil="serit"),
    Banner("plaket", "Anıt plaketi (300×250)", "Koyu zemin, altın renkli çift çerçeve ve klasik yazı; anıt plaketi görünümü.",
           "sabit", "kart", "koyu", stil="plaket"),
    Banner("kose-kurdele", "Köşe kurdelesi", "Yalnızca siyah yas kurdelesi; ekranın seçtiğiniz köşesine sabitlenir, "
           "sayfa kaydırılsa da yerinde kalır. Üzerine gelince anma yazısı görünür, tıklanınca sitemizi açar.",
           "sabit", "kose", "koyu", stil="kose"),
    Banner("rozet", "Rozet (140×140)", "Kırmızı daire içinde ay-yıldız ve kısa anma yazısı; köşelere ve kenar çubuğuna.",
           "sabit", "rozet", "kirmizi", stil="rozet"),
]

ALTIN = "#c9a45c"
KURDELE_YOLU = ("M12 2c-2.2 0-4 1.8-4 4 0 1.5.6 2.8 1.4 4L4 20l2.5 2 5.5-7 5.5 7 2.5-2-5.4-10"
                "C15.4 8.8 16 7.5 16 6c0-2.2-1.8-4-4-4zm0 2c1.1 0 2 .9 2 2 0 1-.4 2-1 3l-1 1.6-1-1.6"
                "c-.6-1-1-2-1-3 0-1.1.9-2 2-2z")


def banner_bul(kod: str) -> Banner | None:
    return next((b for b in BANNERLAR if b.kod == kod), None)


# --- Öğe ağacı ve iki yazıcı (HTML / JSX) ---------------------------------------------------

@dataclass
class _El:
    etiket: str
    ozellik: dict[str, str] = field(default_factory=dict)
    stil: dict[str, str] = field(default_factory=dict)
    cocuklar: list["_El | str"] = field(default_factory=list)


def _css(stil: dict[str, str]) -> str:
    return ";".join(f"{k}:{v}" for k, v in stil.items())


def _jsx_anahtar(k: str) -> str:
    bas, *kalan = k.split("-")
    return bas + "".join(p.capitalize() for p in kalan)


def _jsx_stil(stil: dict[str, str]) -> str:
    return "{{ " + ", ".join(f"{_jsx_anahtar(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in stil.items()) + " }}"


def _yaz(el: "_El | str", jsx: bool, girinti: int) -> str:
    bosluk = " " * girinti
    if isinstance(el, str):
        return bosluk + el
    parcalar = [el.etiket] + [f'{k}="{v}"' for k, v in el.ozellik.items()]
    if el.stil:
        parcalar.append(f"style={_jsx_stil(el.stil)}" if jsx else f'style="{_css(el.stil)}"')
    acilis = "<" + " ".join(parcalar)
    if not el.cocuklar:
        return f"{bosluk}{acilis} />" if jsx or el.etiket in ("circle", "polygon", "path") else f"{bosluk}{acilis}></{el.etiket}>"
    if el.etiket == "svg" or all(isinstance(c, str) for c in el.cocuklar):  # tek satır
        ic = "".join(_yaz(c, jsx, 0) for c in el.cocuklar)
        return f"{bosluk}{acilis}>{ic}</{el.etiket}>"
    ic = "\n".join(_yaz(c, jsx, girinti + 2) for c in el.cocuklar)
    return f"{bosluk}{acilis}>\n{ic}\n{bosluk}</{el.etiket}>"


def _ay_yildiz(renk: Renk, *, ters: bool, en: int = 34, boy: int = 24,
               zemin: str | None = None, dolgu: str = "#ffffff", ek_stil: dict[str, str] | None = None) -> _El:
    """Ay-yıldız; iç daire `zemin` rengindedir (varsayılan bannerın zemini), böylece hilal oluşur."""
    stil = {"flex": "none", "width": f"{en}px", "height": f"{boy}px", "color": zemin or renk.zemin}
    if ters:
        stil["transform"] = "scaleX(-1)"
    stil.update(ek_stil or {})
    return _El("svg", {"viewBox": SVG_KUTU, "aria-hidden": "true"}, stil, [
        _El("circle", {"cx": "425", "cy": "400", "r": "200", "fill": dolgu}),
        _El("circle", {"cx": "475", "cy": "400", "r": "160", "fill": "currentColor"}),
        _El("polygon", {"fill": dolgu, "points": YILDIZ}),
    ])


def _sabit_bant(renk: Renk) -> _El:
    stil = {
        "width": "100%", "box-sizing": "border-box", "background": renk.zemin, "color": renk.yazi,
        "display": "flex", "flex-wrap": "wrap", "align-items": "center", "justify-content": "center",
        "gap": "14px", "padding": "8px 16px", "margin": "0", "font-family": SERIF, "font-size": "18px",
        "font-weight": "600", "letter-spacing": "0.5px", "line-height": "1.3", "text-align": "center",
    }
    if renk.vurgu:
        stil["border-bottom"] = f"2px solid {renk.vurgu}"
    return _El("div", {"role": "note", "aria-label": "Anma"}, stil, [
        _ay_yildiz(renk, ters=False),
        _El("span", cocuklar=[f"{ANMA_YAZISI} · {ANMA_EK}"]),
        _ay_yildiz(renk, ters=True),
    ])


def _sabit_kart(renk: Renk) -> _El:
    stil = {
        "width": f"{KART_EN}px", "height": f"{KART_BOY}px", "max-width": "100%", "box-sizing": "border-box",
        "background": renk.zemin, "color": renk.yazi, "display": "flex", "flex-direction": "column",
        "align-items": "center", "justify-content": "center", "gap": "14px", "padding": "20px",
        "margin": "0", "border-radius": "8px", "font-family": SERIF, "text-align": "center",
    }
    if renk.vurgu:
        stil["border"] = f"2px solid {renk.vurgu}"
    return _El("div", {"role": "note", "aria-label": "Anma"}, stil, [
        _El("div", stil={"display": "flex", "gap": "18px"}, cocuklar=[
            _ay_yildiz(renk, ters=False, en=44, boy=31), _ay_yildiz(renk, ters=True, en=44, boy=31),
        ]),
        _El("div", stil={"font-size": "21px", "font-weight": "600", "line-height": "1.3"}, cocuklar=[ANMA_YAZISI]),
        _El("div", stil={"font-size": "13px", "letter-spacing": "2px", "text-transform": "uppercase", "opacity": "0.85"},
            cocuklar=[ANMA_EK]),
    ])


def guncel_adresi(b: Banner, site_url: str = "") -> str:
    return f"{site_url.rstrip('/')}/gomulu/guncel?" + urlencode({"bicim": b.bicim, "renk": b.renk})


def _guncel_iframe(b: Banner, site_url: str) -> _El:
    if b.bicim == "kart":
        stil = {"width": f"{KART_EN}px", "height": f"{KART_BOY}px", "max-width": "100%", "border": "0", "display": "block"}
    else:
        stil = {"width": "100%", "height": f"{BANT_BOY}px", "border": "0", "display": "block"}
    return _El("iframe", {"src": guncel_adresi(b, site_url), "title": "Şehitlerimizi anıyoruz", "loading": "lazy"}, stil)


def _filigran_bant(renk: Renk) -> _El:
    return _El("div", {"role": "note", "aria-label": "Anma"}, {
        "position": "relative", "overflow": "hidden", "width": "100%", "box-sizing": "border-box",
        "background": renk.zemin, "color": renk.yazi, "padding": "14px 120px 14px 20px", "margin": "0",
        "font-family": SERIF, "text-align": "center",
    }, [
        _El("div", stil={"position": "relative", "z-index": "1", "font-size": "20px", "font-weight": "600",
                         "line-height": "1.3", "letter-spacing": "0.3px"}, cocuklar=[ANMA_YAZISI]),
        _El("div", stil={"position": "relative", "z-index": "1", "font-size": "12px", "letter-spacing": "3px",
                         "text-transform": "uppercase", "opacity": "0.85", "margin-top": "4px"}, cocuklar=[ANMA_EK]),
        _ay_yildiz(renk, ters=False, en=150, boy=106, ek_stil={
            "position": "absolute", "right": "-18px", "top": "50%", "transform": "translateY(-50%)", "opacity": "0.22"}),
    ])


def _kurdele(en: int = 22) -> _El:
    return _El("svg", {"viewBox": "0 0 24 24", "aria-hidden": "true"},
               {"flex": "none", "width": f"{en}px", "height": f"{en}px"},
               [_El("path", {"fill": "#111111", "fill-rule": "evenodd", "d": KURDELE_YOLU})])


def _kurdele_bant() -> _El:
    return _El("div", {"role": "note", "aria-label": "Anma"}, {
        "width": "100%", "box-sizing": "border-box", "background": "#f5f2ea", "color": "#1c1c1c",
        "display": "flex", "flex-wrap": "wrap", "align-items": "center", "justify-content": "center",
        "gap": "14px", "padding": "9px 16px", "margin": "0", "border-top": "1px solid #d9d3c4",
        "border-bottom": "1px solid #d9d3c4", "font-family": SERIF, "font-size": "17px",
        "line-height": "1.3", "text-align": "center",
    }, [
        _kurdele(),
        _El("span", cocuklar=["Aziz şehitlerimizi rahmet ve minnetle anıyoruz"]),
        _kurdele(),
    ])


def _ince_serit(renk: Renk) -> _El:
    return _El("div", {"role": "note", "aria-label": "Anma"}, {
        "width": "100%", "box-sizing": "border-box", "height": "30px", "background": renk.zemin,
        "color": renk.yazi, "border-top": "3px solid #e30a17", "display": "flex", "align-items": "center",
        "justify-content": "center", "gap": "8px", "padding": "0 12px", "margin": "0",
        "font-family": "system-ui, -apple-system, 'Segoe UI', sans-serif", "font-size": "13px",
        "letter-spacing": "0.3px", "white-space": "nowrap", "overflow": "hidden",
    }, [
        _ay_yildiz(renk, ters=False, en=18, boy=13),
        _El("span", stil={"overflow": "hidden", "text-overflow": "ellipsis"},
            cocuklar=["Şehitlerimizi rahmetle anıyoruz · Vatan sağ olsun"]),
    ])


def _plaket() -> _El:
    zemin = "#14171c"
    renk = RENKLER["koyu"]
    return _El("div", {"role": "note", "aria-label": "Anma"}, {
        "width": f"{KART_EN}px", "height": f"{KART_BOY}px", "max-width": "100%", "box-sizing": "border-box",
        "background": zemin, "color": "#e9e6df", "display": "flex", "flex-direction": "column",
        "align-items": "center", "justify-content": "center", "gap": "10px", "padding": "22px", "margin": "0",
        "border": f"1px solid {ALTIN}", "box-shadow": f"inset 0 0 0 6px {zemin}, inset 0 0 0 7px {ALTIN}",
        "font-family": SERIF, "text-align": "center",
    }, [
        _ay_yildiz(renk, ters=False, en=40, boy=28, zemin=zemin),
        _El("div", stil={"color": ALTIN, "font-size": "13px", "letter-spacing": "4px", "text-transform": "uppercase"},
            cocuklar=["Şehitlerimiz"]),
        _El("div", stil={"font-size": "20px", "font-weight": "600", "line-height": "1.3"},
            cocuklar=["Rahmet, minnet ve saygıyla anıyoruz"]),
        _El("div", stil={"width": "48px", "height": "1px", "background": ALTIN}),
        _El("div", stil={"font-size": "14px", "font-style": "italic", "opacity": "0.85"}, cocuklar=["Ruhları şad olsun"]),
    ])


def _rozet(renk: Renk) -> _El:
    return _El("div", {"role": "note", "aria-label": "Anma"}, {
        "width": "140px", "height": "140px", "box-sizing": "border-box", "border-radius": "50%",
        "background": renk.zemin, "color": renk.yazi, "border": "3px solid #ffffff",
        "box-shadow": "0 0 0 2px #e30a17", "display": "flex", "flex-direction": "column",
        "align-items": "center", "justify-content": "center", "gap": "6px", "padding": "14px", "margin": "0",
        "font-family": SERIF, "text-align": "center",
    }, [
        _ay_yildiz(renk, ters=False, en=46, boy=32),
        _El("div", stil={"font-size": "12.5px", "font-weight": "700", "line-height": "1.25", "letter-spacing": "0.5px",
                         "text-transform": "uppercase"}, cocuklar=["Şehitlerimizi unutmayacağız"]),
    ])


KOSELER = {  # köşe kurdelesi yerleşimleri
    "sag-ust": ("Sağ üst", {"top": "12px", "right": "12px"}),
    "sol-ust": ("Sol üst", {"top": "12px", "left": "12px"}),
    "sag-alt": ("Sağ alt", {"bottom": "12px", "right": "12px"}),
    "sol-alt": ("Sol alt", {"bottom": "12px", "left": "12px"}),
}
VARSAYILAN_KOSE = "sag-ust"
KOSE_KURDELE_YAZISI = "Şehitlerimizi rahmetle anıyoruz"


def _kose_kurdelesi(kose: str, site_url: str, *, onizleme: bool = False) -> _El:
    """Ekranın bir köşesine sabitlenen siyah yas kurdelesi; tıklanınca sitemizi açar.

    Önizlemede `position:absolute` kullanılır ki kurdele önizleme kutusunun köşesine otursun.
    """
    stil = {"position": "absolute" if onizleme else "fixed", **KOSELER[kose][1],
            "z-index": "2147483647", "display": "block", "width": "52px", "height": "52px",
            "line-height": "0", "filter": "drop-shadow(0 1px 2px rgba(0,0,0,0.35))"}
    kurdele = _El("svg", {"viewBox": "0 0 24 24", "aria-hidden": "true"}, {"width": "52px", "height": "52px"},
                  [_El("path", {"fill": "#111111", "fill-rule": "evenodd", "stroke": "#ffffff",
                                "stroke-width": "0.6", "stroke-linejoin": "round", "d": KURDELE_YOLU})])
    return _El("a", {"href": f"{site_url.rstrip('/')}/", "target": "_blank", "rel": "noopener",
                     "title": KOSE_KURDELE_YAZISI, "aria-label": KOSE_KURDELE_YAZISI}, stil, [kurdele])


def koseler(b: Banner) -> list[tuple[str, str]]:
    """Köşe seçeneği olan bannerlar için (kod, ad) listesi; diğerleri için tek boş seçenek."""
    if b.stil == "kose":
        return [(k, ad) for k, (ad, _) in KOSELER.items()]
    return [("", "")]


def _agac(b: Banner, site_url: str = "", kose: str = VARSAYILAN_KOSE, *, onizleme: bool = False) -> _El:
    renk = RENKLER[b.renk]
    if b.tur == "guncel":
        return _guncel_iframe(b, site_url)
    if b.stil == "kose":
        return _kose_kurdelesi(kose if kose in KOSELER else VARSAYILAN_KOSE, site_url, onizleme=onizleme)
    cizim = {
        "filigran": lambda: _filigran_bant(renk),
        "kurdele": _kurdele_bant,
        "serit": lambda: _ince_serit(renk),
        "plaket": _plaket,
        "rozet": lambda: _rozet(renk),
    }.get(b.stil)
    if cizim:
        return cizim()
    return _sabit_kart(renk) if b.bicim == "kart" else _sabit_bant(renk)


# --- Kod üreticiler ------------------------------------------------------------------------

def _kaynak(site_url: str) -> str:
    return f"{site_url.rstrip('/')}/bannerlar"


def onizleme_html(b: Banner, kose: str = VARSAYILAN_KOSE) -> str:
    """Bannerlar sayfasındaki canlı önizleme (göreli iframe adresiyle; köşe kurdelesi kutu içinde)."""
    return _yaz(_agac(b, "", kose, onizleme=True), jsx=False, girinti=0)


def html_kodu(b: Banner, *, site_url: str, kose: str = VARSAYILAN_KOSE) -> str:
    return (f"<!-- Vatan Sağ Olsun — {b.ad} — {_kaynak(site_url)} -->\n"
            + _yaz(_agac(b, site_url, kose), jsx=False, girinti=0))


def _bilesen_adi(b: Banner) -> str:
    return "".join(p.capitalize() for p in b.kod.split("-")) + "Banner"


def react_kodu(b: Banner, *, site_url: str, kose: str = VARSAYILAN_KOSE) -> str:
    return (f"// Vatan Sağ Olsun — {b.ad} — {_kaynak(site_url)}\n"
            f"export default function {_bilesen_adi(b)}() {{\n"
            "  return (\n" + _yaz(_agac(b, site_url, kose), jsx=True, girinti=4) + "\n  );\n}\n")


def vue_kodu(b: Banner, *, site_url: str, kose: str = VARSAYILAN_KOSE) -> str:
    return (f"<!-- {_bilesen_adi(b)}.vue — Vatan Sağ Olsun — {_kaynak(site_url)} -->\n"
            "<template>\n" + _yaz(_agac(b, site_url, kose), jsx=False, girinti=2) + "\n</template>\n")


def svelte_kodu(b: Banner, *, site_url: str, kose: str = VARSAYILAN_KOSE) -> str:
    return (f"<!-- {_bilesen_adi(b)}.svelte — Vatan Sağ Olsun — {_kaynak(site_url)} -->\n"
            + _yaz(_agac(b, site_url, kose), jsx=False, girinti=0) + "\n")


def angular_kodu(b: Banner, *, site_url: str, kose: str = VARSAYILAN_KOSE) -> str:
    secici = "app-" + b.kod + "-banner"
    sablon = _yaz(_agac(b, site_url, kose), jsx=False, girinti=4).replace("`", "\\`")
    return (f"// {b.kod}-banner.component.ts — Vatan Sağ Olsun — {_kaynak(site_url)}\n"
            "import { Component } from '@angular/core';\n\n"
            "@Component({\n"
            f"  selector: '{secici}',\n"
            "  standalone: true,\n"
            "  template: `\n" + sablon + "\n  `,\n"
            "})\n"
            f"export class {_bilesen_adi(b)}Component {{}}\n")


def script_kodu(b: Banner, *, site_url: str, kose: str = VARSAYILAN_KOSE) -> str:
    kok = site_url.rstrip("/")
    if b.stil == "kose":
        return (f"<!-- {b.ad}: ekranın {KOSELER[kose][0].lower()} köşesine sabitlenir -->\n"
                f'<script src="{kok}/bant.js" data-banner="{b.kod}" data-kose="{kose}" defer></script>')
    nereye = "sayfanın en üstüne" if b.bicim == "bant" else "bu satırın bulunduğu yere"
    return (f"<!-- {b.ad}: {nereye} yerleşir -->\n"
            f'<script src="{kok}/bant.js" data-banner="{b.kod}" defer></script>')


def bant_js(site_url: str) -> str:
    """`<script src=".../bant.js" data-banner="<kod>">` ile eklenen siteye bannerı yerleştirir.

    Bant biçimi sayfanın en üstüne; kart ve rozet biçimleri script etiketinin bulunduğu yere;
    köşe kurdelesi (`data-kose`) sabit konumlu olarak sayfanın sonuna eklenir.
    Eski `data-renk="kirmizi|koyu"` kullanımı da desteklenir.
    """
    bannerlar = {}
    for b in BANNERLAR:
        for kose, _ in koseler(b):
            anahtar = f"{b.kod}:{kose}" if kose else b.kod
            bannerlar[anahtar] = {"html": _yaz(_agac(b, site_url, kose or VARSAYILAN_KOSE), jsx=False, girinti=0),
                                  "bicim": b.bicim}
    return ("(function () {\n"
            "  var s = document.currentScript;\n"
            "  var kod = (s && (s.getAttribute('data-banner') || s.getAttribute('data-renk'))) || 'kirmizi';\n"
            "  var kose = (s && s.getAttribute('data-kose')) || 'sag-ust';\n"
            f"  var bannerlar = {json.dumps(bannerlar, ensure_ascii=False)};\n"
            "  var b = bannerlar[kod + ':' + kose] || bannerlar[kod] || bannerlar.kirmizi;\n"
            "  function ekle() {\n"
            "    var kap = document.createElement('div');\n"
            "    kap.innerHTML = b.html;\n"
            "    var el = kap.firstElementChild;\n"
            "    if (b.bicim === 'kose') { document.body.appendChild(el); }\n"
            "    else if (b.bicim !== 'bant' && s && s.parentNode) { s.parentNode.insertBefore(el, s); }\n"
            "    else { document.body.insertBefore(el, document.body.firstChild); }\n"
            "  }\n"
            "  if (document.body) { ekle(); } else { document.addEventListener('DOMContentLoaded', ekle); }\n"
            "})();\n")


@dataclass(frozen=True)
class KodSekmesi:
    kod: str
    ad: str
    icerik: str


def kod_sekmeleri(b: Banner, site_url: str, kose: str = VARSAYILAN_KOSE) -> list[KodSekmesi]:
    return [
        KodSekmesi("html", "HTML", html_kodu(b, site_url=site_url, kose=kose)),
        KodSekmesi("react", "React", react_kodu(b, site_url=site_url, kose=kose)),
        KodSekmesi("vue", "Vue", vue_kodu(b, site_url=site_url, kose=kose)),
        KodSekmesi("svelte", "Svelte", svelte_kodu(b, site_url=site_url, kose=kose)),
        KodSekmesi("angular", "Angular", angular_kodu(b, site_url=site_url, kose=kose)),
        KodSekmesi("script", "Tek satır script", script_kodu(b, site_url=site_url, kose=kose)),
    ]


# --- Güncel içerik ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GuncelKisi:
    ad: str  # görev + görünen ad
    url: str
    ust_yazi: str  # ör. "Şehidimiz" / "Şehadetinin 10. yıl dönümü"


@dataclass(frozen=True)
class GuncelIcerik:
    mod: str  # "yeni" | "yildonumu" | "anma"
    kisiler: list[GuncelKisi]
    yazi: str


def _kisi_adi(sehit) -> str:
    return f"{sehit.gorev} {sehit.gorunen_ad}" if sehit.gorev else sehit.gorunen_ad


def guncel_icerik(s: Session, bugun: date) -> GuncelIcerik:
    """Yeni şehit (son 7 gün) varsa onlar; yoksa bugün yıl dönümü olanlar; yoksa anma."""
    yeniler = repo.yeni_sehitler(s, bugun, gun_sayisi=YENI_GUN_SAYISI)
    if yeniler:
        return GuncelIcerik("yeni", [GuncelKisi(_kisi_adi(k), k.url, "Şehidimiz") for k in yeniler], YENI_YAZISI)
    artik = bugun.year % 4 == 0 and (bugun.year % 100 != 0 or bugun.year % 400 == 0)
    donumler = [k for k in repo.yil_donumu(s, bugun.month, bugun.day, artik_yil=artik) if k.yil < bugun.year]
    if donumler:
        return GuncelIcerik("yildonumu", [
            GuncelKisi(_kisi_adi(k), k.url, f"Şehadetinin {bugun.year - k.yil}. yıl dönümü") for k in donumler[:20]
        ], YILDONUMU_YAZISI)
    return GuncelIcerik("anma", [], ANMA_YAZISI)
