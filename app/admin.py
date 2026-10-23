"""Onay paneli: giriş, oturum, CSRF, onay iş akışı."""
import secrets
from datetime import datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import bcrypt
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from slowapi import Limiter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import repo
from app.db import get_session
from app.models import Bildirim, Durum, Hassasiyet, Kategori, Sehit
from app.schemas import SehitVeri

GIRIS_ADRESI = "/panel/giris"
BCRYPT_EN_COK_BAYT = 72
GIRIS_SINIRI = "10/minute"
VARSAYILAN_SECRET = "degistir"
SECRET_EN_AZ_UZUNLUK = 32
KAYNAK_METIN_UZUNLUGU = 300
YAYINDA_SAYFA_ADEDI = 50
SAYISAL_ALANLAR = {"yil": "Yıl", "dogum_yili": "Doğum yılı"}
FORM_ALANLARI = (
    "ad", "soyad", "lakap", "tarih_hassasiyeti", "sehadet_tarihi", "yil", "gorev", "kategori",
    "kurum", "memleket", "baba_adi", "dogum_yili", "donem", "kaynak_kodu",
)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def guvenli_url(url: str | None) -> str | None:
    """Yalnızca http(s) adresleri bağlantı olur (javascript: vb. elenir)."""
    if not url:
        return None
    url = url.strip()
    ayrik = urlparse(url)
    return url if ayrik.scheme in ("http", "https") and ayrik.netloc else None


def kisalt(metin: str | None) -> str:
    return (metin or "")[:KAYNAK_METIN_UZUNLUGU]


templates.env.filters["guvenli_url"] = guvenli_url
templates.env.filters["kisalt"] = kisalt


def sifre_hashle(sifre: str) -> str:
    return bcrypt.hashpw(sifre.encode(), bcrypt.gensalt()).decode()


def sifre_dogru(sifre: str, hash_: str) -> bool:
    ham = sifre.encode()
    if not hash_ or len(ham) > BCRYPT_EN_COK_BAYT:
        return False
    try:
        return bcrypt.checkpw(ham, hash_.encode())  # sabit zamanlı karşılaştırma
    except ValueError:  # bozuk hash
        return False


class GirisGerekli(HTTPException):
    """Oturum yoksa `/panel/giris` adresine 303 yönlendirmesi."""

    def __init__(self) -> None:
        super().__init__(status_code=303, headers={"Location": GIRIS_ADRESI})


def giris_gerekli_isleyici(request: Request, istisna: GirisGerekli) -> RedirectResponse:
    return RedirectResponse(GIRIS_ADRESI, status_code=303)


def secret_zayif_mi(ayarlar) -> bool:
    """Varsayılan ya da kısa SECRET_KEY ile imzalanan oturum çerezi taklit edilebilir."""
    anahtar = ayarlar.secret_key
    return anahtar == VARSAYILAN_SECRET or len(anahtar) < SECRET_EN_AZ_UZUNLUK


def yonetici_gerekli(request: Request) -> str:
    if secret_zayif_mi(request.app.state.settings):
        raise GirisGerekli()  # kapalı durumda hiçbir oturum geçerli sayılmaz
    kullanici = request.session.get("kullanici")
    if not kullanici:
        raise GirisGerekli()
    return kullanici


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = request.session["csrf"] = secrets.token_urlsafe(32)
    return token


def csrf_dogrula(request: Request, token: str) -> None:
    beklenen = request.session.get("csrf")
    if not beklenen or not secrets.compare_digest(token.encode(), beklenen.encode()):
        raise HTTPException(status_code=403, detail="CSRF doğrulaması başarısız")


Yonetici = Annotated[str, Depends(yonetici_gerekli)]
Oturum = Annotated[Session, Depends(get_session)]


def form_oku(
    ad: Annotated[str, Form()] = "",
    soyad: Annotated[str, Form()] = "",
    lakap: Annotated[str, Form()] = "",
    tarih_hassasiyeti: Annotated[str, Form()] = "tam",
    sehadet_tarihi: Annotated[str, Form()] = "",
    yil: Annotated[str, Form()] = "",
    gorev: Annotated[str, Form()] = "",
    kategori: Annotated[str, Form()] = "diger",
    kurum: Annotated[str, Form()] = "",
    memleket: Annotated[str, Form()] = "",
    baba_adi: Annotated[str, Form()] = "",
    dogum_yili: Annotated[str, Form()] = "",
    donem: Annotated[str, Form()] = "",
    kaynak_kodu: Annotated[str, Form()] = "",
    resmi_teyit: Annotated[str | None, Form()] = None,
    isimsiz: Annotated[str | None, Form()] = None,
) -> dict:
    return dict(
        ad=ad, soyad=soyad, lakap=lakap, tarih_hassasiyeti=tarih_hassasiyeti,
        sehadet_tarihi=sehadet_tarihi, yil=yil, gorev=gorev, kategori=kategori, kurum=kurum,
        memleket=memleket, baba_adi=baba_adi, dogum_yili=dogum_yili, donem=donem,
        kaynak_kodu=kaynak_kodu, resmi_teyit=resmi_teyit is not None, isimsiz=isimsiz is not None,
    )


FormVerisi = Annotated[dict, Depends(form_oku)]


def _bos_none(deger: str | None) -> str | None:
    deger = (deger or "").strip()
    return deger or None


def _hata_metni(hata: ValidationError) -> str:
    mesajlar = []
    for e in hata.errors():
        if e["type"] == "value_error":
            mesajlar.append(str(e["ctx"]["error"]))
        else:
            alan = ".".join(str(k) for k in e["loc"]) or "form"
            mesajlar.append(f"'{alan}' alanı geçersiz veya eksik.")
    return " ".join(mesajlar)


def veri_olustur(ham: dict, varsayilan_kaynak: str | None) -> SehitVeri:
    """Form metinlerinden `SehitVeri` kurar; hatada ValueError (Türkçe mesaj) fırlatır."""
    alanlar: dict = {alan: _bos_none(ham[alan]) for alan in FORM_ALANLARI}
    for alan, etiket in SAYISAL_ALANLAR.items():
        deger = alanlar[alan]
        if deger is not None:
            if not (deger.isascii() and deger.isdigit()) or len(deger) > 4:
                raise ValueError(f"{etiket} dört haneye kadar bir sayı olmalıdır.")
            alanlar[alan] = int(deger)
    tarih = alanlar["sehadet_tarihi"]
    if tarih is not None:
        try:
            if not tarih.isascii():
                raise ValueError
            alanlar["sehadet_tarihi"] = datetime.strptime(tarih, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Şehadet tarihi YYYY-AA-GG biçiminde olmalıdır.") from None
    alanlar["kaynak_kodu"] = alanlar["kaynak_kodu"] or varsayilan_kaynak
    alanlar["tarih_hassasiyeti"] = alanlar["tarih_hassasiyeti"] or Hassasiyet.tam
    alanlar["kategori"] = alanlar["kategori"] or Kategori.diger
    alanlar["resmi_teyit"] = ham["resmi_teyit"]
    alanlar["isimsiz"] = ham["isimsiz"]
    try:
        return SehitVeri(**alanlar)
    except ValidationError as hata:
        raise ValueError(_hata_metni(hata)) from None


def _form_degerleri(sehit: Sehit | None) -> dict:
    if sehit is None:
        return {"tarih_hassasiyeti": "tam", "kategori": "diger", "resmi_teyit": False,
                "isimsiz": False}
    deger = {a: getattr(sehit, a) for a in FORM_ALANLARI}
    deger["sehadet_tarihi"] = sehit.sehadet_tarihi.isoformat() if sehit.sehadet_tarihi else ""
    deger["tarih_hassasiyeti"] = Hassasiyet(sehit.tarih_hassasiyeti).value
    deger["kategori"] = Kategori(sehit.kategori).value
    deger = {a: ("" if v is None else v) for a, v in deger.items()}
    deger["resmi_teyit"] = sehit.resmi_teyit
    deger["isimsiz"] = sehit.isimsiz
    return deger


def _giris_sayfasi(request: Request, hata: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request, "panel/giris.html", {"hata": hata}, status_code=status_code
    )


def _sehit_getir(s: Session, sehit_id: int) -> Sehit:
    sehit = repo.getir(s, sehit_id, sadece_yayinda=False)
    if sehit is None:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    return sehit


def _liste_sayfasi(request: Request, kullanici: str, **baglam):
    return templates.TemplateResponse(
        request, "panel/liste.html",
        {"kullanici": kullanici, "csrf": csrf_token(request), **baglam},
    )


def _duzenle_sayfasi(
    request: Request, kullanici: str, sehit: Sehit | None, degerler: dict,
    hata: str | None = None, status_code: int = 200,
):
    return templates.TemplateResponse(
        request, "panel/duzenle.html",
        {
            "kullanici": kullanici, "csrf": csrf_token(request), "sehit": sehit,
            "f": degerler, "hata": hata,
            "kategoriler": list(Kategori), "hassasiyetler": list(Hassasiyet),
        },
        status_code=status_code,
    )


def panel_router_olustur(limiter: Limiter) -> APIRouter:
    # Yönlendirici her uygulama için yeniden kurulur: sınırlayıcı sızmaz (R6).
    router = APIRouter(prefix="/panel")

    @router.get("/giris")
    def giris_formu(request: Request):
        if request.session.get("kullanici"):
            return RedirectResponse("/panel", status_code=303)
        return _giris_sayfasi(request)

    @router.post("/giris")
    @limiter.limit(GIRIS_SINIRI)
    def giris(
        request: Request,
        kullanici: Annotated[str, Form()] = "",
        sifre: Annotated[str, Form()] = "",
    ):
        ayarlar = request.app.state.settings  # çağrı anında okunur
        if secret_zayif_mi(ayarlar):
            return _giris_sayfasi(
                request,
                f"Panel kapalı: SECRET_KEY ayarlanmalı (en az {SECRET_EN_AZ_UZUNLUK} karakter, varsayılan olmamalı).",
                401,
            )
        sifre_tamam = sifre_dogru(sifre, ayarlar.admin_sifre_hash)
        kullanici_tamam = secrets.compare_digest(
            kullanici.encode(), ayarlar.admin_kullanici.encode()
        )
        if not (sifre_tamam and kullanici_tamam):
            return _giris_sayfasi(request, "Kullanıcı adı veya şifre hatalı", 401)
        request.session.clear()  # oturum sabitlemeye karşı yeni oturum
        request.session["kullanici"] = ayarlar.admin_kullanici
        return RedirectResponse("/panel", status_code=303)

    @router.post("/cikis")
    def cikis(request: Request, _: Yonetici, csrf: Annotated[str, Form()] = ""):
        csrf_dogrula(request, csrf)
        request.session.clear()
        return RedirectResponse(GIRIS_ADRESI, status_code=303)

    @router.get("")
    def panel(request: Request, kullanici: Yonetici, s: Oturum):
        bekleyenler = list(s.scalars(
            select(Sehit).where(Sehit.durum == Durum.onay_bekliyor)
            .order_by(Sehit.olusturma.desc(), Sehit.id.desc())
        ))
        yeni_bildirim = s.scalar(
            select(func.count(Bildirim.id)).where(Bildirim.kapandi.is_(False))
        )
        return _liste_sayfasi(
            request, kullanici, mod="bekleyen", kayitlar=bekleyenler,
            bekleyen_sayisi=len(bekleyenler), yeni_bildirim=yeni_bildirim, q="",
        )

    @router.get("/yayinda")
    def yayinda(request: Request, kullanici: Yonetici, s: Oturum, q: str = "", sayfa: int = 1):
        sayfa = max(sayfa, 1)
        sonuc = repo.listele(s, q=q or None, sayfa=sayfa, adet=YAYINDA_SAYFA_ADEDI)
        return _liste_sayfasi(
            request, kullanici, mod="yayinda", kayitlar=sonuc.kayitlar, q=q,
            toplam=sonuc.toplam, sayfa=sayfa, adet=YAYINDA_SAYFA_ADEDI,
        )

    @router.get("/sehit/yeni")
    def yeni_formu(request: Request, kullanici: Yonetici):
        return _duzenle_sayfasi(request, kullanici, None, _form_degerleri(None))

    @router.post("/sehit/yeni")
    def yeni_kaydet(
        request: Request, kullanici: Yonetici, s: Oturum, ham: FormVerisi,
        csrf: Annotated[str, Form()] = "",
    ):
        csrf_dogrula(request, csrf)
        try:
            veri = veri_olustur(ham, "panel")
        except ValueError as hata:
            return _duzenle_sayfasi(request, kullanici, None, ham, str(hata), 400)
        sehit = repo.yeni_sehit(s, veri, durum=Durum.onay_bekliyor)
        return RedirectResponse(f"/panel/sehit/{sehit.id}", status_code=303)

    @router.get("/sehit/{sehit_id:int}")
    def duzenle_formu(request: Request, kullanici: Yonetici, s: Oturum, sehit_id: int):
        sehit = _sehit_getir(s, sehit_id)
        return _duzenle_sayfasi(request, kullanici, sehit, _form_degerleri(sehit))

    @router.post("/sehit/{sehit_id:int}")
    def duzenle_kaydet(
        request: Request, kullanici: Yonetici, s: Oturum, sehit_id: int, ham: FormVerisi,
        csrf: Annotated[str, Form()] = "",
        islem: Annotated[str, Form()] = "",
    ):
        csrf_dogrula(request, csrf)
        sehit = _sehit_getir(s, sehit_id)
        try:
            veri = veri_olustur(ham, sehit.kaynak_kodu)
        except ValueError as hata:
            return _duzenle_sayfasi(request, kullanici, sehit, ham, str(hata), 400)
        repo.sehit_guncelle(s, sehit, veri)
        if islem == "onayla":
            repo.durum_degistir(s, sehit, Durum.yayinda)
            return RedirectResponse("/panel", status_code=303)
        return RedirectResponse(f"/panel/sehit/{sehit.id}", status_code=303)

    def _durum_rotasi(yol: str, durum: Durum) -> None:
        @router.post(f"/sehit/{{sehit_id:int}}/{yol}", name=yol)
        def _islem(
            request: Request, _: Yonetici, s: Oturum, sehit_id: int,
            csrf: Annotated[str, Form()] = "",
        ):
            csrf_dogrula(request, csrf)
            repo.durum_degistir(s, _sehit_getir(s, sehit_id), durum)
            return RedirectResponse("/panel", status_code=303)

    _durum_rotasi("onayla", Durum.yayinda)
    _durum_rotasi("reddet", Durum.reddedildi)
    _durum_rotasi("kaldir", Durum.reddedildi)

    return router
