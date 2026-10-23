"""Herkese açık site sayfaları."""
import calendar
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import repo
from app.dates import bugun
from app.db import get_session
from app.models import Hassasiyet, Sehit

ADET = 25
AYLAR = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
router = APIRouter()
Oturum = Annotated[Session, Depends(get_session)]


def tarih_metni(sehit: Sehit) -> str:
    if sehit.tarih_hassasiyeti == Hassasiyet.tam and sehit.sehadet_tarihi:
        return sehit.sehadet_tarihi.strftime("%d.%m.%Y")
    if sehit.tarih_hassasiyeti == Hassasiyet.yil and sehit.yil:
        return str(sehit.yil)
    return ""


templates.env.filters["tarih_metni"] = tarih_metni


def _yil_coz(ham: str | None, varsayilan: int) -> tuple[str, repo.YilFiltre]:
    if ham == "tumu":
        return "tumu", None
    if ham == "2000-oncesi":
        return "2000-oncesi", "2000-oncesi"
    if ham and ham.isascii() and ham.isdigit() and len(ham) <= 4 and 1 <= int(ham) <= 9999:
        return str(int(ham)), int(ham)
    return str(varsayilan), varsayilan


def _sayfa_coz(ham: str | None) -> int:
    if ham is None or not (ham.isascii() and ham.isdigit()) or len(ham) > 6:
        return 1
    return max(int(ham), 1)


def _sayfa_numaralari(sayfa: int, sayfa_sayisi: int) -> list[int | None]:
    numaralar: list[int | None] = []
    for i in range(1, sayfa_sayisi + 1):
        if i <= 3 or i > sayfa_sayisi - 2 or abs(i - sayfa) <= 1:
            numaralar.append(i)
        elif numaralar[-1] is not None:
            numaralar.append(None)
    return numaralar


@router.get("/")
def ana_sayfa(
    request: Request,
    s: Oturum,
    yil: str | None = None,
    q: str | None = None,
    sayfa: str | None = None,
):
    bugun_tarihi = bugun()
    secili_yil, yil_filtre = _yil_coz(yil, bugun_tarihi.year)
    q = (q or "").strip()
    sayfa_no = _sayfa_coz(sayfa)

    sonuc = repo.listele(s, yil=yil_filtre, q=q or None, sayfa=sayfa_no, adet=ADET)
    sayfa_sayisi = max(1, -(-sonuc.toplam // ADET))

    bugun_kayitlari = [
        {"kayit": k, "yil_donumu": bugun_tarihi.year - k.yil}
        for k in repo.yil_donumu(
            s, bugun_tarihi.month, bugun_tarihi.day,
            artik_yil=calendar.isleap(bugun_tarihi.year),
        )
    ]

    yillar = [(str(y), str(y)) for y in range(bugun_tarihi.year, 1999, -1)]
    yillar += [("2000-oncesi", "2000 öncesi"), ("tumu", "Tümü")]

    def adres(**degisenler) -> str:
        parametreler = {"yil": secili_yil, **degisenler}
        if q:
            parametreler["q"] = q
        return "/?" + urlencode(parametreler)

    sayfalar = [
        (n, adres(sayfa=n) if n else None) for n in _sayfa_numaralari(sayfa_no, sayfa_sayisi)
    ]
    yil_baglantilari = [(etiket, adres(yil=deger), deger == secili_yil) for deger, etiket in yillar]
    etiket_sozlugu = dict(yillar)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "bugun_tarihi": bugun_tarihi,
            "bugun_metni": f"{bugun_tarihi.day} {AYLAR[bugun_tarihi.month - 1]}",
            "bugun_kayitlari": bugun_kayitlari,
            "istatistik": repo.istatistik(s, bugun_tarihi),
            "yillar": yil_baglantilari,
            "secili_yil": secili_yil,
            "secili_etiket": etiket_sozlugu.get(secili_yil, secili_yil),
            "q": q,
            "sayfa_sonucu": sonuc,
            "sayfa": sayfa_no,
            "sayfa_sayisi": sayfa_sayisi,
            "sayfalar": sayfalar,
        },
    )


def _tam_sayi(ham: str | None, en_cok_hane: int) -> int | None:
    if ham is None or not (ham.isascii() and ham.isdigit()) or len(ham) > en_cok_hane:
        return None
    return int(ham)


@router.get("/sehit/{slug_id}")
def sehit_sayfasi(request: Request, slug_id: str, s: Oturum):
    _, ayrac, ham_id = slug_id.rpartition("-")
    sehit_id = _tam_sayi(ham_id, 9) if ayrac else None
    sehit = repo.getir(s, sehit_id) if sehit_id is not None else None
    if sehit is None:
        raise HTTPException(status_code=404)
    if request.url.path != sehit.url:
        return RedirectResponse(sehit.url, status_code=301)
    kaynaklar = [
        k for k in sehit.kaynaklar if k.url and k.url.lower().startswith(("http://", "https://"))
    ]
    return templates.TemplateResponse(
        request,
        "sehit.html",
        {"sehit": sehit, "kaynaklar": kaynaklar, "tarih": tarih_metni(sehit)},
    )


def _ay_gun_coz(ay: str | None, gun: str | None, bugun_tarihi) -> tuple[int, int]:
    a, g = _tam_sayi(ay, 2), _tam_sayi(gun, 2)
    if a is not None and g is not None and 1 <= a <= 12 and 1 <= g <= calendar.monthrange(2000, a)[1]:
        return a, g
    return bugun_tarihi.month, bugun_tarihi.day


@router.get("/yil-donumleri")
def yil_donumleri(request: Request, s: Oturum, ay: str | None = None, gun: str | None = None):
    bugun_tarihi = bugun()
    a, g = _ay_gun_coz(ay, gun, bugun_tarihi)
    kayitlar = [
        {"kayit": k, "yil_donumu": bugun_tarihi.year - k.yil}
        for k in repo.yil_donumu(s, a, g, artik_yil=calendar.isleap(bugun_tarihi.year))
    ]
    metin = f"{g} {AYLAR[a - 1]}"
    bugun_mu = (a, g) == (bugun_tarihi.month, bugun_tarihi.day)
    return templates.TemplateResponse(
        request,
        "yil_donumleri.html",
        {
            "ay": a,
            "gun": g,
            "aylar": list(enumerate(AYLAR, start=1)),
            "gunler": range(1, 32),
            "bugun_kayitlari": kayitlar,
            "bugun_metni": metin,
            "baslik": f"Bugün, {metin}" if bugun_mu else metin,
            "ay_adi": AYLAR[a - 1],
        },
    )


@router.get("/hakkinda")
def hakkinda(request: Request):
    return templates.TemplateResponse(request, "hakkinda.html", {})


MESAJ_EN_COK = 2000
ILETISIM_EN_COK = 200


def _bildir_sehit(s: Session, ham: str | None) -> Sehit | None:
    sehit_id = _tam_sayi((ham or "").strip(), 9)
    return repo.getir(s, sehit_id) if sehit_id is not None else None


@router.get("/bildir")
def bildir_formu(request: Request, s: Oturum, sehit: str | None = None):
    return templates.TemplateResponse(
        request,
        "bildir.html",
        {"sehit": _bildir_sehit(s, sehit), "mesaj": "", "iletisim": "", "hata": None},
    )


@router.post("/bildir")
def bildir_gonder(
    request: Request,
    s: Oturum,
    mesaj: Annotated[str, Form()] = "",
    iletisim: Annotated[str, Form()] = "",
    sehit: Annotated[str, Form()] = "",
):
    mesaj, iletisim = mesaj.strip(), iletisim.strip()
    kayit = _bildir_sehit(s, sehit)
    hata = None
    if not mesaj:
        hata = "Lütfen bir mesaj yazın."
    elif len(mesaj) > MESAJ_EN_COK:
        hata = f"Mesaj en fazla {MESAJ_EN_COK} karakter olabilir."
    elif len(iletisim) > ILETISIM_EN_COK:
        hata = f"İletişim bilgisi en fazla {ILETISIM_EN_COK} karakter olabilir."
    if hata:
        return templates.TemplateResponse(
            request,
            "bildir.html",
            {"sehit": kayit, "mesaj": mesaj, "iletisim": iletisim, "hata": hata},
            status_code=400,
        )
    repo.bildirim_ekle(
        s, mesaj=mesaj, iletisim=iletisim or None, sehit_id=kayit.id if kayit else None
    )
    return templates.TemplateResponse(request, "bildir_tesekkur.html", {})

