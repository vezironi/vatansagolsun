from datetime import date

import pytest

from sqlalchemy import func, select

from app import cli
from app.dates import bugun
from app.models import Sehit


def test_ornek_kayitlar_dagilimi():
    kayitlar = cli.ornek_kayitlar(date(2026, 10, 23))
    yayinda = [k for k in kayitlar if k.durum == "yayinda"]
    assert len(yayinda) == 320 and len(kayitlar) == 325
    assert sum(k.durum == "onay_bekliyor" for k in kayitlar) == 5
    assert sum(k.tarih_hassasiyeti != "tam" for k in kayitlar) == 20
    bugunku = [k for k in yayinda if k.ay == 10 and k.gun == 23 and k.yil >= 2000]
    assert len(bugunku) >= 6
    assert all(k.kaynak_kodu == "ornek" for k in kayitlar)


def test_ornek_kayitlar_deterministik():
    a = [k.arama_metni for k in cli.ornek_kayitlar(date(2026, 10, 23))]
    b = [k.arama_metni for k in cli.ornek_kayitlar(date(2026, 10, 23))]
    assert a == b


def test_ornek_sil_yalniz_ornekleri_siler(session, sehit_ekle):
    gercek = sehit_ekle(kaynak_kodu="gercek")
    session.add_all(cli.ornek_kayitlar(bugun()))
    session.commit()
    assert cli.ornek_sil(session) == 325
    assert session.scalar(select(func.count()).select_from(Sehit)) == 1
    assert session.get(Sehit, gercek.id) is not None


def test_postgresql_icin_eminim_gerekir(monkeypatch, capsys):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "database_url", "postgresql+psycopg://x@yok/yok")
    assert cli.main(["ornek-veri"]) == 1
    assert "--eminim" in capsys.readouterr().err


def test_bos_env_degiskenleri_varsayilana_duser(monkeypatch):
    from app.config import Settings
    monkeypatch.setenv("OTURUM_HTTPS", "")
    monkeypatch.setenv("API_HARIC_KAYNAKLAR", "")
    ayar = Settings(_env_file=None)
    assert ayar.oturum_https is False and ayar.api_haric_kaynaklar == []


# --- aktar komutu -----------------------------------------------------------

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import aktarim  # noqa: E402
from app.db import Base  # noqa: E402
from app.kaynaklar import HamKayit, KaynakHatasi  # noqa: E402
from app.models import KaynakDurumu  # noqa: E402


def _ham(kod, i):
    return HamKayit(kaynak_kodu=kod, dis_kimlik=str(i), ad=f"Ad{i}", soyad=f"Soyad{i}",
                    tarih=date(2010, 1, 1 + i % 28), hassasiyet="tam")


def sahte_okuyucu(kod, sayfa_sayisi=3, hata=None, cagrilar=None):
    """Her sayfa tek kayıt; imleç = tamamlanan sayfa sayısı. hata: {'sayfa': n} dict'i (None kapalı)."""
    def okuyucu(g, imlec):
        if cagrilar is not None:
            cagrilar.append(imlec)
        for i in range(int(imlec or 0), sayfa_sayisi):
            if hata and hata.get("sayfa") == i + 1:
                raise KaynakHatasi("ağ hatası")
            yield str(i + 1), [_ham(kod, i + 1)]
    return okuyucu


@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    from app.config import get_settings

    url = f"sqlite:///{(tmp_path / 'cli.db').as_posix()}"
    monkeypatch.setattr(get_settings(), "database_url", url)
    motor = create_engine(url)
    Base.metadata.create_all(motor)
    yield sessionmaker(motor)
    motor.dispose()


def _sayi(fabrika):
    with fabrika() as s:
        return s.scalar(select(func.count()).select_from(Sehit))


def test_kaynagi_aktar_ikinci_cagri_bir_sey_eklemez(session, monkeypatch):
    cagrilar = []
    monkeypatch.setitem(aktarim.OKUYUCULAR, "egm", sahte_okuyucu("egm", cagrilar=cagrilar))
    d = aktarim.kaynagi_aktar(session, "egm", object())
    assert d.tamamlandi and d.eklenen == 3
    onceki = session.scalar(select(func.count()).select_from(Sehit))
    d2 = aktarim.kaynagi_aktar(session, "egm", object())
    assert d2.eklenen == 3 and session.scalar(select(func.count()).select_from(Sehit)) == onceki == 3
    assert len(cagrilar) == 1  # ikinci çağrıda okuyucu hiç kurulmadı


def test_bastan_imleci_sifirlar(session, monkeypatch):
    cagrilar = []
    monkeypatch.setitem(aktarim.OKUYUCULAR, "egm", sahte_okuyucu("egm", cagrilar=cagrilar))
    aktarim.kaynagi_aktar(session, "egm", object())
    d = aktarim.kaynagi_aktar(session, "egm", object(), bastan=True)
    assert cagrilar == [None, None]  # baştan: imleç sıfırlandı
    assert d.tamamlandi and d.imlec == "3"
    assert session.scalar(select(func.count()).select_from(Sehit)) == 3  # çoğalmadı


def test_hata_cikis_kodu_1_ve_3_sayfadan_devam(cli_db, monkeypatch, capsys):
    hata = {"sayfa": 2}
    cagrilar = []
    monkeypatch.setitem(aktarim.OKUYUCULAR, "egm", sahte_okuyucu("egm", hata=hata, cagrilar=cagrilar))
    monkeypatch.setattr(cli, "Getirici", lambda: object())
    assert cli.main(["aktar", "egm"]) == 1
    cikti = capsys.readouterr()
    assert "Kaldığı yerden devam etmek için aynı komutu tekrar çalıştırın." in cikti.err
    assert "egm: eklenen=1" in cikti.out and "durum=hata" in cikti.out
    assert _sayi(cli_db) == 1
    hata["sayfa"] = None
    assert cli.main(["aktar", "egm"]) == 0
    assert cagrilar == [None, "1"]  # 2. sayfa tekrar denenir; imleç 1. sayfada kalmıştı
    assert _sayi(cli_db) == 3
    assert "durum=basarili" in capsys.readouterr().out


def test_izin_yoksa_atlanir_ve_okuyucu_cagrilmaz(cli_db, monkeypatch, capsys):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["egm"])
    cagrilar = {"egm": [], "sg": [], "sehitlerimiz": [], "kahramanlar": []}
    for kod, liste in cagrilar.items():
        monkeypatch.setitem(aktarim.OKUYUCULAR, kod, sahte_okuyucu(kod, sayfa_sayisi=1, cagrilar=liste))
    monkeypatch.setattr(cli, "Getirici", lambda: object())
    assert cli.main(["aktar", "hepsi"]) == 0
    cikti = capsys.readouterr().out
    assert "sehitlerimiz: atlandı: izin yok (KAYNAK_IZINLERI)" in cikti
    assert cagrilar == {"egm": [None], "sg": [], "sehitlerimiz": [], "kahramanlar": []}


def test_hepsi_sirasi(cli_db, monkeypatch, capsys):
    for kod in ("egm", "sg", "sehitlerimiz", "kahramanlar"):
        monkeypatch.setitem(aktarim.OKUYUCULAR, kod, sahte_okuyucu(kod, sayfa_sayisi=1))
    monkeypatch.setattr(cli, "Getirici", lambda: object())
    assert cli.main(["aktar", "hepsi"]) == 0
    satirlar = [s.split(":")[0] for s in capsys.readouterr().out.splitlines() if "eklenen=" in s]
    assert satirlar == ["egm", "sg", "sehitlerimiz", "kahramanlar"]


def test_sehitlerimiz_kontrol_imleci_en_buyuk_kimlik(session, monkeypatch):
    def okuyucu(g, imlec):
        yield "2010:1", [_ham("sehitlerimiz", 40), _ham("sehitlerimiz", 7)]
        yield "2010:2", [_ham("sehitlerimiz", 25)]
    monkeypatch.setitem(aktarim.OKUYUCULAR, "sehitlerimiz", okuyucu)
    aktarim.kaynagi_aktar(session, "sehitlerimiz", object())
    assert session.get(KaynakDurumu, "sehitlerimiz_kontrol").imlec == "40"


def test_sehitlerimiz_kontrol_imleci_hatada_yalniz_islenen_sayfalar_ve_asla_geri_gitmez(session, monkeypatch):
    def okuyucu(g, imlec):
        yield "2010:1", [_ham("sehitlerimiz", 10)]
        raise KaynakHatasi("kesildi")
    monkeypatch.setitem(aktarim.OKUYUCULAR, "sehitlerimiz", okuyucu)
    session.add(KaynakDurumu(kaynak_kodu="sehitlerimiz_kontrol", imlec="5", tamamlandi=False))
    session.commit()
    d = aktarim.kaynagi_aktar(session, "sehitlerimiz", object())
    assert d.son_durum == "hata"
    assert session.get(KaynakDurumu, "sehitlerimiz_kontrol").imlec == "10"
    # daha küçük id'li yeni bir tur kontrol imlecini düşürmez
    monkeypatch.setitem(aktarim.OKUYUCULAR, "sehitlerimiz", lambda g, i: iter([("2011:1", [_ham("sehitlerimiz", 3)])]))
    aktarim.kaynagi_aktar(session, "sehitlerimiz", object(), bastan=True)
    assert session.get(KaynakDurumu, "sehitlerimiz_kontrol").imlec == "10"


def test_ctrl_c_130_doner_ve_sayfalar_kayitli_kalir(cli_db, monkeypatch, capsys):
    def okuyucu(g, imlec):
        yield "1", [_ham("egm", 1)]
        raise KeyboardInterrupt
    monkeypatch.setitem(aktarim.OKUYUCULAR, "egm", okuyucu)
    monkeypatch.setattr(cli, "Getirici", lambda: object())
    assert cli.main(["aktar", "egm"]) == 130
    assert "durduruldu" in capsys.readouterr().out
    assert _sayi(cli_db) == 1
    with cli_db() as s:
        assert s.get(KaynakDurumu, "egm").imlec == "1"


def test_aktarim_durumu_yazdirir(cli_db, monkeypatch, capsys):
    assert cli.main(["aktarim-durumu"]) == 0
    assert "Henüz" in capsys.readouterr().out
    monkeypatch.setitem(aktarim.OKUYUCULAR, "sg", sahte_okuyucu("sg", sayfa_sayisi=1))
    monkeypatch.setattr(cli, "Getirici", lambda: object())
    cli.main(["aktar", "sg"])
    capsys.readouterr()
    assert cli.main(["aktarim-durumu"]) == 0
    assert "sg: eklenen=1" in capsys.readouterr().out


# --- son inceleme: I6, M5 ---

def test_ozet_bu_calismayi_ve_toplami_ayri_yazar(cli_db, monkeypatch, capsys):
    monkeypatch.setitem(aktarim.OKUYUCULAR, "egm", sahte_okuyucu("egm"))
    monkeypatch.setattr(cli, "Getirici", lambda: object())
    assert cli.main(["aktar", "egm"]) == 0
    assert "egm: eklenen=3 birlesen=0 atlanan=0 hatali=0 (toplam: eklenen=3 " in capsys.readouterr().out
    assert cli.main(["aktar", "egm", "--bastan"]) == 0  # doğru tekrar çalışma hiçbir şey eklemez
    cikti = capsys.readouterr().out
    assert "egm: eklenen=0 birlesen=0 atlanan=3 hatali=0 (toplam: eklenen=3 birlesen=0 atlanan=3 " in cikti
    assert cli.main(["aktar", "egm"]) == 0  # tamamlanmış kaynak: okuyucu çalışmaz
    assert "egm: eklenen=0 birlesen=0 atlanan=0 hatali=0 (toplam: eklenen=3 " in capsys.readouterr().out


def test_hepsi_erken_hata_sonrakileri_durdurmaz(cli_db, monkeypatch, capsys):
    def patlayan(g, imlec):
        raise RuntimeError("beklenmedik")
        yield  # pragma: no cover
    monkeypatch.setitem(aktarim.OKUYUCULAR, "egm", sahte_okuyucu("egm", hata={"sayfa": 1}))
    monkeypatch.setitem(aktarim.OKUYUCULAR, "sg", patlayan)
    for kod in ("sehitlerimiz", "kahramanlar"):
        monkeypatch.setitem(aktarim.OKUYUCULAR, kod, sahte_okuyucu(kod, sayfa_sayisi=1))
    monkeypatch.setattr(cli, "Getirici", lambda: object())
    assert cli.main(["aktar", "hepsi"]) == 1
    cikti = capsys.readouterr()
    assert "egm: hata: ağ hatası" in cikti.err and "sg: beklenmeyen hata: RuntimeError" in cikti.err
    assert "sehitlerimiz: eklenen=1 " in cikti.out
    assert "kahramanlar: eklenen=0 birlesen=1 " in cikti.out  # aynı sahte kişi: sehitlerimiz kaydına katıldı
    assert _sayi(cli_db) == 1
