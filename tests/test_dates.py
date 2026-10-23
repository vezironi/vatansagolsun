from datetime import datetime, timezone, date
from app.dates import bugun

def test_bugun_istanbul_gece_yarisi():
    # UTC 22 Ekim 21:30 = İstanbul 23 Ekim 00:30
    assert bugun(datetime(2026, 10, 22, 21, 30, tzinfo=timezone.utc)) == date(2026, 10, 23)

def test_bugun_parametresiz_tarih_doner():
    assert isinstance(bugun(), date)
