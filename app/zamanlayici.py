"""Arka plan zamanlayıcısı: sehitlerimiz.org.tr'yi 12 saatte bir yeni kayıt için kontrol eder."""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app import aktarim
from app.config import get_settings
from app.kaynaklar.getirici import Getirici

logger = logging.getLogger(__name__)
ZAMAN_DILIMI = "Europe/Istanbul"
KONTROL_SAATI = 12
ILK_CALISMA_DAKIKA = 5


def kontrol_isi(session_factory) -> None:
    """Tek çalışma: kendi oturumunu açar/kapatır; hata günlüğe ve KaynakDurumu'na yazılır."""
    try:
        with session_factory() as session:
            aktarim.sehitlerimiz_kontrol(session, Getirici())
    except Exception:  # noqa: BLE001 - iş bir sonraki turda yine çalışsın
        logger.exception("sehitlerimiz zamanlanmış kontrolü çöktü")


def zamanlayici_kur(session_factory) -> BackgroundScheduler | None:
    """Ayar kapalıysa None; açıksa işi tanımlanmış (henüz başlamamış) zamanlayıcı."""
    if not get_settings().zamanlayici_aktif:
        return None
    zamanlayici = BackgroundScheduler(timezone=ZAMAN_DILIMI)
    ilk = datetime.now(zamanlayici.timezone) + timedelta(minutes=ILK_CALISMA_DAKIKA)
    zamanlayici.add_job(
        kontrol_isi,
        IntervalTrigger(hours=KONTROL_SAATI, start_date=ilk, timezone=ZAMAN_DILIMI),
        args=[session_factory],
        id="sehitlerimiz_kontrol",
        max_instances=1,
        coalesce=True,
    )
    return zamanlayici
