"""Şehit sorguları ve yazma işlemleri."""
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Bildirim, Durum, Hassasiyet, Sehit
from app.schemas import SehitVeri
from app.text import katla

YilFiltre = int | Literal["2000-oncesi"] | None


@dataclass
class Istatistik:
    toplam: int
    bu_yil: int
    yil: int


@dataclass
class Sayfa:
    toplam: int
    kayitlar: list[Sehit]


def _gorunur(sorgu, api: bool):
    sorgu = sorgu.where(Sehit.durum == Durum.yayinda)
    if api:
        haric = get_settings().api_haric_kaynaklar
        if haric:
            sorgu = sorgu.where(Sehit.kaynak_kodu.not_in(haric))
    return sorgu


def istatistik(s: Session, bugun: date, *, api: bool = False) -> Istatistik:
    toplam = s.scalar(_gorunur(select(func.count(Sehit.id)), api))
    bu_yil = s.scalar(_gorunur(select(func.count(Sehit.id)), api).where(Sehit.yil == bugun.year))
    return Istatistik(toplam=toplam, bu_yil=bu_yil, yil=bugun.year)


def listele(
    s: Session,
    *,
    yil: YilFiltre = None,
    q: str | None = None,
    sayfa: int = 1,
    adet: int = 25,
    api: bool = False,
) -> Sayfa:
    sorgu = _gorunur(select(Sehit), api)
    if yil == "2000-oncesi":
        sorgu = sorgu.where(or_(Sehit.yil < 2000, Sehit.yil.is_(None)))
    elif yil is not None:
        sorgu = sorgu.where(Sehit.yil == yil)
    if q:
        for kelime in katla(q).split():
            sorgu = sorgu.where(Sehit.arama_metni.like(f"%{kelime}%"))

    toplam = s.scalar(select(func.count()).select_from(sorgu.subquery()))
    sorgu = sorgu.order_by(
        Sehit.yil.is_(None), Sehit.yil.desc(),
        Sehit.ay.is_(None), Sehit.ay.desc(),
        Sehit.gun.is_(None), Sehit.gun.desc(),
        Sehit.id.desc(),
    )
    sorgu = sorgu.limit(adet).offset((max(sayfa, 1) - 1) * adet)
    return Sayfa(toplam=toplam, kayitlar=list(s.scalars(sorgu)))


def yil_donumu(
    s: Session, ay: int, gun: int, *, artik_yil: bool, api: bool = False
) -> list[Sehit]:
    gunler = [(ay, gun)]
    if (ay, gun) == (2, 28) and not artik_yil:
        gunler.append((2, 29))
    sorgu = _gorunur(select(Sehit), api).where(
        Sehit.tarih_hassasiyeti == Hassasiyet.tam,
        Sehit.yil >= 2000,
        Sehit.ay.is_not(None),
        Sehit.gun.is_not(None),
        or_(*[(Sehit.ay == a) & (Sehit.gun == g) for a, g in gunler]),
    )
    return list(s.scalars(sorgu.order_by(Sehit.yil.desc(), Sehit.id)))


def getir(
    s: Session, sehit_id: int, *, sadece_yayinda: bool = True, api: bool = False
) -> Sehit | None:
    sorgu = select(Sehit).where(Sehit.id == sehit_id)
    if sadece_yayinda:
        sorgu = _gorunur(sorgu, api)
    elif api:
        haric = get_settings().api_haric_kaynaklar
        if haric:
            sorgu = sorgu.where(Sehit.kaynak_kodu.not_in(haric))
    return s.scalar(sorgu)


def _alanlari_uygula(sehit: Sehit, veri: SehitVeri) -> None:
    for alan, deger in veri.model_dump().items():
        setattr(sehit, alan, deger)


def yeni_sehit(s: Session, veri: SehitVeri, *, durum: Durum = Durum.onay_bekliyor) -> Sehit:
    sehit = Sehit(durum=durum)
    _alanlari_uygula(sehit, veri)
    sehit.alanlari_yenile()
    s.add(sehit)
    s.commit()
    return sehit


def sehit_guncelle(s: Session, sehit: Sehit, veri: SehitVeri) -> Sehit:
    _alanlari_uygula(sehit, veri)
    sehit.alanlari_yenile()
    s.commit()
    return sehit


def durum_degistir(s: Session, sehit: Sehit, durum: Durum) -> None:
    sehit.durum = durum
    sehit.alanlari_yenile()
    s.commit()


_BIRLESTIRME_ALANLARI = (
    "soyad", "lakap", "gorev", "kurum", "memleket", "baba_adi", "dogum_yili", "donem",
)


def birlestir(s: Session, hedef: Sehit, fazla: Sehit) -> Sehit:
    for alan in _BIRLESTIRME_ALANLARI:
        if getattr(hedef, alan) in (None, "") and getattr(fazla, alan) not in (None, ""):
            setattr(hedef, alan, getattr(fazla, alan))
    hedef.resmi_teyit = bool(hedef.resmi_teyit or fazla.resmi_teyit)
    for kaynak in list(fazla.kaynaklar):
        kaynak.sehit = hedef
    for bildirim in s.scalars(select(Bildirim).where(Bildirim.sehit_id == fazla.id)):
        bildirim.sehit_id = hedef.id  # silinen kayda bağlı bildirim kalmasın
    s.flush()
    s.delete(fazla)
    hedef.alanlari_yenile()
    s.commit()
    return hedef


def bildirim_ekle(
    s: Session, *, mesaj: str, iletisim: str | None, sehit_id: int | None
) -> Bildirim:
    bildirim = Bildirim(mesaj=mesaj, iletisim=iletisim, sehit_id=sehit_id)
    s.add(bildirim)
    s.commit()
    return bildirim
