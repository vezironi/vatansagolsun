"""Onay paneli: giriş, oturum, CSRF."""
import secrets
from pathlib import Path
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter

GIRIS_ADRESI = "/panel/giris"
BCRYPT_EN_COK_BAYT = 72
GIRIS_SINIRI = "10/minute"
VARSAYILAN_SECRET = "degistir"
SECRET_EN_AZ_UZUNLUK = 32

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


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


def _giris_sayfasi(request: Request, hata: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request, "panel/giris.html", {"hata": hata}, status_code=status_code
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
    def panel(request: Request, kullanici: Yonetici):
        return templates.TemplateResponse(
            request,
            "panel/liste.html",
            {"kullanici": kullanici, "csrf": csrf_token(request), "kayitlar": []},
        )

    return router
