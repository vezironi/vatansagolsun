"""Türkiye saatine göre tarih yardımcıları."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")


def bugun(simdi: datetime | None = None) -> date:
    if simdi is None:
        return datetime.now(TZ).date()
    return simdi.astimezone(TZ).date()
