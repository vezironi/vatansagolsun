"""Kaynak metinlerini ayrıştıran saf yardımcılar (ağa çıkmaz)."""
import re
from datetime import date

from app.models import Hassasiyet, Kategori
from app.text import ad_duzenle, katla, soyad_duzenle

_AYLAR = {
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6,
    "temmuz": 7, "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
}
_YOK = (None, Hassasiyet.bilinmiyor, None)

_SAYISAL = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_YAZILI = re.compile(r"(\d{1,2}) ([a-z]+) (\d{4})")
_YIL = re.compile(r"\d{4}")


def _tam(yil: int, ay: int, gun: int):
    try:
        return date(yil, ay, gun), Hassasiyet.tam, yil
    except ValueError:
        return _YOK


def tarih_coz(metin: str | None) -> tuple[date | None, Hassasiyet, int | None]:
    if not metin:
        return _YOK
    m = katla(metin)
    if (g := _SAYISAL.fullmatch(m)):
        return _tam(int(g[3]), int(g[2]), int(g[1]))
    if (g := _ISO.fullmatch(m)):
        return _tam(int(g[1]), int(g[2]), int(g[3]))
    if (g := _YAZILI.fullmatch(m)):
        ay = _AYLAR.get(g[2])
        return _tam(int(g[3]), ay, int(g[1])) if ay else _YOK
    if _YIL.fullmatch(m) and 1000 <= int(m) <= 2100:
        return None, Hassasiyet.yil, int(m)
    return _YOK


# Önek (katlanmış, boşlukla ayrılmış sözcükler) -> (kanonik görev | None, özgüllük).
# None görev: atılır. Özgüllük: kurum/silah kısaltması 1, rütbe/unvan 2.
RUTBE_ONEKLERI: dict[str, str | None] = {
    "Polis Memuru": "Polis Memuru",
    "Kıdemli Başpolis Memuru": "Kıdemli Başpolis Memuru",
    "Başpolis Memuru": "Başpolis Memuru",
    "Komiser Yardımcısı": "Komiser Yardımcısı",
    "Komiser": "Komiser",
    "Başkomiser": "Başkomiser",
    "Emniyet Amiri": "Emniyet Amiri",
    "Emniyet Müdürü": "Emniyet Müdürü",
    "Bekçi": "Bekçi",
    "Uzman Çavuş": "Uzman Çavuş",
    "Uzman Onbaşı": "Uzman Onbaşı",
    "Astsubay": "Astsubay",
    "Teğmen": "Teğmen",
    "Üsteğmen": "Üsteğmen",
    "Yüzbaşı": "Yüzbaşı",
    "Binbaşı": "Binbaşı",
    "Er": "Er",
    "Onbaşı": "Onbaşı",
    "Çavuş": "Çavuş",
    "Sözleşmeli Er": "Sözleşmeli Er",
    "UZM. ÇVŞ.": "Uzman Çavuş",
    "ULŞ.": None,
    "P.": "Piyade",
    "J.": "Jandarma",
    "KOM.": "Komando",
    "ASTSB.": "Astsubay",
    "ÜÇVŞ.": "Üstçavuş",
    "ÜTĞM.": "Üsteğmen",
    "TĞM.": "Teğmen",
    "YZB.": "Yüzbaşı",
}
_KURUM_KISALTMALARI = {"Piyade", "Jandarma", "Komando"}

_ONEKLER = sorted(
    ((katla(k).split(), v) for k, v in RUTBE_ONEKLERI.items()),
    key=lambda x: -len(x[0]),
)


def isim_ayir(ham: str, *, soyadli: bool) -> tuple[str, str | None, str | None]:
    sozcukler = ham.split()
    katli = [katla(s) for s in sozcukler]
    i = 0
    if katli and katli[0] == "sehit" and len(sozcukler) > 1:
        i = 1
    gorev: str | None = None
    ozgul = -1
    while i < len(sozcukler) - 1:
        for onek, deger in _ONEKLER:
            n = len(onek)
            if i + n < len(sozcukler) and katli[i:i + n] == onek:
                if deger is not None:
                    o = 1 if deger in _KURUM_KISALTMALARI else 2
                    if o >= ozgul:
                        gorev, ozgul = deger, o
                i += n
                break
        else:
            break
    kalan = sozcukler[i:]
    if soyadli and len(kalan) >= 2:
        return ad_duzenle(" ".join(kalan[:-1])), soyad_duzenle(kalan[-1]), gorev
    return ad_duzenle(" ".join(kalan)), None, gorev


def kategori_bul(*ipuclari: str | None) -> Kategori:
    metin = katla(" ".join(i for i in ipuclari if i))
    if any(k in metin for k in ("polis", "emniyet", "komiser", "bekci")):
        return Kategori.polis
    if "jandarma" in metin:
        return Kategori.jandarma
    if "ogretmen" in metin:
        return Kategori.ogretmen
    if any(k in metin for k in ("korucu", "sivil", "memur")):
        return Kategori.diger
    return Kategori.asker


SOYADI_KANUNU_YILI = 1934
_ESKI_DONEMLER = tuple(katla(d) for d in (
    "BALKAN", "BİRİNCİ DÜNYA", "KURTULUŞ", "KIRIM", "OSMANLI", "TRABLUSGARP",
    "MİLLİ MÜCADELE", "MUHAREBE DIŞI DİĞER ŞEHİTLER (1853-1928)",
))


def soyadli_mi(yil: int | None, donem: str | None) -> bool:
    if yil is not None:
        return yil >= SOYADI_KANUNU_YILI
    if donem:
        d = katla(donem)
        return not any(e in d for e in _ESKI_DONEMLER)
    return True
