"""Herkese açık JSON API."""
import calendar
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app import repo
from app.dates import bugun
from app.db import get_session
from app.schemas import (
    BugunKayit, BugunYanit, IstatistikYanit, ListeYanit, SehitDetay, SehitOzet,
)

Oturum = Annotated[Session, Depends(get_session)]


def api_router_olustur(limiter: Limiter, sinir: str) -> APIRouter:
    """Sınırlayıcı uygulamaya özel olduğundan yönlendirici de uygulama başına kurulur."""
    router = APIRouter(prefix="/api", tags=["api"])

    @router.get("/istatistik", response_model=IstatistikYanit)
    @limiter.limit(sinir)
    def istatistik(request: Request, s: Oturum):
        return repo.istatistik(s, bugun(), api=True)

    @router.get("/sehitler", response_model=ListeYanit)
    @limiter.limit(sinir)
    def sehitler(
        request: Request,
        s: Oturum,
        yil: Annotated[str | None, Query(pattern=r"^(\d{1,4}|2000-oncesi)$")] = None,
        q: str | None = None,
        sayfa: Annotated[int, Query(ge=1)] = 1,
        adet: Annotated[int, Query(ge=1, le=100)] = 25,
    ):
        yil_filtre = yil if yil in (None, "2000-oncesi") else int(yil)
        sonuc = repo.listele(s, yil=yil_filtre, q=q, sayfa=sayfa, adet=adet, api=True)
        return ListeYanit(
            toplam=sonuc.toplam,
            sayfa=sayfa,
            adet=adet,
            kayitlar=[SehitOzet.model_validate(k) for k in sonuc.kayitlar],
        )

    @router.get("/sehitler/{sehit_id}", response_model=SehitDetay)
    @limiter.limit(sinir)
    def sehit_detay(request: Request, sehit_id: int, s: Oturum):
        sehit = repo.getir(s, sehit_id, api=True)
        if sehit is None:
            raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
        return SehitDetay.model_validate(sehit)

    @router.get("/bugun", response_model=BugunYanit)
    @limiter.limit(sinir)
    def bugun_yil_donumleri(
        request: Request,
        s: Oturum,
        tarih: Annotated[str | None, Query(pattern=r"^\d{2}-\d{2}$")] = None,
    ):
        simdi = bugun()
        if tarih is None:
            ay, gun = simdi.month, simdi.day
        else:
            ay, gun = int(tarih[:2]), int(tarih[3:])
            try:
                date(2000, ay, gun)  # 2000 artık yıl: 29 Şubat geçerli
            except ValueError:
                raise HTTPException(status_code=422, detail="Geçersiz tarih (AA-GG).")
        kayitlar = repo.yil_donumu(
            s, ay, gun, artik_yil=calendar.isleap(simdi.year), api=True
        )
        return BugunYanit(
            tarih=f"{ay:02d}-{gun:02d}",
            kayitlar=[
                BugunKayit(
                    **SehitOzet.model_validate(k).model_dump(), yil_donumu=simdi.year - k.yil
                )
                for k in kayitlar
            ],
        )

    return router
