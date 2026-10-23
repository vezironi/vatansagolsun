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
def app(session):
    uygulama = create_app()
    uygulama.dependency_overrides[get_session] = lambda: session
    return uygulama


@pytest.fixture
def client(app):
    return TestClient(app)
