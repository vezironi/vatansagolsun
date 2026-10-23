from datetime import date

import pytest

from app import aktarim
from app.kaynaklar import HamKayit, KaynakHatasi
from app.models import Durum, Hassasiyet as H, KaynakDurumu, Sehit


def ham(**kw):
    v = dict(kaynak_kodu="kahramanlar", dis_kimlik=kw.pop("dk", "k1"), ad="Tayfun", soyad="Baş",
             tarih=date(2026, 6, 14), hassasiyet=H.tam, yil=2026, kaynak_adi="kahramanlar.org.tr")
    v.update(kw)
    return HamKayit(**v)


def test_yeni_ve_tekrar_atlanir(session):
    assert aktarim.kayit_aktar(session, ham()).durum == "yeni"
    assert aktarim.kayit_aktar(session, ham()).durum == "atlandi"
    assert session.query(Sehit).count() == 1


def test_resmi_kaynak_tarih_ve_ismi_ezer(session):
    aktarim.kayit_aktar(session, ham(ad="TAYFUN", soyad="BAŞ", gorev="Polis"))
    r = aktarim.kayit_aktar(session, ham(kaynak_kodu="egm", dk="/sehit-polis-memuru-tayfun-bas", gorev="Polis Memuru"))
    s = session.get(Sehit, r.sehit_id)
    assert r.durum == "birlesti" and s.gorev == "Polis Memuru" and s.kaynak_kodu == "egm" and len(s.kaynaklar) == 2


def test_dusuk_oncelik_sadece_bosluk_doldurur(session):
    aktarim.kayit_aktar(session, ham(kaynak_kodu="egm", dk="/x", memleket=None, gorev="Polis Memuru"))
    r = aktarim.kayit_aktar(session, ham(dk="k9", memleket="Sivas", gorev="Polis"))
    s = session.get(Sehit, r.sehit_id)
    assert (s.memleket, s.gorev, s.kaynak_kodu) == ("Sivas", "Polis Memuru", "egm")


def test_tarihsiz_kopya_baba_adiyla_birlesir(session):
    aktarim.kayit_aktar(session, ham(tarih=None, hassasiyet=H.bilinmiyor, yil=None, baba_adi="Ali", dk="a"))
    r = aktarim.kayit_aktar(session, ham(baba_adi="Ali", dk="b"))
    s = session.get(Sehit, r.sehit_id)
    assert r.durum == "birlesti" and s.sehadet_tarihi == date(2026, 6, 14) and session.query(Sehit).count() == 1


def test_farkli_tam_tarih_eslesmez(session):
    aktarim.kayit_aktar(session, ham(dk="a"))
    assert aktarim.kayit_aktar(session, ham(dk="b", tarih=date(2015, 1, 1), yil=2015)).durum == "yeni"


def test_reddedilmis_kayit_dirilmez(session, sehit_ekle):
    s = sehit_ekle(ad="Tayfun", soyad="Baş", sehadet_tarihi=date(2026, 6, 14), durum="reddedildi")
    r = aktarim.kayit_aktar(session, ham())
    session.refresh(s)
    assert r.durum == "birlesti" and s.durum == Durum.reddedildi


def test_bozuk_kayit_digerlerini_bozmaz(session):
    assert aktarim.kayit_aktar(session, ham(ad="", dk="bos")).durum == "hatali"
    assert aktarim.kayit_aktar(session, ham(dk="iyi")).durum == "yeni"


def test_kaynak_calistir_imlec_ve_hata(session):
    def sayfalar():
        yield "1", [ham(dk="p1")]
        yield "2", [ham(dk="p2", ad="Ali", soyad="Kaya")]
        raise KaynakHatasi("429")
    d = aktarim.kaynak_calistir(session, "kahramanlar", sayfalar())
    assert (d.imlec, d.son_durum, d.tamamlandi, d.eklenen) == ("2", "hata", False, 2)
    d2 = aktarim.kaynak_calistir(session, "kahramanlar", iter([("3", [ham(dk="p1")])]))
    assert (d2.imlec, d2.tamamlandi, d2.atlanan, d2.son_durum) == ("3", True, 1, "basarili")


# --- ek testler ---

def test_bosluk_ad_hatali_ve_firlatmaz(session):
    r = aktarim.kayit_aktar(session, ham(ad="   ", dk="x"))
    assert r.durum == "hatali" and r.sehit_id is None and r.mesaj


def test_savepoint_onceki_basarili_kayit_geri_alinmaz(session):
    aktarim.kayit_aktar(session, ham(dk="iyi"))
    r = aktarim.kayit_aktar(session, ham(dk="kotu", ad="Ali", tarih=None))  # tam hassasiyet, tarih yok
    assert r.durum == "hatali"
    session.commit()
    session.expire_all()
    assert session.query(Sehit).count() == 1


def test_uzun_metinler_kirpilir(session):
    r = aktarim.kayit_aktar(session, ham(dk="u", ad="A" * 300, donem="D" * 150, memleket="M" * 250))
    s = session.get(Sehit, r.sehit_id)
    assert r.durum == "yeni" and len(s.ad) == 200 and len(s.donem) == 100 and len(s.memleket) == 200


def test_yeni_kayit_resmi_teyit_ve_durum(session):
    r = aktarim.kayit_aktar(session, ham(), yeni_durum=Durum.onay_bekliyor)
    s = session.get(Sehit, r.sehit_id)
    assert s.resmi_teyit is True and s.isimsiz is False and s.durum == Durum.onay_bekliyor


def test_bilinmeyen_kaynak_kodu_oncelik_sifir(session, sehit_ekle):
    sehit_ekle(ad="Tayfun", soyad="Baş", sehadet_tarihi=date(2026, 6, 14))  # kaynak_kodu "test"
    r = aktarim.kayit_aktar(session, ham())  # kahramanlar (1) > test (0)
    assert session.get(Sehit, r.sehit_id).kaynak_kodu == "kahramanlar"


def test_onay_bekleyen_yayina_cikmaz(session, sehit_ekle):
    s = sehit_ekle(ad="Tayfun", soyad="Baş", sehadet_tarihi=date(2026, 6, 14), durum="onay_bekliyor")
    aktarim.kayit_aktar(session, ham(kaynak_kodu="egm", dk="e"))
    session.refresh(s)
    assert s.durum == Durum.onay_bekliyor


def test_yil_hassasiyetli_ayni_yil_eslesir(session):
    aktarim.kayit_aktar(session, ham(dk="a", tarih=None, hassasiyet=H.yil, yil=2026))
    r = aktarim.kayit_aktar(session, ham(dk="b"))
    s = session.get(Sehit, r.sehit_id)
    assert r.durum == "birlesti" and s.tarih_hassasiyeti == H.tam and s.sehadet_tarihi == date(2026, 6, 14)
    assert (s.yil, s.ay, s.gun) == (2026, 6, 14)


def test_yil_hassasiyetli_farkli_yil_eslesmez(session):
    aktarim.kayit_aktar(session, ham(dk="a", tarih=None, hassasiyet=H.yil, yil=2020))
    assert aktarim.kayit_aktar(session, ham(dk="b")).durum == "yeni"


def test_tarihsiz_cift_tek_aday_eslesir_iki_aday_eslesmez(session, sehit_ekle):
    kw = dict(tarih=None, hassasiyet=H.bilinmiyor, yil=None)
    aktarim.kayit_aktar(session, ham(dk="a", **kw))
    assert aktarim.kayit_aktar(session, ham(dk="b", **kw)).durum == "birlesti"
    sehit_ekle(ad="Tayfun", soyad="Baş", tarih_hassasiyeti="bilinmiyor", sehadet_tarihi=None)
    assert aktarim.kayit_aktar(session, ham(dk="c", **kw)).durum == "yeni"


def test_tarihsiz_farkli_baba_eslesmez(session):
    aktarim.kayit_aktar(session, ham(dk="a", tarih=None, hassasiyet=H.bilinmiyor, yil=None, baba_adi="Ali"))
    assert aktarim.kayit_aktar(session, ham(dk="b", baba_adi="Veli")).durum == "yeni"


def test_eslesen_bul_dogrudan(session):
    assert aktarim.eslesen_bul(session, ham()) is None
    aktarim.kayit_aktar(session, ham())
    assert aktarim.eslesen_bul(session, ham(dk="baska", ad="TAYFUN", soyad="BAŞ")) is not None


def test_birlestirme_alanlari_tutarli(session):
    aktarim.kayit_aktar(session, ham(ad="tayfun", soyad="baş"))
    r = aktarim.kayit_aktar(session, ham(kaynak_kodu="egm", dk="e", memleket="Sivas"))
    s = session.get(Sehit, r.sehit_id)
    assert s.ad == "Tayfun" and s.soyad == "BAŞ" and "sivas" in s.arama_metni and s.isim_anahtari == "tayfun bas"


def test_beklenmeyen_istisna_hatali(session, monkeypatch):
    def patla(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(aktarim.repo, "yeni_sehit", patla)
    r = aktarim.kayit_aktar(session, ham())
    assert r.durum == "hatali" and "boom" in r.mesaj


def test_kaynak_calistir_sayfa_ici_hata_sayilir(session):
    d = aktarim.kaynak_calistir(session, "kahramanlar", iter([("1", [ham(ad="", dk="b"), ham(dk="i")])]))
    assert (d.eklenen, d.hatali, d.tamamlandi, d.son_durum) == (1, 1, True, "basarili")
    assert d.son_calisma is not None


def test_kaynak_calistir_diger_istisna_kaydedilir_ve_yeniden_firlatilir(session):
    def sayfalar():
        yield "1", [ham(dk="p1")]
        raise ValueError("programlama hatasi")
    with pytest.raises(ValueError):
        aktarim.kaynak_calistir(session, "kahramanlar", sayfalar())
    d = session.get(KaynakDurumu, "kahramanlar")
    assert d.son_durum == "hata" and "programlama" in d.son_mesaj and d.imlec == "1" and not d.tamamlandi
    assert session.query(Sehit).count() == 1


def test_kaynak_durumu_olusturur(session):
    d = aktarim.kaynak_durumu(session, "egm")
    assert d.kaynak_kodu == "egm" and d.eklenen == 0 and aktarim.kaynak_durumu(session, "egm") is d


# --- inceleme turu 1 ---

def test_kayit_hatasi_loglanir_ve_son_mesaja_yazilir(session, caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="app.aktarim"):
        d = aktarim.kaynak_calistir(
            session, "kahramanlar", iter([("1", [ham(dk="kotu", ad="Ali", tarih=None), ham(dk="iyi")])])
        )
    assert d.hatali == 1 and d.eklenen == 1 and d.son_durum == "basarili"
    assert d.son_mesaj and len(d.son_mesaj) <= 500 and "[SQL:" not in d.son_mesaj
    assert "kahramanlar/kotu aktarılamadı" in caplog.text


def test_mesaj_sql_dokumu_atilir_ve_kirpilir():
    assert aktarim._temizle("Hata x [SQL: INSERT ...] [parameters: (1,)]") == "Hata x"
    assert len(aktarim._temizle("a" * 900)) == 500


def test_elle_duzenlenmis_kayit_ezilmez(session, sehit_ekle):
    # Panelde yalnızca yılı girilmiş tek kayıt; egm (öncelik 3) aynı yıl, tam tarih ve büyük harfli adla gelir.
    s = sehit_ekle(ad="Tayfun", soyad="Baş", tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=2026,
                   kaynak_kodu="kahramanlar", elle_duzenlendi=True, gorev=None)
    r = aktarim.kayit_aktar(session, ham(kaynak_kodu="egm", dk="e", ad="TAYFUN", soyad="BAŞ",
                                         tarih=date(2026, 6, 15), gorev="Polis Memuru", memleket="Sivas"))
    session.refresh(s)
    assert r.durum == "birlesti" and r.sehit_id == s.id and session.query(Sehit).count() == 1
    assert (s.ad, s.kaynak_kodu) == ("Tayfun", "kahramanlar")  # ad ("TAYFUN" değil) ve kaynak ezilmez
    assert (s.tarih_hassasiyeti, s.sehadet_tarihi, s.yil) == (H.yil, None, 2026)  # bilinen tarih kilitli
    assert (s.gorev, s.memleket) == ("Polis Memuru", "Sivas")  # boşlar dolar


def test_elle_duzenlenmis_adi_ve_dolu_gorevi_ezmez(session, sehit_ekle):
    s = sehit_ekle(ad="Tayfun", soyad="Baş", sehadet_tarihi=date(2026, 6, 14), kaynak_kodu="kahramanlar",
                   elle_duzenlendi=True, gorev="Komiser")
    aktarim.kayit_aktar(session, ham(kaynak_kodu="egm", dk="e", ad="TAYFUN", soyad="BAŞ", gorev="Polis Memuru"))
    session.refresh(s)
    assert (s.ad, s.gorev, s.kaynak_kodu) == ("Tayfun", "Komiser", "kahramanlar")


def test_belirsiz_eslesme_yeni_kayit_ve_uyari(session, sehit_ekle, caplog):
    import logging
    sehit_ekle(ad="Tayfun", soyad="Baş", sehadet_tarihi=date(2026, 6, 14))
    sehit_ekle(ad="Tayfun", soyad="Baş", sehadet_tarihi=date(2026, 6, 14))
    with caplog.at_level(logging.WARNING, logger="app.aktarim"):
        r = aktarim.kayit_aktar(session, ham())
    assert r.durum == "yeni" and session.query(Sehit).count() == 3
    assert "belirsiz eşleşme" in caplog.text


def test_tamamlandi_sifirlama_ilk_sayfadan_once_hata_olsa_da_kalici(session):
    d = aktarim.kaynak_durumu(session, "kahramanlar")
    d.tamamlandi = True
    session.commit()

    def sayfalar():
        raise KaynakHatasi("hemen")
        yield  # pragma: no cover

    d = aktarim.kaynak_calistir(session, "kahramanlar", sayfalar())
    session.expire_all()
    assert d.tamamlandi is False and d.son_durum == "hata"


def test_duz_str_kategori_firlatmaz(session, sehit_ekle):
    sehit_ekle(ad="Tayfun", soyad="Baş", sehadet_tarihi=date(2026, 6, 14), kategori="diger")
    r = aktarim.kayit_aktar(session, ham(kaynak_kodu="egm", dk="e", kategori="polis"))
    assert r.durum == "birlesti" and session.get(Sehit, r.sehit_id).kategori == "polis"


def test_savepoint_kaynak_insert_hatasinda_sehit_satiri_geri_alinir(session, monkeypatch):
    from app.models import Kaynak
    aktarim.kayit_aktar(session, ham(dk="once", ad="Ali", soyad="Bir"))
    # Kaynak eklenirken tekil kısıtı ihlal ettir: ayni (kaynak_kodu, dis_kimlik) ile ikinci satır
    asil = aktarim._kaynak_kaydi

    def bozuk(sehit, h):
        if h.dis_kimlik == "cakisan":
            k = asil(sehit, h)
            k.dis_kimlik = "once"
            return k
        return asil(sehit, h)

    monkeypatch.setattr(aktarim, "_kaynak_kaydi", bozuk)
    r = aktarim.kayit_aktar(session, ham(dk="cakisan", ad="Veli", soyad="Iki"))
    assert r.durum == "hatali" and "[SQL:" not in r.mesaj
    assert aktarim.kayit_aktar(session, ham(dk="sonra", ad="Can", soyad="Uc")).durum == "yeni"
    session.commit()
    session.expire_all()
    adlar = sorted(x.ad for x in session.query(Sehit))
    assert adlar == ["Ali", "Can"]  # Veli'nin Sehit INSERT'i geri alındı
    assert session.query(Kaynak).count() == 2


# --- son inceleme: C1 farklı kişiler birleşmez ---

def _osmanli(**kw):
    v = dict(kaynak_kodu="kahramanlar", ad="Mustafa", soyad=None, tarih=None, hassasiyet=H.bilinmiyor, yil=None,
             donem="BİRİNCİ DÜNYA SAVAŞI (1914-1918) ÇANAKKALE CEPHESİ", kurum=None)
    v.update(kw)
    return ham(**v)


def test_dort_farkli_mustafa_dort_satir(session):
    kayitlar = [
        _osmanli(dk="m1", baba_adi="Hasan", memleket="Kastamonu Araç", dogum_yili=1885),
        _osmanli(dk="m2", baba_adi="Ali", memleket="Çorum Kargı", dogum_yili=1885,
                 donem="BİRİNCİ DÜNYA SAVAŞI (1914-1918) IRAK CEPHESİ"),
        _osmanli(dk="m3", baba_adi="Osman", memleket="Mersin Mut", donem="BALKAN SAVAŞLARI"),
        _osmanli(dk="m4", memleket="Tekirdağ Malkara"),
    ]
    assert [aktarim.kayit_aktar(session, k).durum for k in kayitlar] == ["yeni"] * 4
    assert session.query(Sehit).count() == 4


def test_ayni_donem_ya_da_kurum_tek_isimde_yetmez(session):
    aktarim.kayit_aktar(session, _osmanli(dk="a", kurum="Kara Kuvvetleri"))
    assert aktarim.kayit_aktar(session, _osmanli(dk="b", kurum="Kara Kuvvetleri")).durum == "yeni"


def test_ayni_mustafa_iki_kaynaktan_birlesir(session):
    aktarim.kayit_aktar(session, _osmanli(kaynak_kodu="sehitlerimiz", dk="116", ad="MUSTAFA", baba_adi="Hasan",
                                          memleket="Kastamonu"))
    r = aktarim.kayit_aktar(session, _osmanli(dk="kh:1", baba_adi="HASAN", memleket="Kastamonu Araç",
                                              dogum_yili=1885))
    s = session.get(Sehit, r.sehit_id)
    assert r.durum == "birlesti" and session.query(Sehit).count() == 1
    assert (s.kaynak_kodu, s.dogum_yili, len(s.kaynaklar)) == ("sehitlerimiz", 1885, 2)


def test_tarihsiz_soyadli_iki_kaynaktan_birlesir(session):
    kw = dict(ad="Ali", soyad="KAYA", tarih=None, hassasiyet=H.bilinmiyor, yil=None)
    aktarim.kayit_aktar(session, ham(kaynak_kodu="sehitlerimiz", dk="1", **kw))
    assert aktarim.kayit_aktar(session, ham(dk="kh:1", memleket="Sivas", **kw)).durum == "birlesti"


def test_tek_isim_tarihsiz_tek_aday_birlesmez(session):
    aktarim.kayit_aktar(session, _osmanli(dk="a"))
    assert aktarim.kayit_aktar(session, _osmanli(dk="b", kaynak_kodu="sehitlerimiz")).durum == "yeni"


def test_ayni_tarih_ve_isim_farkli_baba_birlesmez(session):
    aktarim.kayit_aktar(session, ham(dk="a", baba_adi="Ali"))
    assert aktarim.kayit_aktar(session, ham(kaynak_kodu="egm", dk="b", baba_adi="Veli")).durum == "yeni"


def test_farkli_dogum_yili_birlesmez(session):
    aktarim.kayit_aktar(session, ham(dk="a", dogum_yili=1990))
    assert aktarim.kayit_aktar(session, ham(kaynak_kodu="egm", dk="b", dogum_yili=1991)).durum == "yeni"
    assert aktarim.kayit_aktar(session, ham(kaynak_kodu="egm", dk="c", dogum_yili=1990)).durum == "birlesti"


def test_tek_isimde_farkli_il_birlesmez_ayni_il_birlesir(session):
    aktarim.kayit_aktar(session, _osmanli(dk="a", baba_adi="Hasan", memleket="Kastamonu Araç"))
    assert aktarim.kayit_aktar(session, _osmanli(dk="b", baba_adi="Hasan", memleket="Antalya Alanya")).durum == "yeni"
    assert aktarim.kayit_aktar(session, _osmanli(dk="c", baba_adi="Hasan", memleket="KASTAMONU")).durum == "birlesti"


def test_elle_duzenlenmis_diger_kategorisi_ezilmez(session, sehit_ekle):
    s = sehit_ekle(ad="Tayfun", soyad="Baş", sehadet_tarihi=date(2026, 6, 14), kategori="diger",
                   elle_duzenlendi=True)
    r = aktarim.kayit_aktar(session, ham(kategori="polis"))
    session.refresh(s)
    assert r.durum == "birlesti" and s.kategori == "diger"


def test_harfsiz_ad_hatali(session):
    for ad in ("​", "-", "12"):
        r = aktarim.kayit_aktar(session, ham(ad=ad, dk="x" + ad))
        assert r.durum == "hatali" and r.sehit_id is None
    assert session.query(Sehit).count() == 0


def test_resmi_teyitsiz_ve_isimsiz_bayraklari(session):
    r = aktarim.kayit_aktar(session, ham(kaynak_kodu="haber", dk="hurriyet:1#0", resmi_teyit=False))
    s = session.get(Sehit, r.sehit_id)
    assert s.resmi_teyit is False and s.isimsiz is False


def test_isimsiz_kayit_eslestirilmez(session):
    a = aktarim.kayit_aktar(session, ham(ad="İsimsiz", soyad=None, kaynak_kodu="haber", dk="h:1#isimsiz", isimsiz=True, tarih=None, hassasiyet=H.bilinmiyor, yil=None))
    b = aktarim.kayit_aktar(session, ham(ad="İsimsiz", soyad=None, kaynak_kodu="haber", dk="h:2#isimsiz", isimsiz=True, tarih=None, hassasiyet=H.bilinmiyor, yil=None))
    assert (a.durum, b.durum) == ("yeni", "yeni") and a.sehit_id != b.sehit_id
    assert aktarim.kayit_aktar(session, ham(ad="İsimsiz", soyad=None, kaynak_kodu="haber", dk="h:1#isimsiz", isimsiz=True)).durum == "atlandi"
