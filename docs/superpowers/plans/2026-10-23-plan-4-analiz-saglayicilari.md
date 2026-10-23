# vatansagolsun — Plan 4: Sırayla Yedeklenen Analiz Sağlayıcıları Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Haber analizini tek sağlayıcı (Claude) yerine sıralı bir zincirle yapmak: **OpenAI → Gemini → Claude**. Bir sağlayıcı kredi/kota bittiğini bildirirse 24 saat "tükendi" sayılır ve sıradakine geçilir; geçici hatada aynı haber sıradakiyle denenir. Kullanıcı isteği (2026-10-23): OpenAI'daki 5 $ API kredisi bitene kadar OpenAI, sonra ücretsiz Gemini, en son Claude.

**Architecture:** `app/analiz.py` ortak modelleri, istemi ve hata türlerini tutar; sağlayıcıya özgü kod `app/analiz_saglayicilari.py`'ye (OpenAI, Gemini, Claude) ayrılır. `ZincirAnalizci` sağlayıcıları sırayla dener, "tükendi" bilgisini `KaynakDurumu("analiz_<ad>")` satırında saklar (süreçler ve yeniden başlatmalar arasında kalıcı). `analizci_olustur(settings)` yalnızca anahtarı olan sağlayıcılardan zincir kurar; hiçbiri yoksa `None` (mevcut "API anahtarı yok" yolu aynen çalışır).

**Tech Stack:** mevcut yığın + `openai` (Python SDK, Responses API yapılandırılmış çıktı) + `google-genai` (Gemini SDK, `response_schema` ile JSON). Sürümler kurulu paketlere göre sabitlenir (`>=X,<X+1`).

**Spec:** `docs/superpowers/specs/2026-10-23-vatansagolsun-design.md` 4.1 (analiz modeli) — bu plan 4.1'i günceller (Task 3'te belgeye işlenir).

## Global Constraints

- Varsayılan sıra `Settings.analiz_sirasi: list[str] = ["openai", "gemini", "claude"]` (`.env`: `ANALIZ_SIRASI=["openai","gemini","claude"]`).
- Anahtarlar: `OPENAI_API_KEY`, `GEMINI_API_KEY` (yoksa `GOOGLE_API_KEY` da kabul), `ANTHROPIC_API_KEY` (mevcut; `ANTHROPIC_AUTH_TOKEN` da sayılır). Ayarlar alanları: `openai_api_key`, `gemini_api_key`, `anthropic_api_key` (boşsa ortam değişkenine bakılır). Anahtarı olmayan sağlayıcı zincire hiç girmez.
- Modeller ayarlanabilir: `openai_modeli`, `gemini_modeli`, `analiz_modeli` (Claude, mevcut `claude-haiku-5-5`). OpenAI ve Gemini varsayılanları: o sağlayıcının **güncel en ucuz, yapılandırılmış JSON çıktısını destekleyen** modeli — uygulayıcı resmî belgeden doğrular ve gerekçesini rapora yazar (tahmin etme).
- Hepsi aynı `SISTEM_ISTEMI`'ni ve aynı kullanıcı içeriğini (`<haber>` sınırlayıcılı, İstanbul saatli yayın tarihi) kullanır; hepsi aynı `HaberAnalizi` Pydantic şemasına doğrulanır.
- İstek zaman aşımı her sağlayıcıda 60 sn. Sağlayıcı SDK'larının kendi yeniden denemesi en fazla 2.
- **Tükendi** sayılan hatalar (24 saat atlanır): kimlik geçersiz/yetkisiz (401/403), kredi/fatura/kota bitti (OpenAI `insufficient_quota`, HTTP 402; Gemini `RESOURCE_EXHAUSTED` kota/günlük sınır; Anthropic kredi bakiyesi yetersiz 400 `credit balance`). Uygulayıcı her SDK'nın gerçek hata sınıflarını/kodlarını kurulu paketten doğrular.
- **Geçici** hatalar (aynı haber sıradaki sağlayıcıyla denenir, sağlayıcı işaretlenmez): ağ, zaman aşımı, 429 hız sınırı (kota değil), 5xx, ret (`refusal`), şemaya uymayan çıktı.
- Zincirdeki tüm sağlayıcılar başarısız olursa: hepsi "tükendi" ise `AnalizYapilandirilmamis("Tüm analiz sağlayıcıları tükendi")`, aksi halde `AnalizHatasi` (Plan 3'ün imleç/takılı koruması aynen devreye girer).
- Günlük analiz sayacı (Plan 3) haber başına bir kez artar (zincir içindeki denemeler ayrıca sayılmaz).
- Anahtarlar asla loglanmaz, panelde gösterilmez.
- Testlerde ağ ve gerçek API yok; sağlayıcılar sahte istemcilerle test edilir.
- Commit mesajları şu satırla biter: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. OpenAI kredisi bitince (insufficient_quota) aynı haber Gemini'ye gider, OpenAI 24 saat denenmez; 24 saat sonra tekrar denenir. → Task 2 testleri.
2. Geçici hata (429/5xx/ağ/ret/bozuk çıktı) sağlayıcıyı tükendi saymaz ama haberi sıradakine verir. → Task 2 testleri.
3. Hiç anahtar yoksa mevcut "API anahtarı yok" davranışı ve ağ isteği olmaması korunur. → Task 2 testi.
4. Üç sağlayıcının çıktısı aynı `HaberAnalizi` doğrulamasından geçer; şemaya uymayan çıktı `AnalizHatasi` olur, çökmez. → Task 1 testleri.

---

### Task 1: Sağlayıcılar (OpenAI, Gemini, Claude) ve ortak hata sınıflandırması

**Files:**
- Create: `app/analiz_saglayicilari.py`, `tests/test_analiz_saglayicilari.py`
- Modify: `app/analiz.py` (ortak `kullanici_icerigi(baslik, govde, yayin) -> str`; `ClaudeAnalizci` sağlayıcı dosyasına taşınabilir — `app.analiz.ClaudeAnalizci` adı geriye uyum için içe aktarılabilir kalır), `app/config.py`, `pyproject.toml`, `.env.example`

**Interfaces:**
- `class SaglayiciTukendi(AnalizHatasi)` — kalıcı (24 saat) hata; `class SaglayiciGecici(AnalizHatasi)` — geçici.
- Her sağlayıcı sınıfı `ad: str` (`"openai"`, `"gemini"`, `"claude"`) ve `analiz_et(*, baslik, govde, yayin) -> HaberAnalizi`; SDK hatalarını yukarıdaki iki sınıfa eşler (refusal / doğrulama hatası / boş çıktı → `SaglayiciGecici`).
  - `OpenAIAnalizci(model, istemci=None, api_anahtari="")` — OpenAI Python SDK Responses API yapılandırılmış çıktı (`client.responses.parse(model=..., instructions=SISTEM_ISTEMI, input=icerik, text_format=HaberAnalizi)` → `output_parsed`; kurulu SDK'dan doğrula).
  - `GeminiAnalizci(model, istemci=None, api_anahtari="")` — `google-genai` (`genai.Client(api_key=...)`, `client.models.generate_content(model=..., contents=icerik, config=types.GenerateContentConfig(system_instruction=SISTEM_ISTEMI, response_mime_type="application/json", response_schema=HaberAnalizi))` → `response.parsed`; kurulu SDK'dan doğrula).
  - `ClaudeAnalizci` — mevcut davranış; `AuthenticationError`/`PermissionDeniedError`/kredi bakiyesi hatası → `SaglayiciTukendi`, diğerleri → `SaglayiciGecici`.
- `Settings`: `analiz_sirasi`, `openai_api_key=""`, `openai_modeli`, `gemini_api_key=""`, `gemini_modeli` (+ mevcut `anthropic_api_key`, `analiz_modeli`).
- Testler (sahte istemcilerle, her sağlayıcı için): başarılı çıktı `HaberAnalizi`'ye dönüşür ve istek doğru model/istem/şema ile yapılır; kota/kredi hatası → `SaglayiciTukendi`; 401 → `SaglayiciTukendi`; 429 hız/5xx/bağlantı → `SaglayiciGecici`; şemaya uymayan çıktı → `SaglayiciGecici`. SDK hata nesneleri gerçek kurucularıyla oluşturulur.

- [ ] Step 1: başarısız testler · Step 2: başarısız gör · Step 3: paketleri kur (`.venv/Scripts/pip install -e ".[dev]"`) ve yaz · Step 4: tüm testleri geçir · Step 5: commit `feat: OpenAI, Gemini ve Claude analiz sağlayıcıları`

### Task 2: Zincir, "tükendi" kaydı ve `analizci_olustur`

**Files:**
- Modify: `app/analiz.py` (veya `analiz_saglayicilari.py`), `tests/test_analiz_saglayicilari.py`, `tests/test_toplayici.py` (gerekirse)

**Interfaces:**
- `TUKENME_SURESI = timedelta(hours=24)`
- `class ZincirAnalizci`: `__init__(self, saglayicilar: list, *, session_factory, saat: Callable[[], datetime] = utc_now)`; `analiz_et(...)`: sıradaki her sağlayıcı için `KaynakDurumu(f"analiz_{ad}")` satırında `imlec` = tükenme zamanı (ISO) ve `saat() - tükenme < 24 saat` ise atlar; dener; başarı → `son_durum="basarili"`, `son_calisma` güncellenir, döner; `SaglayiciTukendi` → satıra tükenme zamanı + `son_mesaj` (hata türü adı, anahtar yok) yazılır, sıradakine geçilir; `SaglayiciGecici` → loglanır, sıradakine geçilir. Hepsi atlanmış/tükenmişse `AnalizYapilandirilmamis("Tüm analiz sağlayıcıları tükendi")`; en az biri geçici hata verdiyse `AnalizHatasi`. Oturumu kendi açar/kapatır (toplayıcının oturumuna dokunmaz).
- `kullanilan_saglayici` özniteliği: son başarılı sağlayıcının adı (toplayıcı bunu kaydın `Kaynak.metin`'ine eklemez; yalnızca log ve panel).
- `analizci_olustur(settings, session_factory=None) -> ZincirAnalizci | None`: `analiz_sirasi` sırasıyla, anahtarı olan sağlayıcıları kurar; hiç yoksa `None`. `session_factory` verilmezse ayarlardaki veritabanından kurulan oturum fabrikası (toplayıcının kullandığıyla aynı) — `toplayici_calistir` kendi `session_factory`'sini geçirir.
- `analiz_yapilandirildi_mi(settings) -> bool`: herhangi bir sağlayıcının anahtarı varsa True.
- Testler: OpenAI tükendi → Gemini sonucu döner, OpenAI satırı tükendi; ikinci çağrıda OpenAI hiç çağrılmaz; `saat` 25 saat ileri → OpenAI tekrar denenir; OpenAI geçici → Gemini döner, OpenAI satırı tükendi DEĞİL; hepsi tükendi → `AnalizYapilandirilmamis`; biri geçici diğerleri tükendi → `AnalizHatasi`; anahtar yok → `None` ve toplayıcıda "API anahtarı yok" + ağ isteği yok (mevcut test korunur); `analiz_*` satırları `aktarim-durumu`'nda kaynak gibi listelenmez (gizle).

- [ ] Step 1–5: başarısız testler, başarısız gör, yaz, tüm testleri geçir, commit `feat: analiz sağlayıcı zinciri ve otomatik geçiş`

### Task 3: Panel, belge ve tasarım güncellemesi

**Files:**
- Modify: `app/admin.py`, `app/templates/panel/toplayici.html`, `README.md`, `.env.example`, `docs/superpowers/specs/2026-10-23-vatansagolsun-design.md` (4.1 tablosu: "Haber analizi: OpenAI → Gemini → Claude sırasıyla otomatik geçiş (kullanıcı kararı 2026-10-23)")

**Interfaces:**
- Toplayıcı sayfasında "Analiz sağlayıcıları" tablosu: sıra, sağlayıcı adı, anahtar var/yok, durum (`kullanılabilir` / `tükendi — <yerel saat>'e kadar`), son başarılı kullanım zamanı. Anahtar değeri asla gösterilmez.
- README "Yapay zekâ analizi" bölümü yeniden yazılır: üç sağlayıcı, sıranın nasıl değiştirileceği, her birinin anahtarının nereden alınacağı (OpenAI: platform.openai.com → API keys — ChatGPT uygulama bakiyesinin API'de geçmediği notu; Gemini: aistudio.google.com → Get API key, ücretsiz katman, günlük sınırın AI Studio'da görüldüğü, ücretsiz katmanda gönderilen metinlerin Google tarafından kullanılabileceği — gönderilenler zaten herkese açık haberler; Claude: console.anthropic.com), otomatik geçişin nasıl çalıştığı ve maliyet notu.
- Testler: panel tabloyu gösterir, anahtar metni sayfada yok; tükendi satırı İstanbul saatiyle görünür.

- [ ] Step 1–5: başarısız testler, başarısız gör, yaz, tüm testleri geçir, commit `feat: panelde analiz sağlayıcıları ve belge`
