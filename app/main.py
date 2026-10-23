"""Uygulama fabrikası."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.api import api_router_olustur
from app.config import Settings, get_settings
from app.db import motor_olustur

PAKET_DIZINI = Path(__file__).resolve().parent


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Vatan Sağ Olsun",
        docs_url="/api/belgeler",
        openapi_url="/api/openapi.json",
    )
    motor = motor_olustur(settings.database_url)
    app.state.motor = motor
    app.state.session_factory = sessionmaker(motor)
    app.state.settings = settings

    # Sınırlayıcı uygulama başına kurulur: testler arasında sayaç sızmaz.
    app.state.limiter = Limiter(key_func=get_remote_address)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    static_dizini = PAKET_DIZINI / "static"
    if static_dizini.is_dir():
        app.mount("/static", StaticFiles(directory=static_dizini), name="static")

    app.include_router(api_router_olustur(app.state.limiter, settings.istek_siniri))
    return app


app = create_app()
