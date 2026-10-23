"""Girdi şemaları."""
from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import Hassasiyet, Kategori


class SehitVeri(BaseModel):
    ad: str
    soyad: str | None = None
    lakap: str | None = None
    tarih_hassasiyeti: Hassasiyet = Hassasiyet.tam
    sehadet_tarihi: date | None = None
    yil: int | None = None
    gorev: str | None = None
    kategori: Kategori = Kategori.diger
    kurum: str | None = None
    memleket: str | None = None
    baba_adi: str | None = None
    dogum_yili: int | None = None
    donem: str | None = None
    resmi_teyit: bool = False
    isimsiz: bool = False
    kaynak_kodu: str

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
