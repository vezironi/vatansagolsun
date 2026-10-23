"""Analiz sağlayıcıları (OpenAI, Gemini, Claude) ve SDK hatalarının ortak sınıflandırması.

Her sağlayıcı aynı SISTEM_ISTEMI ve kullanıcı içeriğiyle çalışır, çıktıyı HaberAnalizi'ye doğrular ve
SDK hatalarını ikiye ayırır:
- SaglayiciTukendi: kalıcı (kimlik/yetki geçersiz, kredi/kota bitti); zincir sağlayıcıyı bir süre atlar.
- SaglayiciGecici: geçici (ağ, zaman aşımı, hız sınırı, 5xx, ret, bozuk çıktı).
Hata iletileri yalnızca sınıf adı/sabit metin taşır; API anahtarı hiçbir yerde yazılmaz.
"""
import os
from datetime import datetime

import anthropic
import openai
from google import genai
from google.genai import errors as gerrors
from google.genai import types as gtypes
from pydantic import ValidationError

from app.analiz import (
    HaberAnalizi,
    ISTEK_ZAMAN_ASIMI,
    SDK_YENIDEN_DENEME,
    SISTEM_ISTEMI,
    SaglayiciGecici,
    SaglayiciTukendi,
    kullanici_icerigi,
)

__all__ = ["ClaudeAnalizci", "GeminiAnalizci", "OpenAIAnalizci", "SaglayiciGecici", "SaglayiciTukendi",
           "gemini_anahtari"]


def gemini_anahtari(ayar_anahtari: str = "") -> str:
    """Ayar, sonra GEMINI_API_KEY, sonra GOOGLE_API_KEY."""
    return ayar_anahtari or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")


class OpenAIAnalizci:
    ad = "openai"

    def __init__(self, model: str, istemci=None, api_anahtari: str = ""):
        self.model = model
        if istemci is None:
            kimlik = {"api_key": api_anahtari} if api_anahtari else {}
            istemci = openai.OpenAI(**kimlik, timeout=ISTEK_ZAMAN_ASIMI, max_retries=SDK_YENIDEN_DENEME)
        self.istemci = istemci

    def analiz_et(self, *, baslik: str, govde: str, yayin: datetime) -> HaberAnalizi:
        try:
            yanit = self.istemci.responses.parse(
                model=self.model,
                instructions=SISTEM_ISTEMI,
                input=kullanici_icerigi(baslik, govde, yayin),
                text_format=HaberAnalizi,
            )
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            raise SaglayiciTukendi("OpenAI kimlik doğrulaması/yetkisi başarısız") from e
        except openai.APIStatusError as e:
            # insufficient_quota: kredi/kota bitti (kalıcı). Düz 429 hız sınırıdır (geçici).
            if e.status_code == 402 or getattr(e, "code", None) == "insufficient_quota":
                raise SaglayiciTukendi("OpenAI kredisi/kotası bitti") from e
            raise SaglayiciGecici(f"OpenAI isteği başarısız: {type(e).__name__} {e.status_code}") from e
        except openai.APIError as e:  # bağlantı ve zaman aşımı dahil
            raise SaglayiciGecici(f"OpenAI isteği başarısız: {type(e).__name__}") from e
        except ValueError as e:  # parse() çıktıyı kendisi doğrular (ValidationError)
            raise SaglayiciGecici("OpenAI çıktısı çözümlenemedi") from e
        for oge in getattr(yanit, "output", None) or []:
            for parca in getattr(oge, "content", None) or []:
                if getattr(parca, "type", None) == "refusal":
                    raise SaglayiciGecici("OpenAI isteği reddetti")
        if yanit.output_parsed is None:
            raise SaglayiciGecici("OpenAI geçerli bir çıktı üretmedi")
        return yanit.output_parsed


def _gemini_kota_bitti(e: gerrors.APIError) -> bool:
    """429 RESOURCE_EXHAUSTED günlük kota bitişi mi, yoksa geçici hız sınırı mı?

    Yalnızca açıkça günlük olan kota "tükendi" sayılır: QuotaFailure quotaId'sinde "PerDay" ya da
    iletide "per day"/"daily". Dakikalık ya da belirsiz 429 geçicidir (sağlayıcı 24 saat parka alınmaz).
    """
    ayrinti = e.details.get("error", e.details) if isinstance(e.details, dict) else {}
    kimlikler = [str(v.get("quotaId", "")).lower()
                 for d in (ayrinti.get("details") or []) if isinstance(d, dict)
                 for v in (d.get("violations") or []) if isinstance(v, dict)]
    if any("perday" in k for k in kimlikler):
        return True
    mesaj = str(ayrinti.get("message", "")).lower()
    return "per day" in mesaj or "daily" in mesaj


class GeminiAnalizci:
    ad = "gemini"

    def __init__(self, model: str, istemci=None, api_anahtari: str = ""):
        self.model = model
        if istemci is None:
            istemci = genai.Client(
                api_key=gemini_anahtari(api_anahtari) or None,
                http_options=gtypes.HttpOptions(
                    timeout=int(ISTEK_ZAMAN_ASIMI * 1000),  # milisaniye
                    retry_options=gtypes.HttpRetryOptions(attempts=SDK_YENIDEN_DENEME + 1),
                ),
            )
        self.istemci = istemci

    def analiz_et(self, *, baslik: str, govde: str, yayin: datetime) -> HaberAnalizi:
        try:
            yanit = self.istemci.models.generate_content(
                model=self.model,
                contents=kullanici_icerigi(baslik, govde, yayin),
                config=gtypes.GenerateContentConfig(
                    system_instruction=SISTEM_ISTEMI,
                    response_mime_type="application/json",
                    response_schema=HaberAnalizi,
                ),
            )
        except gerrors.ClientError as e:
            mesaj = str(e.message or "").lower()
            if e.code in (401, 402, 403) or (e.code == 400 and "api key" in mesaj):
                raise SaglayiciTukendi("Gemini kimlik doğrulaması/yetkisi başarısız") from e
            if e.code == 429 and _gemini_kota_bitti(e):
                raise SaglayiciTukendi("Gemini kotası bitti") from e
            raise SaglayiciGecici(f"Gemini isteği başarısız: {type(e).__name__} {e.code}") from e
        except gerrors.APIError as e:  # ServerError dahil
            raise SaglayiciGecici(f"Gemini isteği başarısız: {type(e).__name__} {e.code}") from e
        except ValueError as e:
            raise SaglayiciGecici("Gemini çıktısı çözümlenemedi") from e
        except Exception as e:  # SDK ağ/zaman aşımı hataları httpx istisnası olarak sızar
            raise SaglayiciGecici(f"Gemini isteği başarısız: {type(e).__name__}") from e
        parsed = getattr(yanit, "parsed", None)
        if parsed is None:
            raise SaglayiciGecici("Gemini geçerli bir çıktı üretmedi")
        if isinstance(parsed, HaberAnalizi):
            return parsed
        try:
            return HaberAnalizi.model_validate(parsed)
        except ValidationError as e:
            raise SaglayiciGecici("Gemini çıktısı şemaya uymuyor") from e


class ClaudeAnalizci:
    ad = "claude"

    def __init__(self, *, model: str, istemci: anthropic.Anthropic | None = None, api_anahtari: str = ""):
        self.model = model
        if istemci is None:
            kimlik = {"api_key": api_anahtari} if api_anahtari else {}
            istemci = anthropic.Anthropic(**kimlik, timeout=ISTEK_ZAMAN_ASIMI, max_retries=SDK_YENIDEN_DENEME)
        self.istemci = istemci

    def analiz_et(self, *, baslik: str, govde: str, yayin: datetime) -> HaberAnalizi:
        try:
            yanit = self.istemci.messages.parse(
                model=self.model,
                max_tokens=4096,
                system=SISTEM_ISTEMI,
                messages=[{"role": "user", "content": kullanici_icerigi(baslik, govde, yayin)}],
                output_format=HaberAnalizi,
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            raise SaglayiciTukendi("Claude kimlik doğrulaması/yetkisi başarısız") from e
        except anthropic.APIStatusError as e:
            if e.status_code == 402 or (e.status_code == 400 and "credit balance" in str(e).lower()):
                raise SaglayiciTukendi("Claude kredi bakiyesi yetersiz") from e
            raise SaglayiciGecici(f"Claude isteği başarısız: {type(e).__name__} {e.status_code}") from e
        except anthropic.APIError as e:
            raise SaglayiciGecici(f"Claude isteği başarısız: {type(e).__name__}") from e
        except ValueError as e:  # parse() çıktıyı kendisi doğrular (ValidationError)
            raise SaglayiciGecici("Claude çıktısı çözümlenemedi") from e
        if yanit.stop_reason == "refusal":
            raise SaglayiciGecici("Claude isteği reddetti")
        if yanit.parsed_output is None:
            raise SaglayiciGecici("Claude geçerli bir çıktı üretmedi")
        return yanit.parsed_output
