"""Arka plan zamanlayıcısı: sehitlerimiz.org.tr (12 saatte bir) ve toplayıcı (30 dakikada bir)."""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app import aktarim, toplayici
from app.config import Settings, get_settings
from app.kaynaklar.getirici import Getirici

logger = logging.getLogger(__name__)
ZAMAN_DILIMI = "Europe/Istanbul"
KONTROL_SAATI = 12
ILK_CALISMA_DAKIKA = 5
TOPLAYICI_DAKIKA = 30
TOPLAYICI_ILK_DAKIKA = 2
TOPLAYICI_ISI_KIMLIGI = "toplayici"


def kontrol_isi(session_factory) -> None:
    """Tek çalışma: kendi oturumunu açar/kapatır; hata günlüğe ve KaynakDurumu'na yazılır."""
    try:
        with session_factory() as session:
            aktarim.sehitlerimiz_kontrol(session, Getirici())
    except Exception:  # noqa: BLE001 - iş bir sonraki turda yine çalışsın
        logger.exception("sehitlerimiz zamanlanmış kontrolü çöktü")


def toplayici_isi(session_factory) -> None:
    """Toplayıcının tek turu; hata günlüğe yazılır, zamanlayıcıyı durdurmaz."""
    try:
        toplayici.toplayici_calistir(session_factory)
    except Exception:  # noqa: BLE001 - iş bir sonraki turda yine çalışsın
        logger.exception("toplayıcı zamanlanmış turu çöktü")


def zamanlayici_kur(session_factory, settings: Settings | None = None) -> BackgroundScheduler | None:
    """Ayar kapalıysa None; açıksa işi tanımlanmış (henüz başlamamış) zamanlayıcı.

    `settings`: uygulamanın ayarları (create_app'e verilen); verilmezse get_settings().
    """
    if not (settings or get_settings()).zamanlayici_aktif:
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
    zamanlayici.add_job(
        toplayici_isi,
        IntervalTrigger(
            minutes=TOPLAYICI_DAKIKA,
            start_date=datetime.now(zamanlayici.timezone) + timedelta(minutes=TOPLAYICI_ILK_DAKIKA),
            timezone=ZAMAN_DILIMI,
        ),
        args=[session_factory],
        id=TOPLAYICI_ISI_KIMLIGI,
        max_instances=1,
        coalesce=True,
    )
    return zamanlayici
