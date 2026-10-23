"""Uygulama ayarları (.env dosyasından okunur)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./yerel.db"
    secret_key: str = "degistir"
    admin_kullanici: str = "admin"
    admin_sifre_hash: str = ""
    api_haric_kaynaklar: list[str] = []
    istek_siniri: str = "60/minute"
    site_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
