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
_GORUNMEZ = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")


def metin_temizle(s: str | None) -> str:
    """Görünmez karakterleri atar, NBSP'yi boşluğa çevirir, boşlukları sadeleştirir."""
    s = _GORUNMEZ.sub("", str(s or "")).replace("\xa0", " ")
    return " ".join(s.split())


def alan_temizle(deger) -> str | None:
    """metin_temizle; boş ve "-" değerler None olur."""
    metin = metin_temizle(deger)
    return None if metin in ("", "-") else metin


def _tam(yil: int, ay: int, gun: int):
    try:
        return date(yil, ay, gun), Hassasiyet.tam, yil
    except ValueError:
        return _YOK


def tarih_coz(metin: str | None) -> tuple[date | None, Hassasiyet, int | None]:
    m = katla(metin_temizle(metin))
    if not m:
        return _YOK
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


# Unvan/rütbe önekleri: yazılış -> görevdeki karşılığı (None: atılır, ör. "Şehit", "ULŞ.").
# Baştaki öneklerin hepsi sırayla açılıp birleştirilir: "P. ASB. KD. BÇVŞ." -> "Piyade Astsubay
# Kıdemli Başçavuş". Eşleştirme katlanmış sözcüklerle, en uzun önek önce yapılır.
RUTBE_ONEKLERI: dict[str, str | None] = {
    # onur unvanları
    "Şehit": None,
    "Şehidimiz": None,
    "ULŞ.": None,
    # tam sözcükler
    "Polis Memuru": "Polis Memuru",
    "Kıdemli Başpolis Memuru": "Kıdemli Başpolis Memuru",
    "Başpolis Memuru": "Başpolis Memuru",
    "Komiser Yardımcısı": "Komiser Yardımcısı",
    "Komiser": "Komiser",
    "Başkomiser": "Başkomiser",
    "Emniyet Amiri": "Emniyet Amiri",
    "Emniyet Müdürü": "Emniyet Müdürü",
    "Emniyet Müdür Yardımcısı": "Emniyet Müdür Yardımcısı",
    **{f"{n}. Sınıf Emniyet Müdürü": f"{n}. Sınıf Emniyet Müdürü" for n in range(1, 5)},
    **{f"{n}. Sınıf": f"{n}. Sınıf Emniyet Müdürü" for n in range(1, 5)},
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
    "Piyade": "Piyade",
    "Jandarma": "Jandarma",
    # kısaltmalar (TSK yazımı)
    "P.": "Piyade",
    "J.": "Jandarma",
    "HV.": "Hava",
    "DZ.": "Deniz",
    "SVN.": "Savunma",
    "PLT.": "Pilot",
    "BKM.": "Bakım",
    "İST.": "İstihkam",
    "İSTH.": "İstihbarat",
    "İKM.": "İkmal",
    "KOM.": "Komando",
    "MHN.": "Muhabere",
    "TOP.": "Topçu",
    "TNK.": "Tank",
    "ASB.": "Astsubay",
    "ASTSB.": "Astsubay",
    "KD.": "Kıdemli",
    "BÇVŞ.": "Başçavuş",
    "ÜÇVŞ.": "Üstçavuş",
    "ÇVŞ.": "Çavuş",
    "UZM.": "Uzman",
    "ONB.": "Onbaşı",
    "SÖZ.": "Sözleşmeli",
    "TĞM.": "Teğmen",
    "ÜTĞM.": "Üsteğmen",
    "YZB.": "Yüzbaşı",
    "BNB.": "Binbaşı",
    "YB.": "Yarbay",
    "YRB.": "Yarbay",
    "ALB.": "Albay",
    "TUĞG.": "Tuğgeneral",
    "TÜMG.": "Tümgeneral",
    "KORG.": "Korgeneral",
    "ORG.": "Orgeneral",
    "PROF.": "Prof.",
    "DR.": "Dr.",
}

_ONEKLER = sorted(
    ((tuple(katla(k).split()), v) for k, v in RUTBE_ONEKLERI.items()),
    key=lambda x: -len(x[0]),
)
_AYIRICILAR = {"ve", "-", "–", ",", "/", "&"}


def _normalle(ham: str) -> str:
    s = metin_temizle(ham)
    s = re.sub(r"(\d+)\.\s*(?=\S)", r"\1. ", s)  # "4.sınıf" -> "4. sınıf"
    return re.sub(r"\.(?=[^\W\d_])", ". ", s)  # "UZM.ÇVŞ." -> "UZM. ÇVŞ."


def _onekleri_tuket(katli: list[str], i: int) -> tuple[int, list[str]]:
    """i'den başlayan ardışık önekleri tüketir: (ilk önek olmayan sözcük, görev parçaları)."""
    parcalar: list[str] = []
    while i < len(katli):
        for onek, deger in _ONEKLER:
            n = len(onek)
            if tuple(katli[i:i + n]) == onek:
                if deger is not None:
                    parcalar.append(deger)
                i += n
                break
        else:
            break
    return i, parcalar


def isim_ayir(ham: str, *, soyadli: bool) -> tuple[str, str | None, str | None]:
    """Baştaki unvan/rütbeleri görev olarak ayırır; kalan ad (ve soyadlıysa son sözcük soyad).

    Yalnızca önekten oluşan metinde ad boş döner: ("", None, görev).
    """
    sozcukler = _normalle(ham).split()
    i, parcalar = _onekleri_tuket([katla(s) for s in sozcukler], 0)
    gorev = " ".join(parcalar) or None
    kalan = sozcukler[i:]
    if not kalan:
        return "", None, gorev
    if soyadli and len(kalan) >= 2:
        return ad_duzenle(" ".join(kalan[:-1])), soyad_duzenle(kalan[-1]), gorev
    return ad_duzenle(" ".join(kalan)), None, gorev


def kisileri_ayir(baslik: str) -> list[str]:
    """Birden çok kişinin yazıldığı başlığı kişi kişi böler.

    Adın ardından gelen yeni bir unvan/rütbe dizisi (arkasında en az bir ad sözcüğüyle) ya da
    tek başına duran "ve", "-", "–", ",", "/", "&" yeni kişiye geçer.
    """
    sozcukler = _normalle(baslik).split()
    katli = [katla(s) for s in sozcukler]
    kisiler: list[list[str]] = []
    mevcut: list[str] = []
    adli = False  # mevcut kişide önek dışında sözcük var mı
    i = 0
    while i < len(sozcukler):
        if katli[i] in _AYIRICILAR:
            if mevcut:
                kisiler.append(mevcut)
            mevcut, adli, i = [], False, i + 1
            continue
        son, _ = _onekleri_tuket(katli, i)
        if son > i and (not adli or (son < len(sozcukler) and katli[son] not in _AYIRICILAR)):
            if adli:
                kisiler.append(mevcut)
                mevcut, adli = [], False
            mevcut.extend(sozcukler[i:son])
            i = son
            continue
        mevcut.append(sozcukler[i])  # ad sözcüğü (sondaki "ER", "BEKÇİ" gibi soyadlar dahil)
        adli, i = True, i + 1
    if mevcut:
        kisiler.append(mevcut)
    return [" ".join(k) for k in kisiler]


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
