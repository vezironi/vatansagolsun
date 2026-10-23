"""Uygulama ayarları (.env dosyasından okunur)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "sqlite:///./yerel.db"
    secret_key: str = "degistir"
    admin_kullanici: str = "admin"
    admin_sifre_hash: str = ""
    api_haric_kaynaklar: list[str] = []
    istek_siniri: str = "60/minute"
    site_url: str = "http://localhost:8000"
    kaynak_izinleri: list[str] = ["egm", "sg", "kahramanlar", "sehitlerimiz", "temmuz15", "hurriyet", "sabah"]
    istek_araligi_sn: float = 2.0
    zamanlayici_aktif: bool = False  # docker-compose'ta True: 12 saatlik sehitlerimiz kontrolü
    analiz_sirasi: list[str] = ["openai", "gemini", "claude"]  # anahtarı olmayan sağlayıcı zincire girmez
    analiz_modeli: str = "claude-haiku-5-5"  # Claude
    openai_modeli: str = "gpt-6-luna"
    gemini_modeli: str = "gemini-3.1-flash-lite"
    gunluk_analiz_siniri: int = 200
    anthropic_api_key: str = ""  # boşsa SDK kendi kimlik çözümüne bırakılır
    openai_api_key: str = ""  # boşsa OPENAI_API_KEY ortam değişkenine bakılır
    gemini_api_key: str = ""  # boşsa GEMINI_API_KEY / GOOGLE_API_KEY ortam değişkenine bakılır
    oturum_https: bool = False  # üretimde True: oturum çerezi yalnızca HTTPS ile gider
    muzik_aktif: bool = True  # sitenin sol altındaki müzik çalar
    muzik_dosyasi: str = "/public/kolaydegildir.mp3"  # proje kökündeki public/ klasörü /public altında sunulur
    muzik_basligi: str = "Duman — Kolay Değildir"
    muzik_baslangic_sesi: float = 0.4  # 0–1; ziyaretçi değiştirince tarayıcıda hatırlanır


@lru_cache
def get_settings() -> Settings:
    return Settings()
