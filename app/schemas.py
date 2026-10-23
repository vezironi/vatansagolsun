"""Girdi şemaları."""
from datetime import date
from typing import Self

from pydantic import BaseModel, model_validator

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
