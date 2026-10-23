"""Herkese açık site sayfaları."""
import calendar
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
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
    if ham and ham.isdigit() and 1 <= int(ham) <= 9999:
        return str(int(ham)), int(ham)
    return str(varsayilan), varsayilan


def _sayfa_coz(ham: str | None) -> int:
    try:
        return max(int(ham), 1) if ham is not None else 1
    except ValueError:
        return 1


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

