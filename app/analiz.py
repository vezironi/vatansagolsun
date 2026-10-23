"""Haber metinlerinin Claude ile yapılandırılmış analizi."""
import os
from datetime import datetime
from typing import Literal, Protocol

import anthropic
from pydantic import BaseModel, Field

from app.dates import TZ

SISTEM_ISTEMI = """Sen Türk şehitlerini anan bir arşiv için haber metinlerini inceleyen bir analiz asistanısın.

Görevin: verilen haber başlığı ve metninin bir şehadet haberi olup olmadığını belirlemek ve haberdeki şehitlere ait bilgileri yapılandırılmış biçimde çıkarmak.

Kapsam: Türk şehitleri; asker, jandarma, polis, öğretmen, korucu ve resmî olarak şehit sayılan siviller. Yabancı askerlerin ölümleri kapsam dışıdır. Kaza veya hastalık sonucu ölüm haberleri ancak haber açıkça "şehit" diyorsa şehit haberidir.

Kurallar:
- Yalnızca metinde açıkça geçen bilgileri çıkar. Hiçbir isim, rütbe, memleket veya tarih uydurma; bilmediğin veya metinde olmayan alanı null bırak.
- İsimleri Türkçe yazımıyla, metindeki gibi yaz.
- Şehadet tarihi metinde yoksa, yayın tarihinden "bugün", "dün", "dünkü" gibi ifadelere göre çıkar (YYYY-AA-GG); çıkaramıyorsan null bırak.
- İsmi verilmeyen şehit sayısını ("2 askerimiz şehit oldu") isimsiz_sayisi alanına yaz. İsimleri verilen kişileri kisiler listesine ekle; aynı kişiyi iki kez sayma (isimli kişiyi isimsiz_sayisi'na ekleme).
- yeni_olay: şehadet, yayın tarihinden geriye en fazla 7 gün içinde yaşanmışsa true. Anma, cenaze veya yıl dönümü haberinde ölüm 7 günden eskiyse false.
- resmi_kurum_duyurusu: haber MSB, EGM, Jandarma Genel Komutanlığı veya valilik gibi resmî bir kurumun açıklamasını aktarıyorsa true.
- olay_ozeti: olayı tek cümleyle özetle.
- Şehit haberi değilse sehit_haberi=false, isimsiz_sayisi=0 ve kisiler boş olsun."""


class Kisi(BaseModel):
    ad: str
    soyad: str | None = None
    gorev: str | None = None
    kategori: Literal["asker", "jandarma", "polis", "ogretmen", "diger"]
    memleket: str | None = None
    kurum: str | None = None
    sehadet_tarihi: str | None = None  # YYYY-AA-GG


class HaberAnalizi(BaseModel):
    sehit_haberi: bool
    yeni_olay: bool  # son 7 gün içinde yaşanmış şehadet; anma/yıl dönümü False
    resmi_kurum_duyurusu: bool
    isimsiz_sayisi: int = Field(ge=0)  # isim verilmeyen şehit sayısı
    kisiler: list[Kisi]
    olay_ozeti: str  # tek cümle


class AnalizHatasi(Exception):
    pass


class AnalizYapilandirilmamis(AnalizHatasi):
    """Kimlik bilgisi yok ya da geçersiz."""


class Analizci(Protocol):
    def analiz_et(self, *, baslik: str, govde: str, yayin: datetime) -> HaberAnalizi: ...


class ClaudeAnalizci:
    def __init__(self, *, model: str, istemci: anthropic.Anthropic | None = None, api_anahtari: str = ""):
        self.model = model
        if istemci is None:
            istemci = anthropic.Anthropic(api_key=api_anahtari) if api_anahtari else anthropic.Anthropic()
        self.istemci = istemci

    def analiz_et(self, *, baslik: str, govde: str, yayin: datetime) -> HaberAnalizi:
        yerel = yayin.astimezone(TZ)
        icerik = f"Yayın tarihi: {yerel:%Y-%m-%d %H:%M} (Europe/Istanbul)\nBaşlık: {baslik}\n\n{govde}"
        try:
            yanit = self.istemci.messages.parse(
                model=self.model,
                max_tokens=4096,
                system=SISTEM_ISTEMI,
                messages=[{"role": "user", "content": icerik}],
                output_format=HaberAnalizi,
            )
        except anthropic.AuthenticationError as e:
            raise AnalizYapilandirilmamis("Claude kimlik doğrulaması başarısız") from e
        except anthropic.APIError as e:
            raise AnalizHatasi(f"Claude isteği başarısız: {type(e).__name__}") from e
        except ValueError as e:  # parse() çıktıyı kendisi doğrular (ValidationError)
            raise AnalizHatasi("Claude çıktısı çözümlenemedi") from e
        if yanit.stop_reason == "refusal":
            raise AnalizHatasi("Claude isteği reddetti")
        if yanit.parsed_output is None:
            raise AnalizHatasi("Claude geçerli bir çıktı üretmedi")
        return yanit.parsed_output


def analizci_olustur(settings) -> Analizci | None:
    anahtar = settings.anthropic_api_key
    if not (anahtar or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return None
    return ClaudeAnalizci(model=settings.analiz_modeli, api_anahtari=anahtar)
