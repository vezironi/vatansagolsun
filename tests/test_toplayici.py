import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app import toplayici
from app.analiz import AnalizHatasi, HaberAnalizi, Kisi
from app.dates import TZ
from app.kaynaklar import haber
from app.kaynaklar.haber import HaberOgesi, Makale
from app.models import Durum, KaynakDurumu, Kaynak, Sehit

SIMDI = datetime(2026, 10, 23, 14, 0, tzinfo=TZ)


class SahteGetirici:
    def __init__(self):
        self.cagrilar = []

    def metin(self, kod, url):
        self.cagrilar.append(url)
        return "<html></html>"


class SahteAnalizci:
    def __init__(self, *cevaplar):
        self.cevaplar = list(cevaplar)
        self.cagri = 0

    def analiz_et(self, *, baslik, govde, yayin):
        self.cagri += 1
        c = self.cevaplar.pop(0) if self.cevaplar else analiz()
        if isinstance(c, Exception):
            raise c
        return c


def analiz(kisiler=None, **kw):
    v = dict(sehit_haberi=True, yeni_olay=True, resmi_kurum_duyurusu=True, isimsiz_sayisi=0,
             kisiler=[Kisi(ad="ali", soyad="kaya", kategori="asker", sehadet_tarihi="2026-10-22")]
             if kisiler is None else kisiler, olay_ozeti="Olay.")
    v.update(kw)
    return HaberAnalizi(**v)


def oge(n, saat_once=1.0, baslik="Şehit haberi", gun_once=0):
    yayin = SIMDI - timedelta(days=gun_once, hours=saat_once)
    return HaberOgesi("hurriyet", str(n), f"https://x/{n}", baslik, "", yayin)


@pytest.fixture
def ortam(monkeypatch):
    class O:
        ogeler = []
    monkeypatch.setattr(haber, "ogeleri_getir", lambda g, k: list(O.ogeler))
    monkeypatch.setattr(haber, "makale_ayristir", lambda html, k: Makale("Başlık", "Gövde", None))
    return O


def tara(s, ortam, ogeler, analizci, g=None):
    ortam.ogeler = ogeler
    return toplayici.haber_kaynagi_tara(s, "hurriyet", g or SahteGetirici(), analizci, simdi=SIMDI)


def imlec_nesnesi(s):
    return toplayici.HaberImleci.oku(s.get(KaynakDurumu, "hurriyet").imlec)


def imlec(s):
    return (imlec_nesnesi(s) or toplayici.HaberImleci()).son_yayin


def imlec_kur(s, metin):
    s.add(KaynakDurumu(kaynak_kodu="hurriyet", imlec=metin, eklenen=0, birlesen=0, atlanan=0, hatali=0))
    s.commit()


def test_ilk_calisma_yalnizca_bugun(session, ortam):
    dun, bugun = oge(1, gun_once=1), oge(2, saat_once=2)
    a = SahteAnalizci()
    d = tara(session, ortam, [bugun, dun], a)
    assert a.cagri == 1 and imlec(session) == bugun.yayin and d.eklenen == 1


def test_imlecten_sonrasi_ve_uc_gun_telafi(session, ortam):
    session.add(KaynakDurumu(kaynak_kodu="hurriyet", imlec=(SIMDI - timedelta(days=5)).isoformat(),  # eski düz ISO biçimi de okunur
                             eklenen=0, birlesen=0, atlanan=0, hatali=0))
    session.commit()
    eski, yeni = oge(1, gun_once=4), oge(2, gun_once=2, baslik="Şehit 2")
    a = SahteAnalizci()
    tara(session, ortam, [yeni, eski], a)
    assert a.cagri == 1 and imlec(session) == yeni.yayin


def test_ayni_sehit_iki_haberde_tek_kayit(session, ortam):
    a = SahteAnalizci(analiz(), analiz())
    tara(session, ortam, [oge(1, 3), oge(2, 2)], a)
    assert session.query(Sehit).count() == 1
    s = session.query(Sehit).one()
    assert s.durum == Durum.onay_bekliyor and session.query(Kaynak).count() == 2
    assert s.ad == "Ali" and s.soyad == "KAYA"


_ALANLAR = ("ad", "soyad", "gorev", "memleket", "kurum", "kategori", "tarih_hassasiyeti",
            "sehadet_tarihi", "yil", "ay", "gun", "resmi_teyit", "kaynak_kodu", "durum")
_DOLU_KISI = Kisi(ad="ali", soyad="kaya", kategori="asker", sehadet_tarihi="2026-10-22",
                  gorev="Uydurma Rütbe", memleket="Uydurma İl", kurum="Uydurma Kurum")


def _bos_alanli_kayit(sehit_ekle, durum):
    """Haberin doldurabileceği her alanı boş/zayıf kayıt (yıl hassasiyetli, kategori diğer)."""
    return sehit_ekle(ad="Ali", soyad="KAYA", kategori="diger", tarih_hassasiyeti="yil",
                      sehadet_tarihi=None, yil=2026, resmi_teyit=False, durum=durum)


@pytest.mark.parametrize("durum", ["yayinda", "reddedildi"])
def test_yayindaki_kayda_sadece_kaynak_eklenir(session, ortam, sehit_ekle, durum):
    # Karar Q9: haber, yayındaki/reddedilmiş kaydı asla değiştirmez; yalnızca kaynak eklenir.
    s = _bos_alanli_kayit(sehit_ekle, durum)
    once = {a: getattr(s, a) for a in _ALANLAR}
    d = tara(session, ortam, [oge(1)], SahteAnalizci(analiz(kisiler=[_DOLU_KISI])))
    session.refresh(s)
    assert session.query(Sehit).count() == 1 and {a: getattr(s, a) for a in _ALANLAR} == once
    assert len(s.kaynaklar) == 1 and s.kaynaklar[0].kaynak_kodu == "haber" and d.birlesen == 1


def test_onay_bekleyen_kayit_haberle_doldurulur(session, ortam, sehit_ekle):
    s = _bos_alanli_kayit(sehit_ekle, "onay_bekliyor")
    tara(session, ortam, [oge(1)], SahteAnalizci(analiz(kisiler=[_DOLU_KISI])))
    session.refresh(s)
    assert (s.gorev, s.memleket, s.kurum, s.kategori) == ("Uydurma Rütbe", "Uydurma İl", "Uydurma Kurum", "asker")
    assert s.sehadet_tarihi == date(2026, 10, 22) and s.resmi_teyit is True and s.durum == Durum.onay_bekliyor


def test_reddedilen_dirilmez(session, ortam, sehit_ekle):
    s = sehit_ekle(ad="Ali", soyad="KAYA", sehadet_tarihi=date(2026, 10, 22), durum="reddedildi")
    tara(session, ortam, [oge(1)], SahteAnalizci())
    assert s.durum == Durum.reddedildi and session.query(Sehit).count() == 1


def test_isimsiz_taslak(session, ortam):
    tara(session, ortam, [oge(1)], SahteAnalizci(analiz(kisiler=[], isimsiz_sayisi=2)))
    s = session.query(Sehit).one()
    assert s.isimsiz and s.durum == Durum.onay_bekliyor
    assert session.query(Kaynak).one().metin.startswith("İsimsiz şehit sayısı: 2. Olay.")


def test_anma_haberi_kayit_uretmez(session, ortam):
    o = oge(1)
    tara(session, ortam, [o], SahteAnalizci(analiz(yeni_olay=False)))
    assert session.query(Sehit).count() == 0 and imlec(session) == o.yayin


def test_analiz_hatasi_imleci_tutar(session, ortam):
    o1, o2, o3 = oge(1, 3), oge(2, 2), oge(3, 1)
    d = tara(session, ortam, [o3, o2, o1], SahteAnalizci(analiz(), AnalizHatasi("x")))
    assert imlec(session) == o1.yayin and d.son_durum == "hata" and session.query(Sehit).count() == 1
    a = SahteAnalizci(analiz(), analiz())
    tara(session, ortam, [o3, o2, o1], a)
    assert a.cagri == 2 and imlec(session) == o3.yayin


def test_anahtar_yok_istek_yok(session, ortam):
    g = SahteGetirici()
    d = tara(session, ortam, [oge(1)], None, g)
    assert g.cagrilar == [] and d.son_mesaj == "API anahtarı yok" and d.son_durum == "hata"
    assert d.imlec is None


def test_gunluk_sinir(session, ortam, monkeypatch):
    monkeypatch.setattr(toplayici.get_settings(), "gunluk_analiz_siniri", 1)
    o1, o2 = oge(1, 3), oge(2, 2)
    a = SahteAnalizci(analiz())
    d = tara(session, ortam, [o2, o1], a)
    assert a.cagri == 1 and imlec(session) == o1.yayin and d.son_mesaj == "günlük analiz sınırı"
    assert d.son_durum == "basarili"


def test_sehit_gecmeyen_haber_analiz_edilmez(session, ortam):
    o = oge(1, baslik="Hava durumu")
    a = SahteAnalizci()
    tara(session, ortam, [o], a)
    assert a.cagri == 0 and imlec(session) == o.yayin


def test_toplayici_kayitlari_resmi_teyit_bayragi(session, ortam):
    tara(session, ortam, [oge(1)], SahteAnalizci(analiz(resmi_kurum_duyurusu=False)))
    assert session.query(Sehit).one().resmi_teyit is False


def test_izin_yok(session, ortam, monkeypatch):
    monkeypatch.setattr(toplayici.get_settings(), "kaynak_izinleri", ["egm"])
    g = SahteGetirici()
    d = tara(session, ortam, [oge(1)], SahteAnalizci(), g)
    assert d.son_mesaj == "izin yok" and g.cagrilar == []


def test_analiz_sayaci_gun_degisince_sifirlanir(session):
    assert toplayici.analiz_sayaci_artir(session, date(2026, 10, 22), 1)
    assert not toplayici.analiz_sayaci_artir(session, date(2026, 10, 22), 1)
    assert toplayici.analiz_sayaci_artir(session, date(2026, 10, 23), 1)


def test_ayni_saniyedeki_ogeler_kaybolmaz(session, ortam):
    a, b = oge(1, 2), oge(2, 2)  # aynı yayın anı
    assert a.yayin == b.yayin
    tara(session, ortam, [a, b], SahteAnalizci(analiz(), AnalizHatasi("x")))
    assert imlec(session) == a.yayin
    an = SahteAnalizci(analiz(kisiler=[Kisi(ad="veli", soyad="demir", kategori="asker")]))
    tara(session, ortam, [a, b], an)
    assert an.cagri == 1 and session.query(Sehit).count() == 2


def test_gelecek_tarihli_oge_imleci_surmez(session, ortam):
    gecmis, gelecek = oge(1, 2), oge(2, -3)
    a = SahteAnalizci()
    tara(session, ortam, [gecmis, gelecek], a)
    assert a.cagri == 1 and imlec(session) == gecmis.yayin


def test_takili_oge_ucuncu_denemede_atlanir(session, ortam):
    kotu, iyi = oge(1, 3), oge(2, 2)
    for _ in range(2):
        d = tara(session, ortam, [kotu, iyi], SahteAnalizci(AnalizHatasi("x")))
        assert d.son_durum == "hata" and d.imlec and imlec(session) is None
    a = SahteAnalizci(AnalizHatasi("x"), analiz())
    d = tara(session, ortam, [kotu, iyi], a)
    assert a.cagri == 2 and d.hatali == 1 and d.eklenen == 1
    assert d.son_mesaj == "3. denemede atlandı: 1" and imlec(session) == iyi.yayin


def test_makale_hatasi_sayaci_harcamaz(session, ortam, monkeypatch):
    def kotu(html, k):
        raise haber.KaynakHatasi("404")
    monkeypatch.setattr(haber, "makale_ayristir", kotu)
    tara(session, ortam, [oge(1)], SahteAnalizci())
    assert session.get(KaynakDurumu, toplayici.SAYAC_KODU) is None or not session.get(KaynakDurumu, toplayici.SAYAC_KODU).imlec


def test_hatali_taslak_mesaja_yazilir(session, ortam):
    d = tara(session, ortam, [oge(1)], SahteAnalizci(analiz(kisiler=[Kisi(ad="1", kategori="asker")])))
    assert d.hatali == 1 and "aktarılamadı" in d.son_mesaj


def test_ilk_calisma_sinir_istanbul_gece_yarisi(session, ortam):
    dun = HaberOgesi("hurriyet", "1", "u1", "Şehit", "", datetime(2026, 10, 22, 23, 59, tzinfo=TZ))
    bugun = HaberOgesi("hurriyet", "2", "u2", "Şehit", "", datetime(2026, 10, 23, 0, 1, tzinfo=TZ))
    a = SahteAnalizci()
    tara(session, ortam, [dun, bugun], a)
    assert a.cagri == 1 and imlec(session) == bugun.yayin


# --- imleç: 3 günlük kimlik kümesi (I3), TEXT sütun (C1), beklenmeyen hata koruması (I2) ---

def test_sonradan_eklenen_eski_tarihli_oge_islenir(session, ortam):
    yeni = oge(1, saat_once=1)
    tara(session, ortam, [yeni], SahteAnalizci())
    gec = oge(2, saat_once=5, baslik="Şehit 2")  # imleç zamanından eski, akışa sonradan girdi
    a = SahteAnalizci(analiz(kisiler=[Kisi(ad="veli", soyad="demir", kategori="asker")]))
    tara(session, ortam, [yeni, gec], a)
    assert a.cagri == 1 and session.query(Sehit).count() == 2
    assert imlec(session) == yeni.yayin  # son_yayin geri gitmez


def test_onceki_gunden_gec_gelen_oge_uc_gun_icinde_islenir(session, ortam):
    son = SIMDI - timedelta(hours=1)
    imlec_kur(session, toplayici.HaberImleci(son_yayin=son, islenen={"9": son.isoformat()}).yaz())
    gec, cok_eski = oge(2, gun_once=2), oge(3, gun_once=3, saat_once=1)
    a = SahteAnalizci()
    tara(session, ortam, [oge(9, saat_once=1), gec, cok_eski], a)
    assert a.cagri == 1 and set(imlec_nesnesi(session).islenen) == {"9", "2"}


def test_budama_uc_gunden_eskileri_atar(session, ortam):
    eski, yakin = SIMDI - timedelta(days=4), SIMDI - timedelta(days=1)
    imlec_kur(session, toplayici.HaberImleci(
        son_yayin=yakin, islenen={"eski": eski.isoformat(), "yakin": yakin.isoformat()},
        taban=SIMDI - timedelta(days=5)).yaz())
    a = SahteAnalizci()
    tara(session, ortam, [HaberOgesi("hurriyet", "yakin", "https://x/y", "Şehit", "", yakin)], a)
    im = imlec_nesnesi(session)
    assert a.cagri == 0 and im.islenen == {"yakin": yakin.isoformat()} and im.taban is None


def test_onceki_imlec_bicimi_okunur_tekrar_analiz_yok(session, ortam):
    an = SIMDI - timedelta(hours=3)
    imlec_kur(session, json.dumps({"son_yayin": an.isoformat(), "son_kimlikler": ["1"], "takili": None}))
    islenmis = HaberOgesi("hurriyet", "1", "https://x/1", "Şehit", "", an)
    ayni_an_yeni = HaberOgesi("hurriyet", "2", "https://x/2", "Şehit", "", an)
    daha_eski = HaberOgesi("hurriyet", "0", "https://x/0", "Şehit", "", an - timedelta(hours=1))
    a = SahteAnalizci()
    tara(session, ortam, [islenmis, ayni_an_yeni, daha_eski], a)
    assert a.cagri == 1 and "2" in imlec_nesnesi(session).islenen


def test_en_eski_duz_iso_imleci_o_ani_islenmis_sayar():
    an = SIMDI - timedelta(hours=3)
    im = toplayici.HaberImleci.oku(an.isoformat())
    assert not im.islenecek_mi(HaberOgesi("hurriyet", "1", "u", "b", "", an), SIMDI)
    assert im.islenecek_mi(HaberOgesi("hurriyet", "2", "u", "b", "", an + timedelta(seconds=1)), SIMDI)
    assert toplayici.HaberImleci.oku(None) is None and toplayici.HaberImleci.oku("bozuk") is None


def test_ilk_calismanin_tabani_bos_turda_da_kalir(session, ortam):
    a = SahteAnalizci()
    tara(session, ortam, [], a)  # bugün hiç haber yok
    tara(session, ortam, [oge(1, gun_once=1)], a)  # dünkü haber sonradan görünür: ilk çalışma geçmişi taşımaz
    assert a.cagri == 0 and imlec_nesnesi(session).taban is not None


def test_imlec_25_ayni_an_ve_takili_url_gidip_gelir(session):
    an = SIMDI - timedelta(hours=1)
    im = toplayici.HaberImleci()
    for i in range(25):
        im.isle(HaberOgesi("hurriyet", str(43351000 + i), "u", "b", "", an))
    im.takili = {"kimlik": "https://www.sabah.com.tr/gundem/2026/10/23/" + "uzun-baslik-" * 20, "deneme": 2}
    metin = im.yaz()
    assert len(metin) > 300  # eski VARCHAR(300) sütuna sığmazdı
    assert toplayici.HaberImleci.oku(metin) == im
    imlec_kur(session, metin)
    session.expire_all()
    assert toplayici.HaberImleci.oku(session.get(KaynakDurumu, "hurriyet").imlec) == im


def test_hurriyet_gercek_ornek_21_ayni_an(session, ortam):
    xml = (Path(__file__).parent.parent / "docs/superpowers/plans/kaynaklar/haber/veri/h_gundem.xml").read_text(encoding="utf-8")
    ogeler = haber.rss_ayristir(xml, haber.HABER_KAYNAKLARI["hurriyet"])
    bugun = [o for o in ogeler if o.yayin.astimezone(TZ).date() == SIMDI.date()]
    assert sum(o.yayin == datetime(2026, 10, 23, 7, 0, tzinfo=TZ) for o in bugun) == 21
    a = SahteAnalizci()
    tara(session, ortam, ogeler, a)
    metin = session.get(KaynakDurumu, "hurriyet").imlec
    assert len(metin) > 300 and set(toplayici.HaberImleci.oku(metin).islenen) == {o.kimlik for o in bugun}
    tara(session, ortam, ogeler, a)
    assert a.cagri == 0 and session.get(KaynakDurumu, "hurriyet").imlec == metin


def test_beklenmeyen_hata_takili_sayar_ucuncude_atlar(session, ortam, monkeypatch):
    def patlar(html, k):
        raise RuntimeError("ayrıştırıcı hatası")
    monkeypatch.setattr(haber, "makale_ayristir", patlar)
    kotu, iyi = oge(1, 3), oge(2, 2, baslik="Hava durumu")
    for n in (1, 2):
        d = tara(session, ortam, [kotu, iyi], SahteAnalizci())
        assert d.son_durum == "hata" and "RuntimeError: ayrıştırıcı hatası" in d.son_mesaj
        session.expire_all()
        assert imlec_nesnesi(session).takili == {"kimlik": "1", "deneme": n}
        assert "2" not in imlec_nesnesi(session).islenen  # ilk hatada durulur
    d = tara(session, ortam, [kotu, iyi], SahteAnalizci())
    assert d.hatali == 1 and d.son_mesaj == "3. denemede atlandı: 1"
    assert set(imlec_nesnesi(session).islenen) == {"1", "2"} and imlec_nesnesi(session).takili is None


@pytest.fixture
def gercek_savepoint_oturumu():
    """pysqlite, BEGIN'siz SAVEPOINT'in RELEASE'inde commit eder; PostgreSQL gibi davranması
    için SQLAlchemy'nin önerdiği tarif: sürücü işlem yönetmez, BEGIN'i SQLAlchemy yollar."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db import Base

    motor = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(motor, "connect")
    def _baglan(dbapi_baglanti, _kayit):
        dbapi_baglanti.isolation_level = None

    @event.listens_for(motor, "begin")
    def _basla(baglanti):
        baglanti.exec_driver_sql("BEGIN")

    Base.metadata.create_all(motor)
    with sessionmaker(motor)() as s:
        yield s
    motor.dispose()


def test_beklenmeyen_hata_ogenin_yarim_isini_geri_alir(gercek_savepoint_oturumu, ortam, monkeypatch):
    session = gercek_savepoint_oturumu
    gercek = toplayici.kayit_aktar

    def yarim(s, ham, **kw):
        gercek(s, ham, **kw)
        raise RuntimeError("taslak sonrası")
    monkeypatch.setattr(toplayici, "kayit_aktar", yarim)
    d = tara(session, ortam, [oge(1)], SahteAnalizci())
    assert d.son_durum == "hata" and session.query(Sehit).count() == 0 and d.eklenen == 0
    assert session.get(KaynakDurumu, toplayici.SAYAC_KODU).imlec.endswith(":1")  # harcanan analiz sayılır
    assert imlec_nesnesi(session).takili == {"kimlik": "1", "deneme": 1}


# --- resmî sayfa taraması ve birleşik çalıştırma (Task 5) ---

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.aktarim import kayit_aktar  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402
from app.kaynaklar import HamKayit, KaynakHatasi, egm, sg  # noqa: E402


def _ham(kod, kimlik, ad):
    return HamKayit(kaynak_kodu=kod, dis_kimlik=kimlik, ad=ad, soyad="Test",
                    tarih=date(2026, 10, 20), hassasiyet="tam")


def _tamamla(s, kod, imlec="son"):
    s.add(KaynakDurumu(kaynak_kodu=kod, tamamlandi=True, imlec=imlec,
                       eklenen=0, birlesen=0, atlanan=0, hatali=0))
    s.commit()


def _egm_sayfalari(tuketilen):
    def sayfalar(g, *, baslangic):
        assert baslangic is None
        for etiket, kayitlar in [
            ("sehitlerimiz:1", [_ham("egm", "/a", "Ali"), _ham("egm", "/b", "Veli")]),
            ("sehitlerimiz:2", [_ham("egm", "/c", "Can")]),
            ("sehitlerimiz:3", [_ham("egm", "/d", "Deniz")]),
            ("ozelharekat:1", [_ham("egm", "/e", "Efe")]),
        ]:
            tuketilen.append(etiket)
            yield etiket, kayitlar
    return sayfalar


def test_resmi_toplu_aktarim_yokken_istek_atmaz(session, monkeypatch):
    def patlar(g, *, baslangic):
        raise AssertionError("istek atılmamalı")
    monkeypatch.setattr(egm, "sayfalar", patlar)
    d = toplayici.resmi_kaynak_tara(session, "egm", SahteGetirici())
    assert d.kaynak_kodu == "egm_toplayici" and "aktar egm" in d.son_mesaj
    assert session.scalar(select(Sehit.id)) is None


def test_resmi_tarama_yeni_onay_bekliyor_bilinen_atlandi_imlec_degismez(session, monkeypatch):
    kayit_aktar(session, _ham("egm", "/a", "Ali"))  # toplu aktarımda yayına alınmış
    session.commit()
    _tamamla(session, "egm", imlec="istihbarat:1")
    tuketilen = []
    monkeypatch.setattr(egm, "sayfalar", _egm_sayfalari(tuketilen))
    d = toplayici.resmi_kaynak_tara(session, "egm", SahteGetirici())
    assert tuketilen == ["sehitlerimiz:1", "sehitlerimiz:2"]  # 3. sayfa istenmez
    assert (d.eklenen, d.atlanan, d.son_durum) == (2, 1, "basarili")
    durumlar = {x.ad: x.durum for x in session.scalars(select(Sehit))}
    assert durumlar == {"Ali": "yayinda", "Veli": "onay_bekliyor", "Can": "onay_bekliyor"}
    toplu = session.get(KaynakDurumu, "egm")
    assert toplu.imlec == "istihbarat:1" and toplu.tamamlandi and toplu.eklenen == 0


def test_resmi_izin_yoksa(session, monkeypatch):
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["hurriyet"])
    d = toplayici.resmi_kaynak_tara(session, "sg", SahteGetirici())
    assert d.son_mesaj == "izin yok" and d.son_durum == "atlandi"


def test_resmi_sg_tek_sayfa(session, monkeypatch):
    _tamamla(session, "sg", imlec="1")
    monkeypatch.setattr(sg, "sayfalar", lambda g, *, baslangic: iter([("1", [_ham("sg", "/x", "Sinan")])]))
    d = toplayici.resmi_kaynak_tara(session, "sg", SahteGetirici())
    assert d.eklenen == 1 and session.scalar(select(Sehit.durum)) == "onay_bekliyor"
    assert session.get(KaynakDurumu, "sg").imlec == "1"


def test_resmi_kaynak_hatasi_durum_satirina_yazilir(session, monkeypatch):
    _tamamla(session, "sg", imlec="1")

    def bozuk(g, *, baslangic):
        raise KaynakHatasi("ağ koptu")
        yield  # pragma: no cover
    monkeypatch.setattr(sg, "sayfalar", bozuk)
    d = toplayici.resmi_kaynak_tara(session, "sg", SahteGetirici())
    assert d.son_durum == "hata" and "ağ koptu" in d.son_mesaj


@pytest.fixture
def fabrika():
    motor = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(motor)
    yield sessionmaker(motor)
    motor.dispose()


def test_calistir_bir_kaynak_patlarsa_digerleri_calisir(fabrika, monkeypatch, ortam):
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["egm", "sg", "hurriyet"])
    with fabrika() as s:
        _tamamla(s, "egm")
        _tamamla(s, "sg")

    def patlar(g, *, baslangic):
        raise RuntimeError("beklenmedik")
        yield  # pragma: no cover
    monkeypatch.setattr(egm, "sayfalar", patlar)
    monkeypatch.setattr(sg, "sayfalar", lambda g, *, baslangic: iter([("1", [_ham("sg", "/x", "Sinan")])]))
    ortam.ogeler = [oge(1)]
    sonuc = toplayici.toplayici_calistir(fabrika, g=SahteGetirici(), analizci=SahteAnalizci(), simdi=SIMDI)
    assert [d.kaynak_kodu for d in sonuc] == ["egm_toplayici", "sg_toplayici", "hurriyet"]
    assert [d.son_durum for d in sonuc] == ["hata", "basarili", "basarili"]
    assert "RuntimeError" in sonuc[0].son_mesaj
    assert sonuc[1].eklenen == 1 and sonuc[2].eklenen == 1  # oturum kapandıktan sonra da okunabilir


def test_calistir_analizci_yoksa_haber_api_anahtari_yok(fabrika, monkeypatch, ortam):
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["hurriyet"])
    monkeypatch.setattr(toplayici, "analizci_olustur", lambda ayar: None)
    sonuc = toplayici.toplayici_calistir(fabrika, g=SahteGetirici(), simdi=SIMDI)
    assert [(d.kaynak_kodu, d.son_durum) for d in sonuc] == [
        ("egm_toplayici", "atlandi"), ("sg_toplayici", "atlandi"), ("hurriyet", "hata")]
    assert sonuc[2].son_mesaj == "API anahtarı yok"


def test_calistir_kaynak_secimi(fabrika, monkeypatch):
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["egm", "sg"])
    sonuc = toplayici.toplayici_calistir(fabrika, g=SahteGetirici(), analizci=SahteAnalizci(),
                                         simdi=SIMDI, kodlar=["sg"])
    assert [d.kaynak_kodu for d in sonuc] == ["sg_toplayici"]


# --- eşzamanlılık kilidi (M1) ---

def _kilit_kur(fabrika, an):
    from datetime import timezone
    with fabrika() as s:
        s.add(KaynakDurumu(kaynak_kodu=toplayici.KILIT_KODU,
                           imlec=an.astimezone(timezone.utc).isoformat(timespec="seconds"),
                           eklenen=0, birlesen=0, atlanan=0, hatali=0))
        s.commit()


def test_kilit_tutuluyorsa_is_yapmadan_doner(fabrika, monkeypatch, ortam, caplog):
    from datetime import timezone
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["hurriyet"])
    _kilit_kur(fabrika, datetime.now(timezone.utc))
    ortam.ogeler = [oge(1)]
    a = SahteAnalizci()
    with caplog.at_level("WARNING"):
        sonuc = toplayici.toplayici_calistir(fabrika, g=SahteGetirici(), analizci=a, simdi=SIMDI)
    assert sonuc == [] and a.cagri == 0 and toplayici.ZATEN_CALISIYOR in caplog.text
    with fabrika() as s:
        assert s.get(KaynakDurumu, "hurriyet") is None and toplayici.toplayici_calisiyor_mu(s)


def test_bayat_kilit_alinir_calisirken_tutulur_sonra_birakilir(fabrika, monkeypatch):
    from datetime import timezone
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["hurriyet"])
    _kilit_kur(fabrika, datetime.now(timezone.utc) - timedelta(minutes=21))  # çökmüş tur kalıntısı
    calisirken = []

    def getir(g, k):
        with fabrika() as s:
            calisirken.append(toplayici.toplayici_calisiyor_mu(s))
        return []
    monkeypatch.setattr(haber, "ogeleri_getir", getir)
    sonuc = toplayici.toplayici_calistir(fabrika, g=SahteGetirici(), analizci=SahteAnalizci(), simdi=SIMDI)
    assert [d.kaynak_kodu for d in sonuc] == ["egm_toplayici", "sg_toplayici", "hurriyet"]
    assert calisirken == [True]
    with fabrika() as s:
        assert not toplayici.toplayici_calisiyor_mu(s) and s.get(KaynakDurumu, toplayici.KILIT_KODU).imlec is None


def test_kilit_hata_olsa_da_birakilir(fabrika, monkeypatch):
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["hurriyet"])

    def patlar(*a, **k):
        raise KeyboardInterrupt
    monkeypatch.setattr(toplayici, "resmi_kaynak_tara", patlar)
    with pytest.raises(KeyboardInterrupt):
        toplayici.toplayici_calistir(fabrika, g=SahteGetirici(), analizci=SahteAnalizci(), simdi=SIMDI)
    with fabrika() as s:
        assert not toplayici.toplayici_calisiyor_mu(s)


# --- istem enjeksiyonu sınırı (M5) ---

def test_kisi_sayisi_20_ile_sinirlanir(session, ortam, caplog):
    kisiler = [Kisi(ad=f"ad{i}", soyad=f"soyad{i}", kategori="asker") for i in range(25)]
    with caplog.at_level("WARNING"):
        d = tara(session, ortam, [oge(1)], SahteAnalizci(analiz(kisiler=kisiler)))
    assert d.eklenen == 20 and session.query(Sehit).count() == 20
    assert "25 kişi" in caplog.text and "20" in caplog.text


def test_calisiyor_mu_postgresqlde_advisory_lock_dener():
    from types import SimpleNamespace

    class Sahte:
        def __init__(self, alinir):
            self.alinir, self.sorgular = alinir, []

        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def scalar(self, sorgu, p):
            self.sorgular.append((str(sorgu), p))
            return self.alinir

        def execute(self, sorgu, p):
            self.sorgular.append((str(sorgu), p))

    tutuluyor = Sahte(False)
    assert toplayici.toplayici_calisiyor_mu(tutuluyor) is True and len(tutuluyor.sorgular) == 1
    bos = Sahte(True)  # alınabildi: hemen bırakılır
    assert toplayici.toplayici_calisiyor_mu(bos) is False
    assert [q for q, _ in bos.sorgular] == ["SELECT pg_try_advisory_lock(:k)", "SELECT pg_advisory_unlock(:k)"]
