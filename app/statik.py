"""Statik dosya adresleri: içerik özetiyle sürümlenir, böylece güncellenen CSS/JS
tarayıcı ya da CDN (Cloudflare) önbelleğindeki eski kopyaya takılmaz."""
import hashlib
from functools import lru_cache
from pathlib import Path

STATIK_DIZINI = Path(__file__).resolve().parent / "static"


@lru_cache
def statik(yol: str) -> str:
    try:
        ozet = hashlib.sha1((STATIK_DIZINI / yol).read_bytes()).hexdigest()[:10]
    except OSError:
        return f"/static/{yol}"
    return f"/static/{yol}?v={ozet}"
