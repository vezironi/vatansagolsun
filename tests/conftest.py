from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (tabloları Base'e kaydeder)
from app.db import Base, get_session
from app.main import create_app
from app.models import Sehit


@pytest.fixture
def session():
    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(motor)
    with sessionmaker(motor)() as s:
        yield s
    motor.dispose()


@pytest.fixture
def sehit_ekle(session):
    def _ekle(**alanlar) -> Sehit:
        varsayilan = dict(
            ad="Ahmet",
            soyad="Yılmaz",
            kategori="asker",
            kaynak_kodu="test",
            durum="yayinda",
            tarih_hassasiyeti="tam",
            sehadet_tarihi=date(2016, 10, 23),
        )
        varsayilan.update(alanlar)
        s = Sehit(**varsayilan)
        s.alanlari_yenile()
        session.add(s)
        session.commit()
        return s

    return _ekle


@pytest.fixture
def app(session, monkeypatch):
    from app.config import get_settings

    # Güçlü anahtar: zayıf anahtarda panel bilerek kapalıdır.
    monkeypatch.setattr(get_settings(), "secret_key", "t" * 40)
    uygulama = create_app()
    uygulama.dependency_overrides[get_session] = lambda: session
    return uygulama


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def ayarli_sifre(app, monkeypatch):
    from app.admin import sifre_hashle

    monkeypatch.setattr(app.state.settings, "admin_kullanici", "admin")
    monkeypatch.setattr(app.state.settings, "admin_sifre_hash", sifre_hashle("test-sifre"))


@pytest.fixture
def panel_client(app, ayarli_sifre):
    # Aynı uygulamaya bağlı ikinci istemci: çerez kabı ayrı, `client` giriş yapmaz.
    istemci = TestClient(app)
    yanit = istemci.post(
        "/panel/giris",
        data={"kullanici": "admin", "sifre": "test-sifre"},
        follow_redirects=False,
    )
    assert yanit.status_code == 303
    return istemci


@pytest.fixture
def csrf():
    import re

    def _oku(istemci: TestClient) -> str:
        sayfa = istemci.get("/panel").text
        eslesme = re.search(r'name="csrf"\s+value="([^"]+)"', sayfa)
        assert eslesme, "panel sayfasında csrf alanı yok"
        return eslesme.group(1)

    return _oku
