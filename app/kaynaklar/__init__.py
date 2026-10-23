"""Tarihsel kayıt kaynakları: ortak tipler."""
from dataclasses import dataclass
from datetime import date

from app.models import Hassasiyet, Kategori


@dataclass
class HamKayit:
    kaynak_kodu: str
    dis_kimlik: str
    ad: str
    soyad: str | None = None
    lakap: str | None = None
    tarih: date | None = None
    hassasiyet: Hassasiyet = Hassasiyet.bilinmiyor
    yil: int | None = None
    gorev: str | None = None
    kategori: Kategori = Kategori.asker
    kurum: str | None = None
    memleket: str | None = None
    baba_adi: str | None = None
    dogum_yili: int | None = None
    donem: str | None = None
    kaynak_adi: str = ""
    kaynak_url: str | None = None
    metin: str | None = None


class KaynakHatasi(Exception):
    """Kaynaktan veri alınırken oluşan hata."""

    def __init__(self, mesaj: str = "", *, durum_kodu: int | None = None) -> None:
        super().__init__(mesaj)
        self.durum_kodu = durum_kodu  # HTTP durum kodu (4xx yanıtlarında), yoksa None


class KaynakIzniYok(KaynakHatasi):
    """Kaynak izin listesinde olmadığı için istek atılmadı."""
