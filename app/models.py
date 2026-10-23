"""Veritabanı modelleri."""
from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.text import ad_duzenle, gorunen_ad, isim_anahtari, katla, slug, soyad_duzenle


class Durum(StrEnum):
    onay_bekliyor = "onay_bekliyor"
    yayinda = "yayinda"
    reddedildi = "reddedildi"


class Hassasiyet(StrEnum):
    tam = "tam"
    yil = "yil"
    bilinmiyor = "bilinmiyor"


class Kategori(StrEnum):
    asker = "asker"
    jandarma = "jandarma"
    polis = "polis"
    ogretmen = "ogretmen"
    diger = "diger"


def _simdi() -> datetime:
    return datetime.now(timezone.utc)


def _enum(sinif: type[StrEnum]) -> Enum:
    # native_enum=False: SQLite ve PostgreSQL'de aynı (VARCHAR) davranış.
    return Enum(sinif, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


class Sehit(Base):
    __tablename__ = "sehitler"
    __table_args__ = (Index("ix_sehitler_ay_gun", "ay", "gun"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ad: Mapped[str] = mapped_column(String(200))
    soyad: Mapped[str | None] = mapped_column(String(200))
    lakap: Mapped[str | None] = mapped_column(String(200))
    tarih_hassasiyeti: Mapped[Hassasiyet] = mapped_column(_enum(Hassasiyet), default=Hassasiyet.tam)
    sehadet_tarihi: Mapped[date | None] = mapped_column(Date)
    yil: Mapped[int | None] = mapped_column(Integer, index=True)
    ay: Mapped[int | None] = mapped_column(Integer)
    gun: Mapped[int | None] = mapped_column(Integer)
    gorev: Mapped[str | None] = mapped_column(String(200))
    kategori: Mapped[Kategori] = mapped_column(_enum(Kategori), default=Kategori.diger)
    kurum: Mapped[str | None] = mapped_column(String(200))
    memleket: Mapped[str | None] = mapped_column(String(200))
    baba_adi: Mapped[str | None] = mapped_column(String(200))
    dogum_yili: Mapped[int | None] = mapped_column(Integer)
    donem: Mapped[str | None] = mapped_column(String(100))
    sehadet_yeri: Mapped[str | None] = mapped_column(String(200))
    sehadet_olayi: Mapped[str | None] = mapped_column(Text)  # nasıl şehit düştüğü (kaynak anlatımı)
    fotograf_url: Mapped[str | None] = mapped_column(Text)  # yalnızca http(s); kaynağın sunucusundan gösterilir
    durum: Mapped[Durum] = mapped_column(_enum(Durum), default=Durum.onay_bekliyor, index=True)
    resmi_teyit: Mapped[bool] = mapped_column(Boolean, default=False)
    isimsiz: Mapped[bool] = mapped_column(Boolean, default=False)
    kaynak_kodu: Mapped[str] = mapped_column(String(50), index=True)
    elle_duzenlendi: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    slug: Mapped[str] = mapped_column(String(300), default="")
    arama_metni: Mapped[str] = mapped_column(Text, default="", index=True)
    isim_anahtari: Mapped[str] = mapped_column(String(400), default="", index=True)
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_simdi)
    guncelleme: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_simdi, onupdate=_simdi)

    kaynaklar: Mapped[list["Kaynak"]] = relationship(
        back_populates="sehit", cascade="all, delete-orphan"
    )

    @property
    def gorunen_ad(self) -> str:
        return gorunen_ad(self.ad, self.soyad, self.lakap)

    @property
    def url(self) -> str:
        return f"/sehit/{self.slug}-{self.id}"

    def alanlari_yenile(self) -> None:
        self.ad = ad_duzenle(self.ad)
        self.soyad = soyad_duzenle(self.soyad) if self.soyad and self.soyad.strip() else None
        self.lakap = ad_duzenle(self.lakap) if self.lakap and self.lakap.strip() else None
        self.slug = slug(self.gorunen_ad)[:300].strip("-") or "sehit"
        parcalar = [self.ad, self.soyad, self.lakap, self.memleket, self.gorev, self.kurum]
        self.arama_metni = katla(" ".join(p for p in parcalar if p))

        self.isim_anahtari = isim_anahtari(self.ad, self.soyad, self.lakap)

        hassasiyet = Hassasiyet(self.tarih_hassasiyeti)
        if hassasiyet == Hassasiyet.tam and self.sehadet_tarihi:
            self.yil = self.sehadet_tarihi.year
            self.ay = self.sehadet_tarihi.month
            self.gun = self.sehadet_tarihi.day
        elif hassasiyet == Hassasiyet.yil:
            self.ay = self.gun = self.sehadet_tarihi = None
        elif hassasiyet == Hassasiyet.bilinmiyor:
            self.yil = self.ay = self.gun = self.sehadet_tarihi = None


class Kaynak(Base):
    __tablename__ = "kaynaklar"
    __table_args__ = (UniqueConstraint("kaynak_kodu", "dis_kimlik", name="uq_kaynak_dis_kimlik"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sehit_id: Mapped[int] = mapped_column(ForeignKey("sehitler.id"))
    url: Mapped[str | None] = mapped_column(Text)
    baslik: Mapped[str | None] = mapped_column(Text)
    metin: Mapped[str | None] = mapped_column(Text)
    kaynak_adi: Mapped[str] = mapped_column(String(100))
    kaynak_kodu: Mapped[str | None] = mapped_column(String(50))
    dis_kimlik: Mapped[str | None] = mapped_column(String(300))
    eklenme: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_simdi)

    sehit: Mapped[Sehit] = relationship(back_populates="kaynaklar")


class KaynakDurumu(Base):
    __tablename__ = "kaynak_durumlari"

    kaynak_kodu: Mapped[str] = mapped_column(String(50), primary_key=True)
    imlec: Mapped[str | None] = mapped_column(Text)  # haber imleci 3 günlük kimlik kümesi taşır
    tamamlandi: Mapped[bool] = mapped_column(Boolean, default=False)
    son_calisma: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    son_durum: Mapped[str | None] = mapped_column(String(20))
    son_mesaj: Mapped[str | None] = mapped_column(Text)
    eklenen: Mapped[int] = mapped_column(Integer, default=0)
    birlesen: Mapped[int] = mapped_column(Integer, default=0)
    atlanan: Mapped[int] = mapped_column(Integer, default=0)
    hatali: Mapped[int] = mapped_column(Integer, default=0)


class Bildirim(Base):
    __tablename__ = "bildirimler"

    id: Mapped[int] = mapped_column(primary_key=True)
    sehit_id: Mapped[int | None] = mapped_column(ForeignKey("sehitler.id"))
    mesaj: Mapped[str] = mapped_column(Text)
    iletisim: Mapped[str | None] = mapped_column(String(200))
    kapandi: Mapped[bool] = mapped_column(Boolean, default=False)
    tarih: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_simdi)
