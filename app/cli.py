"""Komut satırı araçları: `sifre-olustur`, `ornek-veri`."""
import argparse
import getpass
import random
import sys
from datetime import date, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.admin import BCRYPT_EN_COK_BAYT, sifre_hashle
from app.config import get_settings
from app.dates import bugun
from app.db import motor_olustur
from app.models import Bildirim, Kaynak, Sehit

ORNEK_KAYNAK = "ornek"
ADLAR = ["Ahmet", "Mehmet", "Mustafa", "Ali", "Hasan", "Hüseyin", "İbrahim", "Ömer", "Yusuf",
         "Murat", "Emre", "Fatih", "Kemal", "Serkan", "Burak", "Cem", "Eren", "Onur", "Işık", "Şaban"]
SOYADLAR = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Öztürk", "Aydın", "Arslan",
            "Doğan", "Kılıç", "Aslan", "Çetin", "Kara", "Koç", "Kurt", "Özdemir", "Işık", "Güneş"]
MEMLEKETLER = ["Ankara", "İstanbul", "İzmir", "Konya", "Trabzon", "Sivas", "Erzurum", "Diyarbakır",
               "Gaziantep", "Kayseri", "Samsun", "Malatya", "Van", "Hatay", "Çorum"]
KATEGORILER = [("asker", "Uzman Çavuş", "Kara Kuvvetleri"), ("asker", "Er", "Kara Kuvvetleri"),
               ("jandarma", "Jandarma Astsubay", "Jandarma"), ("polis", "Polis Memuru", "Emniyet"),
               ("ogretmen", "Öğretmen", "Milli Eğitim"), ("diger", "Güvenlik Korucusu", None)]
ESKI_LAKAPLAR = ["Cevizli Mehmet", "Bayraktar", "Kör Ali", "Seyit Onbaşı", "Hacı Bayram",
                 "Sütçü İmam", "Koca Seyit", "Topçu Ahmet", "Mehmetçik", "Külahlı Ali"]


def _tarih_uret(rng: random.Random, bas: date, son: date) -> date:
    return bas + timedelta(days=rng.randrange((son - bas).days + 1))


def _kayit(rng: random.Random, **alanlar) -> Sehit:
    kategori, gorev, kurum = rng.choice(KATEGORILER)
    veri = dict(
        ad=rng.choice(ADLAR), soyad=rng.choice(SOYADLAR), kategori=kategori, gorev=gorev,
        kurum=kurum, memleket=rng.choice(MEMLEKETLER), kaynak_kodu=ORNEK_KAYNAK,
        durum="yayinda", tarih_hassasiyeti="tam",
    )
    veri.update(alanlar)
    sehit = Sehit(**veri)
    sehit.alanlari_yenile()
    sehit.kaynaklar.append(Kaynak(kaynak_adi="Örnek kaynak", baslik="Örnek veri, gerçek kayıt değildir"))
    return sehit


def ornek_kayitlar(bugun_: date, rng: random.Random | None = None) -> list[Sehit]:
    """Deterministik örnek kayıtlar: 300 yayında, 5 onay bekleyen, 20 eski."""
    rng = rng or random.Random(2026)
    kayitlar: list[Sehit] = []
    # "Bugün" kutusu görünsün: bugünün gün/ayına denk gelen, 2000 sonrası kayıtlar.
    for yil in rng.sample(range(2001, bugun_.year), 6):
        kayitlar.append(_kayit(rng, sehadet_tarihi=date(yil, bugun_.month, bugun_.day)))
    for _ in range(294):
        kayitlar.append(_kayit(rng, sehadet_tarihi=_tarih_uret(rng, date(2000, 1, 1), bugun_)))
    for _ in range(5):
        kayitlar.append(_kayit(
            rng, durum="onay_bekliyor",
            sehadet_tarihi=_tarih_uret(rng, bugun_ - timedelta(days=60), bugun_),
        ))
    # Eski kayıtlar: yalnızca yıl ya da tarih bilinmiyor; soyadsız, lakaplı.
    for i in range(20):
        ortak = dict(soyad=None, lakap=ESKI_LAKAPLAR[i % len(ESKI_LAKAPLAR)], kategori="diger",
                     gorev=None, kurum=None)
        if i % 2 == 0:
            kayitlar.append(_kayit(rng, tarih_hassasiyeti="yil", yil=rng.randrange(1915, 2000), **ortak))
        else:
            kayitlar.append(_kayit(rng, tarih_hassasiyeti="bilinmiyor", **ortak))
    return kayitlar


def ornek_sil(session: Session) -> int:
    sehitler = list(session.scalars(select(Sehit).where(Sehit.kaynak_kodu == ORNEK_KAYNAK)))
    kimlikler = [s.id for s in sehitler]
    if kimlikler:
        session.execute(update(Bildirim).where(Bildirim.sehit_id.in_(kimlikler)).values(sehit_id=None))
    for sehit in sehitler:
        session.delete(sehit)
    session.commit()
    return len(kimlikler)


def ornek_veri(argv: list[str]) -> int:
    ayril = argparse.ArgumentParser(prog="python -m app.cli ornek-veri")
    ayril.add_argument("--sil", action="store_true", help="örnek kayıtları sil")
    ayril.add_argument("--eminim", action="store_true", help="PostgreSQL'e yazmayı onayla")
    secenekler = ayril.parse_args(argv)
    url = get_settings().database_url
    if url.startswith("postgresql") and not secenekler.eminim:
        print("Bu bir PostgreSQL (üretim) veritabanı; örnek veri işlenmedi. "
              "Gerçekten istiyorsanız --eminim ekleyin.", file=sys.stderr)
        return 1
    with sessionmaker(motor_olustur(url))() as session:
        silinen = ornek_sil(session)
        if secenekler.sil:
            print(f"{silinen} örnek kayıt silindi.")
            return 0
        kayitlar = ornek_kayitlar(bugun())
        session.add_all(kayitlar)
        session.commit()
        print(f"{len(kayitlar)} örnek kayıt eklendi ({silinen} eski örnek kayıt değiştirildi).")
    return 0


def sifre_olustur() -> int:
    sifre = getpass.getpass("Yeni yönetici şifresi: ")
    if not sifre:
        print("Şifre boş olamaz.", file=sys.stderr)
        return 1
    if len(sifre.encode()) > BCRYPT_EN_COK_BAYT:
        print(f"Şifre en fazla {BCRYPT_EN_COK_BAYT} bayt olabilir.", file=sys.stderr)
        return 1
    if getpass.getpass("Şifre (tekrar): ") != sifre:
        print("Şifreler uyuşmuyor.", file=sys.stderr)
        return 1
    hash_ = sifre_hashle(sifre)
    print("\n.env dosyasına şu satırı ekleyin (tek tırnaklar dahil, olduğu gibi):\n")
    print(f"ADMIN_SIFRE_HASH='{hash_}'")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    for akis in (sys.stdout, sys.stderr):  # Windows konsolu (cp1252) Türkçe harflerde çökmesin
        if hasattr(akis, "reconfigure"):
            akis.reconfigure(encoding="utf-8", errors="replace")
    if argv == ["sifre-olustur"]:
        return sifre_olustur()
    if argv and argv[0] == "ornek-veri":
        return ornek_veri(argv[1:])
    print("Kullanım: python -m app.cli sifre-olustur | ornek-veri [--sil] [--eminim]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
