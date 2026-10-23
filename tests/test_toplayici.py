from datetime import date, datetime, timedelta

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


def imlec(s):
    return toplayici.HaberImleci.oku(s.get(KaynakDurumu, "hurriyet").imlec).son_yayin


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
