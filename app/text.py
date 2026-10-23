"""Türkçe metin yardımcıları: büyük/küçük harf, ad düzeni, arama katlama, slug."""
import re

_KATLA_TABLO = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def tr_lower(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def tr_upper(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()


def ad_duzenle(s: str) -> str:
    kelimeler = s.split()
    return " ".join(tr_upper(k[0]) + tr_lower(k[1:]) for k in kelimeler)


def soyad_duzenle(s: str) -> str:
    return tr_upper(s.strip())


def katla(s: str) -> str:
    s = tr_lower(s).translate(_KATLA_TABLO)
    return re.sub(r"\s+", " ", s).strip()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", katla(s)).strip("-")


def gorunen_ad(ad: str, soyad: str | None, lakap: str | None) -> str:
    if soyad:
        return f"{ad} {soyad}"
    if lakap:
        return f"{ad} — {lakap}"
    return ad
