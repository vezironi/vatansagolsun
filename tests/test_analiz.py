from datetime import datetime, timezone
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from pydantic import ValidationError

from app.analiz import (
    AnalizHatasi,
    AnalizYapilandirilmamis,
    ClaudeAnalizci,
    HaberAnalizi,
    SISTEM_ISTEMI,
    analizci_olustur,
)

YAYIN = datetime(2026, 10, 23, tzinfo=timezone.utc)


def sahte_istemci(cevap=None, stop="end_turn", hata=None):
    class M:
        def parse(self, **kw):
            M.kw = kw
            if hata:
                raise hata
            return SimpleNamespace(parsed_output=cevap, stop_reason=stop)

    return SimpleNamespace(messages=M())


def analizci(**kw):
    return ClaudeAnalizci(model="m", istemci=sahte_istemci(**kw))


def test_basarili_analiz_ve_istek_bicimi():
    c = HaberAnalizi(sehit_haberi=True, yeni_olay=True, resmi_kurum_duyurusu=True, isimsiz_sayisi=0,
                     kisiler=[{"ad": "Ali", "soyad": "KAYA", "gorev": "Piyade Uzman Çavuş", "kategori": "asker",
                               "memleket": "Sivas", "kurum": "TSK", "sehadet_tarihi": "2026-10-22"}], olay_ozeti="x")
    ist = sahte_istemci(c)
    a = ClaudeAnalizci(model="claude-haiku-5-5", istemci=ist).analiz_et(baslik="B", govde="G", yayin=YAYIN)
    assert a.kisiler[0].soyad == "KAYA"
    kw = type(ist.messages).kw
    assert kw["model"] == "claude-haiku-5-5" and kw["output_format"] is HaberAnalizi and kw["system"] == SISTEM_ISTEMI
    assert kw["max_tokens"] == 4096
    assert "temperature" not in kw and "thinking" not in kw
    assert "2026-10-23" in kw["messages"][0]["content"] and "G" in kw["messages"][0]["content"]


def test_ret_ve_bos_cikti_hata():
    with pytest.raises(AnalizHatasi):
        analizci(cevap=None, stop="refusal").analiz_et(baslik="", govde="x", yayin=datetime.now(timezone.utc))
    with pytest.raises(AnalizHatasi):
        analizci(cevap=None).analiz_et(baslik="", govde="x", yayin=YAYIN)


def _yanit(kod):
    istek = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx2.Response(kod, request=istek)


def test_kimlik_hatasi_yapilandirilmamis():
    hata = anthropic.AuthenticationError("bad key", response=_yanit(401), body=None)
    with pytest.raises(AnalizYapilandirilmamis):
        analizci(hata=hata).analiz_et(baslik="B", govde="G", yayin=YAYIN)


def test_diger_api_hatalari_analiz_hatasi():
    istek = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    for hata in (anthropic.APIConnectionError(request=istek),
                 anthropic.RateLimitError("limit", response=_yanit(429), body=None)):
        with pytest.raises(AnalizHatasi) as e:
            analizci(hata=hata).analiz_et(baslik="B", govde="G", yayin=YAYIN)
        assert not isinstance(e.value, AnalizYapilandirilmamis)


def test_model_kisitlari():
    with pytest.raises(ValidationError):
        HaberAnalizi(sehit_haberi=True, yeni_olay=True, resmi_kurum_duyurusu=False, isimsiz_sayisi=-1,
                     kisiler=[], olay_ozeti="x")
    with pytest.raises(ValidationError):
        HaberAnalizi(sehit_haberi=True, yeni_olay=True, resmi_kurum_duyurusu=False, isimsiz_sayisi=0,
                     kisiler=[{"ad": "A", "kategori": "uzayli"}], olay_ozeti="x")


def test_analizci_olustur(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    ayar = SimpleNamespace(anthropic_api_key="", analiz_modeli="claude-haiku-5-5")
    assert analizci_olustur(ayar) is None
    ayar.anthropic_api_key = "sk-test"
    a = analizci_olustur(ayar)
    assert isinstance(a, ClaudeAnalizci) and a.model == "claude-haiku-5-5"
    ayar.anthropic_api_key = ""
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok")
    assert isinstance(analizci_olustur(ayar), ClaudeAnalizci)


def test_sistem_istemi_sabit():
    assert "uydurma" in SISTEM_ISTEMI
    assert "2026" not in SISTEM_ISTEMI
