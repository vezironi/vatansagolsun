"""Girdi şemaları."""
from datetime import date
from typing import Self
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import Hassasiyet, Kategori


OLAY_UZUNLUGU = 4000
URL_UZUNLUGU = 1000


def http_adresi_mi(url: str) -> bool:
    ayrik = urlparse(url)
    return ayrik.scheme in ("http", "https") and bool(ayrik.netloc)


class SehitVeri(BaseModel):
    ad: str = Field(max_length=200)
    soyad: str | None = Field(default=None, max_length=200)
    lakap: str | None = Field(default=None, max_length=200)
    tarih_hassasiyeti: Hassasiyet = Hassasiyet.tam
    sehadet_tarihi: date | None = None
    yil: int | None = None
    gorev: str | None = Field(default=None, max_length=200)
    kategori: Kategori = Kategori.diger
    kurum: str | None = Field(default=None, max_length=200)
    memleket: str | None = Field(default=None, max_length=200)
    baba_adi: str | None = Field(default=None, max_length=200)
    dogum_yili: int | None = None
    donem: str | None = Field(default=None, max_length=100)
    sehadet_yeri: str | None = Field(default=None, max_length=200)
    sehadet_olayi: str | None = Field(default=None, max_length=OLAY_UZUNLUGU)
    fotograf_url: str | None = Field(default=None, max_length=URL_UZUNLUGU)
    resmi_teyit: bool = False
    isimsiz: bool = False
    kaynak_kodu: str = Field(max_length=50)

    @field_validator("fotograf_url")
    @classmethod
    def _fotograf_http_mi(cls, url: str | None) -> str | None:
        if url is not None and not http_adresi_mi(url):
            raise ValueError("Fotoğraf adresi http:// ya da https:// ile başlamalıdır.")
        return url

    @model_validator(mode="after")
    def _tarih_tutarli_mi(self) -> Self:
        if self.tarih_hassasiyeti == Hassasiyet.tam and self.sehadet_tarihi is None:
            raise ValueError("Tam tarih için şehadet tarihi zorunludur.")
        if self.tarih_hassasiyeti == Hassasiyet.yil and self.yil is None:
            raise ValueError("Yıl hassasiyeti için yıl zorunludur.")
        return self


class KaynakYanit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kaynak_adi: str
    url: str | None = None


class SehitOzet(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    ad: str
    soyad: str | None
    lakap: str | None
    gorunen_ad: str
    sehadet_yili: int | None = Field(validation_alias="yil")
    sehadet_tarihi: date | None
    tarih_hassasiyeti: Hassasiyet
    gorev: str | None
    kategori: Kategori
    memleket: str | None
    url: str


class SehitDetay(SehitOzet):
    kurum: str | None
    baba_adi: str | None
    dogum_yili: int | None
    donem: str | None
    sehadet_yeri: str | None
    sehadet_olayi: str | None
    fotograf_url: str | None
    kaynaklar: list[KaynakYanit]


class IstatistikYanit(BaseModel):
    toplam: int
    bu_yil: int
    yil: int


class ListeYanit(BaseModel):
    toplam: int
    sayfa: int
    adet: int
    kayitlar: list[SehitOzet]


class BugunKayit(SehitOzet):
    yil_donumu: int


class BugunYanit(BaseModel):
    tarih: str
    kayitlar: list[BugunKayit]
