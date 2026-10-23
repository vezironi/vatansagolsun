# vatansagolsun — Plan 3: 30 Dakikalık Toplayıcı Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Her 30 dakikada bir resmî şehit sayfalarındaki (EGM, Sahil Güvenlik) yeni kayıtları ve haber sitelerinin RSS akışlarındaki yeni şehit haberlerini toplamak; haberleri Claude Haiku ile ayrıştırıp (isim, görev, tarih, isimsiz sayısı) yöneticinin onay paneline **onay bekleyen** taslak olarak düşürmek; panelde toplayıcının durumunu göstermek.

**Architecture:** `app/kaynaklar/haber.py` RSS ve makale sayfalarını `Getirici` üzerinden okur. `app/analiz.py` makale metnini Claude'a gönderip yapılandırılmış `HaberAnalizi` döndürür (test edilebilsin diye istemci dışarıdan verilir). `app/toplayici.py` kaynak başına imleçli (KaynakDurumu) tarama yapar: anahtar sözcük süzgeci → makale → analiz → `aktarim.kayit_aktar(..., yeni_durum=onay_bekliyor)`. Resmî sayfalar için Plan 2 okuyucularının ilk sayfaları kullanılır. Plan 2'nin APScheduler'ına 30 dakikalık iş eklenir; panelde `/panel/toplayici` sayfası durumu gösterir.

**Tech Stack:** Plan 1–2 yığını + `anthropic>=1,<2` (Python SDK; model `claude-haiku-5-5`, `client.messages.parse(..., output_format=PydanticModel)` → `.parsed_output`).

**Spec:** `docs/superpowers/specs/2026-10-23-vatansagolsun-design.md` (4.4, 4.5)

**Haber kaynakları araştırması:** `docs/superpowers/plans/kaynaklar/haber/BULGULAR.md` ve `.../haber/veri/` (Task 2'de kopyalanır).

**Kapsam dışı:** X (Twitter) hesapları (ücretli API — spec "sonra"); MSB sitesi (JS/çerez doğrulaması otomatik erişimi engelliyor); Telegram/Discord bildirimleri.

## Global Constraints

- Ağa yalnızca Plan 2 `Getirici` üzerinden çıkılır (2 sn/sunucu, robots, izin listesi).
- Kaynak kodları: resmî `egm`, `sg`; haber `hurriyet`, `sabah`, `aa`, `trt`. `Settings.kaynak_izinleri` varsayılanı Plan 2 listesine `"hurriyet", "sabah"` eklenerek genişler (kullanıcının seçtiği haber siteleri). `aa`, `trt` destekli ama **varsayılan kapalı**.
- Toplayıcının oluşturduğu **her yeni kayıt `onay_bekliyor`** girer; mevcut kayıtların durumu değişmez (Plan 2 kuralı). Toplayıcı hiçbir kaydı yayına almaz.
- Haber kaynaklı kayıtlar: `kaynak_kodu="haber"` (öncelik 0 — yalnızca boş alan doldurur), `resmi_teyit` = analizdeki `resmi_kurum_duyurusu`; isimsiz haberler `isimsiz=True` taslak.
- İlk çalışma (imleç yok): yalnızca **bugünün** (Europe/Istanbul) haberleri. Sonraki çalışmalar: imleçten (son işlenen yayın zamanı) sonrası, ama en fazla **3 gün** geriye (kesinti telafisi — spec 4.4).
- Bir haber işlenemezse (makale indirilemedi, analiz hatası) imleç o haberin **öncesinde** kalır; sonraki çalışma tekrar dener.
- Analiz modeli `Settings.analiz_modeli = "claude-haiku-5-5"`; günlük analiz sınırı `Settings.gunluk_analiz_siniri = 200`. API anahtarı yoksa (`ANTHROPIC_API_KEY` boş ve SDK kimlik bulamıyor) haber analizi yapılmaz, imleç ilerlemez, durum "API anahtarı yok" olur; resmî kaynak taraması yine çalışır.
- Resmî kaynak (egm/sg) taraması yalnızca o kaynağın toplu aktarımı tamamlanmışsa (`KaynakDurumu(kod).tamamlandi`) yapılır; aksi halde "önce `aktar <kod>` çalıştırın" durumu yazılır (yüzlerce eski kaydın onaya düşmesini önler).
- Toplayıcı işi 30 dakikada bir, `max_instances=1`, `coalesce=True`; yalnızca `zamanlayici_aktif` iken. Testlerde ağ ve gerçek API yok (sahte getirici + sahte analizci).
- Commit mesajları şu satırla biter: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. Aynı şehit iki farklı haberde/kaynakta geçerse tek onay bekleyen kayıt oluşur, kaynakları birikir; aynı haber iki RSS akışında (Sabah son dakika + gündem) geçerse bir kez analiz edilir. → Task 4 testleri.
2. Kesinti sonrası 3 güne kadar telafi; ilk çalışmada yalnızca bugün; işlenemeyen haber imleci ilerletmez. → Task 4 testleri.
3. Analiz hatası/ret (`stop_reason == "refusal"`)/eksik API anahtarı/günlük sınır aşımı çökertmez, kayıt üretmez, haber sonra tekrar denenir. → Task 3, Task 4 testleri.
4. Toplayıcı hiçbir kaydı yayına almaz; yayındaki bir kayda yalnızca kaynak ekler; reddedilmiş kayıt dirilmez. → Task 4, Task 5 testleri.
5. Resmî sayfa taraması, toplu aktarım yapılmamışken yüzlerce kaydı onaya düşürmez. → Task 5 testi.

---

## Dosya yapısı

```
app/kaynaklar/__init__.py   + HamKayit.resmi_teyit, HamKayit.isimsiz
app/kaynaklar/haber.py      HaberOgesi, rss_ayristir, sehit_gecer_mi, makale_ayristir, HABER_KAYNAKLARI
app/analiz.py               HaberAnalizi/Kisi modelleri, Analizci protokolü, ClaudeAnalizci, analiz_istemi
app/toplayici.py            haber_kaynagi_tara, resmi_kaynak_tara, toplayici_calistir
app/aktarim.py              ham_to_veri bayrakları, isimsiz kayıt eşleştirilmez
app/zamanlayici.py          + 30 dakikalık toplayıcı işi
app/admin.py, templates/panel/toplayici.html, _sekmeler.html   panel durum sayfası
app/cli.py                  + topla
tests/fixtures/haber/       RSS + makale örnekleri (kısaltılmış, gerçek)
tests/test_haber.py, test_analiz.py, test_toplayici.py
```

---

### Task 1: Ham kayıt bayrakları ve ayarlar

**Files:**
- Modify: `app/kaynaklar/__init__.py`, `app/aktarim.py`, `app/config.py`, `.env.example`, `tests/test_aktarim.py`

**Interfaces:**
- Produces:
  - `HamKayit.resmi_teyit: bool = True`, `HamKayit.isimsiz: bool = False` (alanların sonuna; mevcut çağrılar etkilenmez)
  - `aktarim.ham_to_veri` bu iki alanı `SehitVeri`'ye taşır (şu an sabit `resmi_teyit=True`, `isimsiz=False`).
  - `aktarim.kayit_aktar`: `ham.isimsiz` ise `eslesen_bul` çağrılmaz, her zaman yeni kayıt (dis_kimlik tekilliği yine geçerli: aynı isimsiz haber tekrar gelirse `atlandi`).
  - `Settings.kaynak_izinleri` varsayılanı: `["egm", "sg", "kahramanlar", "sehitlerimiz", "hurriyet", "sabah"]`
  - `Settings.analiz_modeli: str = "claude-haiku-5-5"`, `Settings.gunluk_analiz_siniri: int = 200`, `Settings.anthropic_api_key: str = ""` (boşsa SDK kendi kimlik çözümüne bırakılır)
  - `.env.example`: `ANTHROPIC_API_KEY=`, `GUNLUK_ANALIZ_SINIRI=200`, `KAYNAK_IZINLERI` satırına haber kaynakları ve "aa, trt isterseniz ekleyin" notu.

- [ ] **Step 1: Başarısız testler** — `tests/test_aktarim.py`:

```python
def test_resmi_teyitsiz_ve_isimsiz_bayraklari(session):
    from app.models import Sehit
    r = aktarim.kayit_aktar(session, ham(kaynak_kodu="haber", dk="hurriyet:1#0", resmi_teyit=False))
    s = session.get(Sehit, r.sehit_id)
    assert s.resmi_teyit is False and s.isimsiz is False

def test_isimsiz_kayit_eslestirilmez(session):
    a = aktarim.kayit_aktar(session, ham(ad="İsimsiz", soyad=None, kaynak_kodu="haber", dk="h:1#isimsiz", isimsiz=True, tarih=None, hassasiyet=H.bilinmiyor, yil=None))
    b = aktarim.kayit_aktar(session, ham(ad="İsimsiz", soyad=None, kaynak_kodu="haber", dk="h:2#isimsiz", isimsiz=True, tarih=None, hassasiyet=H.bilinmiyor, yil=None))
    assert (a.durum, b.durum) == ("yeni", "yeni") and a.sehit_id != b.sehit_id
    assert aktarim.kayit_aktar(session, ham(ad="İsimsiz", soyad=None, kaynak_kodu="haber", dk="h:1#isimsiz", isimsiz=True)).durum == "atlandi"
```

- [ ] **Step 2–5:** başarısız gör (`.venv/Scripts/python -m pytest tests/test_aktarim.py -v`), uygula, tüm testleri geçir, commit: `git commit -m "feat: ham kayıtta resmi teyit/isimsiz bayrakları, toplayıcı ayarları"`

---

### Task 2: RSS ve makale ayrıştırma

**Files:**
- Create: `app/kaynaklar/haber.py`, `tests/test_haber.py`, `tests/fixtures/haber/` (gerçek örneklerden kısaltılmış), `docs/superpowers/plans/kaynaklar/haber/BULGULAR.md` + `veri/`

**Interfaces:**
- Produces (`app/kaynaklar/haber.py`):
  - `@dataclass HaberOgesi(kaynak_kodu: str, kimlik: str, url: str, baslik: str, ozet: str, yayin: datetime)` — `yayin` saat dilimli (aware).
  - `@dataclass HaberKaynagi(kod: str, ad: str, rss: list[str], govde_secici: str)`
  - `HABER_KAYNAKLARI: dict[str, HaberKaynagi]`:
    - `hurriyet`: ad "Hürriyet", rss `["https://www.hurriyet.com.tr/rss/gundem"]`, gövde `.news-content`
    - `sabah`: ad "Sabah", rss `["https://www.sabah.com.tr/rss/sondakika.xml", "https://www.sabah.com.tr/rss/gundem.xml"]`, gövde `div.newsBox`
    - `aa`: ad "Anadolu Ajansı", rss `["https://www.aa.com.tr/tr/rss/default?cat=guncel"]`, gövde araştırma notlarına göre
    - `trt`: ad "TRT Haber", rss `["https://www.trthaber.com/sondakika.rss"]`, gövde araştırma notlarına göre
  - `rss_ayristir(xml: str, kaynak: HaberKaynagi) -> list[HaberOgesi]` — `xml.etree.ElementTree` (DTD/varlık genişletmesi yok; gerekirse `defusedxml` yerine güvenli ayrıştırma notu). `pubDate` RFC 822 (`email.utils.parsedate_to_datetime`; Hürriyet'in `Z` soneki UTC'dir). `kimlik`: URL'nin sonundaki sayı (`-(\d{6,})(?:\.html)?/?$`), yoksa `guid`, yoksa URL. Açıklamadaki HTML etiketleri metne çevrilir (`metin_temizle`). Bozuk öğe atlanır (log).
  - `sehit_gecer_mi(*metinler: str) -> bool` — `katla` edilmiş metinde `\bsehi(t|d)` veya `sehadet` geçiyorsa True ("şehir" gibi yanlış pozitifleri ele: "sehir" eşleşmemeli).
  - `@dataclass Makale(baslik: str, govde: str, yayin: datetime | None)`; `makale_ayristir(html: str, kaynak: HaberKaynagi) -> Makale` — önce JSON-LD `NewsArticle` (`headline`, `datePublished`; `articleBody` yalnızca Sabah'ta güvenilir), gövde `govde_secici` altındaki `h2`/`p` metinleri; gövde en fazla 20.000 karakter. Gövde boşsa `KaynakHatasi`.
  - `ogeleri_getir(g: Getirici, kaynak: HaberKaynagi) -> list[HaberOgesi]` — tüm RSS'leri okur, `kimlik`e göre tekilleştirir (aynı haber iki akışta), yayın zamanına göre **yeniden eskiye** sıralar.

- [ ] **Step 1: Araştırma dosyalarını kopyala** — `C:/Users/vezir/AppData/Local/Temp/claude/C--Users-vezir-OneDrive-Desktop-Desktops-Apps-vatansagolsun/efa658f2-137c-4a92-9b9b-c2756000b968/scratchpad/haber-arastirma/BULGULAR.md` ve `veri/` (yalnızca `h_gundem.xml`, `h_art.html`, `h_art2.html`, `s_son.xml`, `s_gundem.xml`, `s_art.html`, `aa_rss.xml`, `trt_rss.xml`) → `docs/superpowers/plans/kaynaklar/haber/`. Test fixture'larını bunlardan kısaltarak `tests/fixtures/haber/` altına koy (RSS: 3–5 öğe, en az biri "şehit" içeren gerçek öğe varsa o; yoksa gerçek bir öğenin başlığını değiştirmeden ayrı bir sentetik öğe ekleyip testte sentetik olduğunu belirt).

- [ ] **Step 2: Başarısız testler** — `tests/test_haber.py`: her kaynak için `rss_ayristir` öğe sayısı, ilk öğenin `yayin`ının aware ve doğru (Hürriyet `Z` → UTC; Sabah `+0300`), `kimlik` URL'deki sayı; `sehit_gecer_mi("Pençe-Kilit bölgesinde 2 askerimiz şehit oldu")` True, `("Şehidimizi uğurladık")` True, `("Şehadet haberi")` True, `("İstanbul şehir hatları")` False; `makale_ayristir` Hürriyet ve Sabah örneklerinde `yayin` = JSON-LD `datePublished`, gövde boş değil ve başlık içermiyor; `ogeleri_getir` iki akışta aynı haberi bir kez döndürür ve sıralar (sahte getirici ile).

- [ ] **Step 3–5:** başarısız gör, yaz, tüm testleri geçir, commit: `git commit -m "feat: haber RSS ve makale ayrıştırma"`

---

### Task 3: Claude ile haber analizi

**Files:**
- Create: `app/analiz.py`, `tests/test_analiz.py`
- Modify: `pyproject.toml` (`anthropic>=1,<2` — kurulu sürüme göre doğrula)

**Interfaces:**
- Produces (`app/analiz.py`):
  - Pydantic modeller:
    - `class Kisi(BaseModel)`: `ad: str`, `soyad: str | None`, `gorev: str | None`, `kategori: Literal["asker","jandarma","polis","ogretmen","diger"]`, `memleket: str | None`, `kurum: str | None`, `sehadet_tarihi: str | None` (YYYY-AA-GG)
    - `class HaberAnalizi(BaseModel)`: `sehit_haberi: bool`, `yeni_olay: bool` (son 7 gün içinde yaşanmış bir şehadet mi; anma/yıl dönümü haberleri False), `resmi_kurum_duyurusu: bool`, `isimsiz_sayisi: int` (isim verilmeyen şehit sayısı, ≥0), `kisiler: list[Kisi]`, `olay_ozeti: str` (tek cümle)
  - `class AnalizHatasi(Exception)`; `class AnalizYapilandirilmamis(AnalizHatasi)` (kimlik bilgisi yok).
  - `class Analizci(Protocol)`: `def analiz_et(self, *, baslik: str, govde: str, yayin: datetime) -> HaberAnalizi`
  - `class ClaudeAnalizci`: `__init__(self, *, model: str, istemci: anthropic.Anthropic | None = None)`; istemci yoksa `anthropic.Anthropic()` (API anahtarı ayarlardan doluysa `api_key=` ile). `analiz_et`: `istemci.messages.parse(model=..., max_tokens=4096, system=SISTEM_ISTEMI, messages=[{"role": "user", "content": <yayin tarihi + başlık + gövde>}], output_format=HaberAnalizi)`; `stop_reason == "refusal"` veya `parsed_output is None` → `AnalizHatasi`; `anthropic.AuthenticationError` → `AnalizYapilandirilmamis`; diğer `anthropic.APIError` → `AnalizHatasi` (SDK zaten 429/5xx'i 2 kez yeniden dener).
  - `SISTEM_ISTEMI` (Türkçe, sabit — önbellek dostu): görev tanımı (Türk şehitleri: asker, jandarma, polis, öğretmen, korucu, resmî olarak şehit sayılan siviller); yabancı askerler, kaza/hastalık haberleri ancak haber "şehit" diyorsa; **yalnızca metinde açıkça geçen bilgileri çıkar, uydurma**; isimler Türkçe yazımıyla; tarih metinde yoksa yayın tarihinden "bugün/dün" ifadelerine göre çıkar, çıkaramıyorsan null; isimsiz şehit sayısı ("2 askerimiz") `isimsiz_sayisi`'na, isimler verilmişse o kişiler `kisiler`e (aynı kişiyi iki kez sayma); anma/cenaze/yıl dönümü haberinde ölüm 7 günden eskiyse `yeni_olay=false`; MSB/EGM/Jandarma/valilik açıklaması aktarılıyorsa `resmi_kurum_duyurusu=true`.
  - `analizci_olustur(settings) -> Analizci | None` — `settings.anthropic_api_key`, ortamdaki `ANTHROPIC_API_KEY` ve `ANTHROPIC_AUTH_TOKEN`'ın hepsi boşsa `None`; aksi halde `ClaudeAnalizci(model=settings.analiz_modeli)`. (Geçersiz anahtar ilk çağrıda `AnalizYapilandirilmamis` olur.)

- [ ] **Step 1: Başarısız testler** — `tests/test_analiz.py` (gerçek API yok; sahte istemci `messages.parse` döndürür):

```python
from datetime import datetime, timezone
import pytest
from types import SimpleNamespace
from app.analiz import ClaudeAnalizci, HaberAnalizi, AnalizHatasi, SISTEM_ISTEMI

def sahte_istemci(cevap=None, stop="end_turn", hata=None):
    class M:
        def parse(self, **kw):
            M.kw = kw
            if hata: raise hata
            return SimpleNamespace(parsed_output=cevap, stop_reason=stop)
    return SimpleNamespace(messages=M())

def test_basarili_analiz_ve_istek_bicimi():
    c = HaberAnalizi(sehit_haberi=True, yeni_olay=True, resmi_kurum_duyurusu=True, isimsiz_sayisi=0,
                     kisiler=[{"ad": "Ali", "soyad": "KAYA", "gorev": "Piyade Uzman Çavuş", "kategori": "asker",
                               "memleket": "Sivas", "kurum": "TSK", "sehadet_tarihi": "2026-10-22"}], olay_ozeti="x")
    ist = sahte_istemci(c)
    a = ClaudeAnalizci(model="claude-haiku-5-5", istemci=ist).analiz_et(baslik="B", govde="G", yayin=datetime(2026, 10, 23, tzinfo=timezone.utc))
    assert a.kisiler[0].soyad == "KAYA"
    kw = type(ist.messages).kw
    assert kw["model"] == "claude-haiku-5-5" and kw["output_format"] is HaberAnalizi and kw["system"] == SISTEM_ISTEMI
    assert "2026-10-23" in kw["messages"][0]["content"] and "G" in kw["messages"][0]["content"]

def test_ret_ve_bos_cikti_hata():
    with pytest.raises(AnalizHatasi):
        ClaudeAnalizci(model="m", istemci=sahte_istemci(None, stop="refusal")).analiz_et(baslik="", govde="x", yayin=datetime.now(timezone.utc))
```

  Ayrıca: `anthropic.AuthenticationError` → `AnalizYapilandirilmamis`; `anthropic.APIConnectionError` → `AnalizHatasi` (SDK hata sınıflarını gerçek kurucularıyla oluştur; gerekirse `httpx2.Request`/`Response` ile).

- [ ] **Step 2–5:** başarısız gör, `anthropic` ekle (`.venv/Scripts/pip install -e ".[dev]"`), yaz, tüm testleri geçir, commit: `git commit -m "feat: Claude Haiku ile yapılandırılmış haber analizi"`

---

### Task 4: Haber kaynağı taraması

**Files:**
- Create: `app/toplayici.py`, `tests/test_toplayici.py`

**Interfaces:**
- Consumes: Task 1–3; `aktarim.kayit_aktar`, `aktarim.kaynak_durumu`; `ayristir.tarih_coz`, `ayristir.isim_ayir` (görevden ayıklama gerekmez — analiz zaten ayırır; adı yine `ad_duzenle`/`soyad_duzenle` ile normalleştir); `dates.TZ`
- Produces (`app/toplayici.py`):
  - `TELAFI_GUN = 3`
  - `@dataclass HaberImleci(son_yayin: datetime | None)` — `KaynakDurumu(kod).imlec`'te ISO metin olarak saklanır.
  - `analiz_sayaci_artir(s, bugun: date, sinir: int) -> bool` — `KaynakDurumu("analiz_sayaci").imlec = "YYYY-AA-GG:N"`; gün değişince sıfırlanır; sınır aşıldıysa False (sayaç artmaz).
  - `haber_kaynagi_tara(s: Session, kod: str, g, analizci: Analizci | None, *, simdi: datetime) -> KaynakDurumu`:
    1. `kod` izinlerde değilse → `son_mesaj="izin yok"`, istek yok.
    2. `analizci is None` → `son_durum="hata"`, `son_mesaj="API anahtarı yok"`, imleç değişmez, istek yok.
    3. Pencere alt sınırı: imleç yoksa bugünün başı (İstanbul); varsa `max(imlec.son_yayin, simdi - 3 gün)`.
    4. `ogeleri_getir` → pencere içindeki ve `yayin > alt_sinir` öğeler, **eskiden yeniye** işlenir.
    5. Her öğe: `sehit_gecer_mi(baslik, ozet)` değilse → işlendi say (imleç ilerler). Geçiyorsa: günlük sınır aşıldıysa dur (imleç bu öğenin öncesinde kalır, `son_mesaj="günlük analiz sınırı"`); makaleyi getir+ayrıştır, analiz et. `sehit_haberi and yeni_olay` değilse işlendi say. Değilse taslakları üret:
       - her `Kisi` → `HamKayit(kaynak_kodu="haber", dis_kimlik=f"{kod}:{oge.kimlik}#{slug(ad soyad)}", ad, soyad, gorev, kategori, memleket, kurum, tarih/hassasiyet/yil = tarih_coz(sehadet_tarihi) (yoksa bilinmiyor), resmi_teyit=analiz.resmi_kurum_duyurusu, kaynak_adi=kaynak.ad, kaynak_url=oge.url, metin=f"{baslik}\n\n{govde[:4000]}")` → `kayit_aktar(..., yeni_durum=Durum.onay_bekliyor)`.
       - `isimsiz_sayisi > 0` → bir taslak: `ad="İsimsiz"`, `isimsiz=True`, `gorev` = `olay_ozeti`'nden değil, boş; `metin` başına `f"İsimsiz şehit sayısı: {n}. {olay_ozeti}"`; `dis_kimlik=f"{kod}:{oge.kimlik}#isimsiz"`; tarih = yayın gününün İstanbul tarihi, hassasiyet `tam` (panelde düzeltilebilir).
    6. Makale/analiz hatası (`KaynakHatasi`, `AnalizHatasi`) → o öğede dur; imleç son başarılı öğenin `yayin`ı; `son_durum="hata"`, `son_mesaj`. `AnalizYapilandirilmamis` → aynı, mesaj "API anahtarı geçersiz/yok".
    7. Sayaçlar Plan 2 `KaynakDurumu` alanlarına (eklenen/birlesen/atlanan/hatali) eklenir; `son_calisma=simdi`.

- [ ] **Step 1: Başarısız testler** — `tests/test_toplayici.py` (sahte getirici: `ogeleri_getir` ve makale çağrıları `monkeypatch` ile; sahte analizci kayıtlı cevaplar döndürür ve çağrı sayısını tutar):
  - `test_ilk_calisma_yalnizca_bugun`: dünkü ve bugünkü "şehit" öğeleri → yalnızca bugünkü analiz edilir; imleç = bugünkü öğenin yayını.
  - `test_imlecten_sonrasi_ve_uc_gun_telafi`: imleç 5 gün önce → yalnızca son 3 günün öğeleri işlenir.
  - `test_ayni_sehit_iki_haberde_tek_kayit`: iki öğe aynı "Ali KAYA, 22.10.2026" → 1 `onay_bekliyor` kayıt, 2 `Kaynak`.
  - `test_yayindaki_kayda_sadece_kaynak_eklenir` ve `test_reddedilen_dirilmez` (Plan 2 kuralı toplayıcıda da).
  - `test_isimsiz_taslak`: `isimsiz_sayisi=2`, `kisiler=[]` → 1 `isimsiz=True` taslak, metinde "2".
  - `test_anma_haberi_kayit_uretmez`: `yeni_olay=False` → kayıt yok, imleç ilerler.
  - `test_analiz_hatasi_imleci_tutar`: 3 öğeden 2.sinde `AnalizHatasi` → 1. işlendi, imleç 1.nin yayını, `son_durum="hata"`; ikinci çalışmada 2. tekrar analiz edilir.
  - `test_anahtar_yok_istek_yok`: `analizci=None` → getiriciye çağrı yok, mesaj "API anahtarı yok".
  - `test_gunluk_sinir`: sınır 1 → ikinci şehit öğesinde durur, imleç ikinciden önce.
  - `test_sehit_gecmeyen_haber_analiz_edilmez`: analizci çağrı sayısı 0, imleç ilerler.
  - `test_toplayici_kayitlari_resmi_teyit_bayragi`: `resmi_kurum_duyurusu=False` → kayıt `resmi_teyit is False`.

- [ ] **Step 2–5:** başarısız gör, yaz, tüm testleri geçir, commit: `git commit -m "feat: haber kaynağı taraması — imleç, telafi, analiz, onaya düşen taslaklar"`

---

### Task 5: Resmî sayfa taraması, birleşik çalıştırma ve `topla` komutu

**Files:**
- Modify: `app/toplayici.py`, `app/cli.py`, `tests/test_toplayici.py`, `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `resmi_kaynak_tara(s: Session, kod: Literal["egm","sg"], g) -> KaynakDurumu` — izin yoksa "izin yok"; `KaynakDurumu(kod).tamamlandi` değilse istek atmadan `son_mesaj="önce 'aktar {kod}' çalıştırın"`. Aksi halde: egm için `egm.sayfalar(g, baslangic=None)`'dan yalnızca `sehitlerimiz:1` ve `sehitlerimiz:2` sayfaları, sg için tek sayfa; her kayıt `kayit_aktar(..., yeni_durum=onay_bekliyor)` (bilinenler `atlandi`). Toplu aktarım imlecine (`KaynakDurumu(kod).imlec`) dokunmaz — sayaçlar `KaynakDurumu(f"{kod}_toplayici")`'ya yazılır.
  - `toplayici_calistir(session_factory, *, g=None, analizci=None, simdi=None) -> list[KaynakDurumu]` — sıra: `egm`, `sg`, sonra `HABER_KAYNAKLARI` içinde izinli olanlar. Her kaynak kendi oturumunda; bir kaynağın istisnası loglanıp `KaynakDurumu`'na yazılır, diğerleri çalışır. `analizci` verilmezse `analizci_olustur(get_settings())`.
  - CLI: `python -m app.cli topla [--kaynak KOD]` — tek tur; her kaynak için tek satır özet (bu çalışmanın sayıları); çıkış kodu: hata varsa 1.
  - `aktarim-durumu` toplayıcı satırlarını da gösterir (mevcut davranış).

- [ ] **Step 1: Başarısız testler** — `resmi_kaynak_tara` toplu aktarım yokken istek atmaz; varken yeni kart `onay_bekliyor`, bilinen kart `atlandi`, toplu aktarım imleci değişmez; `toplayici_calistir` bir kaynak istisna fırlatınca diğerleri çalışır; `topla` CLI çıkış kodları (sahte bileşenlerle, test DB'si yalıtılmış — Plan 2 CLI testlerindeki yöntem).

- [ ] **Step 2–5:** başarısız gör, yaz, tüm testleri geçir, commit: `git commit -m "feat: resmî sayfa taraması ve topla komutu"`

---

### Task 6: 30 dakikalık iş, panel durum sayfası, belge ve canlı deneme

**Files:**
- Create: `app/templates/panel/toplayici.html`, `tests/test_admin.py` eklemeleri, `tests/test_zamanlayici.py` eklemeleri
- Modify: `app/zamanlayici.py`, `app/admin.py`, `app/templates/panel/_sekmeler.html`, `README.md`, `docker-compose.yml` (gerekirse), `.env.example`

**Interfaces:**
- Produces:
  - `zamanlayici_kur` mevcut 12 saatlik işe ek olarak `toplayici_isi` — `IntervalTrigger(minutes=30)`, `max_instances=1`, `coalesce=True`, ilk çalışma başlangıçtan 2 dk sonra, `id="toplayici"`. İş istisna fırlatmaz (loglar).
  - `GET /panel/toplayici` (Yonetici): kaynak başına satır — kaynak adı, son çalışma (İstanbul saati, `istanbul_saati` süzgeci), durum, mesaj, eklenen/birlesen/atlanan/hatali; ayrıca "bugünkü analiz sayısı / sınır", "Claude API: yapılandırıldı / anahtar yok" (anahtarın kendisi asla gösterilmez), zamanlayıcı açık mı, sonraki çalışma zamanı.
  - `POST /panel/toplayici/simdi` (Yonetici + CSRF): zamanlayıcı varsa `toplayici` işini hemen tetikler (`modify(next_run_time=şimdi)`), sayfaya 303 + "Toplayıcı başlatıldı" bildirimi; zamanlayıcı yoksa 409 ve açıklama ("ZAMANLAYICI_AKTIF=true gerekli; elle: `python -m app.cli topla`").
  - Sekmelere "Toplayıcı" bağlantısı; ana panelde (`/panel`) toplayıcının son hatası varsa üstte kısa uyarı.
  - README: "Yeni şehitleri otomatik toplama" bölümü — ne yaptığı (30 dk; resmî sayfalar + Hürriyet + Sabah; AA/TRT'yi açma), Claude API anahtarı nasıl alınır (console.anthropic.com → API Keys) ve `.env`'e `ANTHROPIC_API_KEY=...`, tahmini maliyet (günde birkaç düzine analiz; Haiku 5.5 ile aylık birkaç dolar altında), gelen kayıtların panelde onay beklediği, "Resmî teyit yok" ve "İsimsiz" rozetlerinin anlamı, toplu aktarım yapılmadan resmî sayfa taramasının beklediği, X hesaplarının neden yok olduğu.

- [ ] **Step 1: Başarısız testler** — panel sayfası girişsiz 303, girişli 200 ve satırları gösterir, anahtar metni sayfada yok; "şimdi çalıştır" zamanlayıcısız 409, sahte zamanlayıcıyla `modify` çağrılır; `zamanlayici_kur` (ayar açıkken) iki iş kaydeder (`id`ler `sehitlerimiz_kontrol`/mevcut ad ve `toplayici`), ayar kapalıyken `None`.

- [ ] **Step 2–4:** başarısız gör, yaz, tüm testleri geçir.

- [ ] **Step 5: Canlı deneme** — geçici `.canli_deneme.db` (asla `yerel.db` değil): `alembic upgrade head`, `aktar sg`, `aktar egm`, sonra `topla`. Claude kimliği için önce `ant auth status` (yoksa `ANTHROPIC_API_KEY` ortamda var mı) kontrol et; **kimlik yoksa** haber taraması "API anahtarı yok" durumuyla bitmeli — bunu doğrula ve ayrıca analizci olmadan anahtar sözcük süzgecinden geçen bugünkü haber başlıklarını (scratch betiği ile) listele. Kimlik varsa en fazla 5 analizlik bir deneme yap ve çıkan taslakları (ad, görev, tarih, resmi_teyit, isimsiz) rapora yaz. Sonra `.canli_deneme.db`'yi sil.

- [ ] **Step 6: Commit** — `git commit -m "feat: 30 dakikalık toplayıcı işi, panel durum sayfası ve belge"`
