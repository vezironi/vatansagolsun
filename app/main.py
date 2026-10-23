"""Uygulama fabrikası."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.admin import GirisGerekli, secret_zayif_mi, giris_gerekli_isleyici, panel_router_olustur
from app.api import api_router_olustur
from app.config import Settings, get_settings
from app.db import motor_olustur
from app.zamanlayici import zamanlayici_kur
from app.site import bildir_router_olustur, router as site_router

logger = logging.getLogger(__name__)
PAKET_DIZINI = Path(__file__).resolve().parent


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        zamanlayici = zamanlayici_kur(app.state.session_factory)
        app.state.zamanlayici = zamanlayici
        if zamanlayici is not None:
            zamanlayici.start()
            logger.info("sehitlerimiz zamanlayıcısı başladı (12 saatte bir)")
        try:
            yield
        finally:
            if zamanlayici is not None:
                zamanlayici.shutdown(wait=False)

    app = FastAPI(
        lifespan=lifespan,
        title="Vatan Sağ Olsun",
        docs_url="/api/belgeler",
        openapi_url="/api/openapi.json",
    )
    if secret_zayif_mi(settings):
        logger.warning(
            "SECRET_KEY varsayılan ya da 32 karakterden kısa: yönetici paneli kapalı kalacak."
        )
    motor = motor_olustur(settings.database_url)
    app.state.motor = motor
    app.state.session_factory = sessionmaker(motor)
    app.state.settings = settings
    app.state.zamanlayici = None

    # Sınırlayıcı uygulama başına kurulur: testler arasında sayaç sızmaz.
    app.state.limiter = Limiter(key_func=get_remote_address)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_exception_handler(GirisGerekli, giris_gerekli_isleyici)

    # Üretimde OTURUM_HTTPS=true (testler http://testserver kullanır, varsayılan False).
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        same_site="lax",
        https_only=settings.oturum_https,
    )

    static_dizini = PAKET_DIZINI / "static"
    if static_dizini.is_dir():
        app.mount("/static", StaticFiles(directory=static_dizini), name="static")

    app.include_router(api_router_olustur(app.state.limiter, settings.istek_siniri))
    app.include_router(panel_router_olustur(app.state.limiter))
    app.include_router(bildir_router_olustur(app.state.limiter))
    app.include_router(site_router)
    return app


app = create_app()
