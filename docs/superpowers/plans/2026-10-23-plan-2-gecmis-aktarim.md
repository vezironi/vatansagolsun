# vatansagolsun — Plan 2: Geçmiş Veri Aktarımı Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resmî kaynaklardan (EGM, Sahil Güvenlik) ve iki arşivden (kahramanlar.org.tr, sehitlerimiz.org.tr) geçmiş şehit kayıtlarını nazikçe, kaldığı yerden devam edebilen ve tekrar çalıştırılınca çoğaltmayan bir aktarımla veritabanına almak; sehitlerimiz.org.tr'ye 12 saatte bir yeni kayıt kontrolü eklemek.

**Architecture:** Her kaynak için `app/kaynaklar/` altında bir okuyucu modülü, ham kayıtları (`HamKayit`) üretir; okuyucular yalnızca ortak `Getirici` (hız sınırlı, robots'a uyan, izin kontrollü HTTP istemcisi) üzerinden ağa çıkar. `app/aktarim.py` ham kaydı `SehitVeri`'ye çevirir, mevcut kayıtlarla eşleştirir, kaynak önceliğine göre birleştirir ve `Kaynak` satırı ekler. Her kaynağın ilerlemesi `KaynakDurumu` tablosunda tutulur (kaldığı yerden devam, 12 saatlik kontrol imleci). Zamanlayıcı (APScheduler) yalnızca ayarla açılır.

**Tech Stack:** Plan 1 yığını + `httpx` (çalışma bağımlılığı), `selectolax` (HTML ayrıştırma), `apscheduler>=3.10,<4`.

**Spec:** `docs/superpowers/specs/2026-10-23-vatansagolsun-design.md` (özellikle 4.2, 4.3, 4.4 madde 4)

**Kaynak araştırması (bu planın dayanağı):** `docs/superpowers/plans/kaynaklar/BULGULAR.md` ve örnek dosyalar `docs/superpowers/plans/kaynaklar/veri/` (Task 1'de buraya kopyalanır).

**Kapsam dışı (Plan 3):** 30 dakikalık toplayıcı, haber siteleri, Claude Haiku analizi, EGM/SG'de yeni kayıt takibi, panelde toplayıcı durum bölümü. MSB sitesi otomatik erişimi engellediği (JS/çerez doğrulaması) için bu planda yok.

## Global Constraints

- Ağa yalnızca `Getirici` üzerinden çıkılır. Aynı sunucuya iki istek arası en az `istek_araligi_sn` (varsayılan **2.0**) saniye. 429/5xx'te en fazla 3 deneme, artan bekleme (30, 60, 120 sn). robots.txt'nin yasakladığı yola istek atılmaz.
- Kullanıcı aracısı (UA): `Mozilla/5.0 (compatible; vatansagolsun-aktarim/1.0; +{site_url})`.
- Kaynak açma/kapama: `Settings.kaynak_izinleri: list[str]`, varsayılan `["egm", "sg", "kahramanlar", "sehitlerimiz"]` (kullanıcı kararı: kamuya açık bilgiler, izin beklenmez — spec 4.3). Bir site itiraz ederse `.env`'den çıkarılarak kapatılır. Listede olmayan kaynağa `Getirici` istek atmaz (`KaynakIzniYok` hatası).
- Kaynak öncelikleri: `ONCELIK = {"panel": 4, "egm": 3, "sg": 3, "sehitlerimiz": 2, "kahramanlar": 1, "haber": 0, "ornek": 0}`. Yüksek öncelikli kaynak ad/soyad/tarih/görevi ezer; düşük öncelikli yalnızca boş alanları doldurur. `Sehit.kaynak_kodu` = kayda katkı vermiş en yüksek öncelikli kaynak.
- Toplu aktarımla gelen kayıtlar `yayinda` girer (spec 4.3). sehitlerimiz 12 saatlik kontrolünden gelen yeni kayıtlar `onay_bekliyor` girer. Mevcut kaydın durumu aktarımda **değişmez** (reddedilmiş kayıt dirilmez, onay bekleyen yayına çıkmaz; yalnızca kaynak eklenir/boş alan dolar).
- İçe alınan kayıtlarda `resmi_teyit = True` (kaynakların hepsi resmî kayıtlardan derlenmiş).
- Tekrar çalıştırma çoğaltmaz: `Kaynak(kaynak_kodu, dis_kimlik)` tekildir; görülen kayıt atlanır.
- Testler ağa çıkmaz: tüm okuyucu testleri `tests/fixtures/kaynaklar/` altındaki örnek dosyalarla, sahte `Getirici` ile çalışır.
- Zamanlayıcı yalnızca `Settings.zamanlayici_aktif=True` iken başlar (varsayılan False; docker-compose'ta True). Testlerde asla başlamaz.
- Kaynak gösterimi: sehitlerimiz kayıtlarında `Kaynak.kaynak_adi = "sehitlerimiz.org.tr — Türkiye Şehit Arşivi"` ve kayıt URL'si.
- Commit mesajları şu satırla biter: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. Aynı aktarımı iki kez çalıştırmak kayıt sayısını değiştirmez; yarıda kesilen aktarım kaldığı sayfadan devam eder. → Task 4, Task 9 testleri.
2. Karışık tarih biçimleri ("22.07.2015", "23 Aralık 2015", "5 Ekim 2015", "2010-06-21", "20 Kasım 2019", boş, "-", saçma metin) doğru ayrışır; ayrışmayan değer `bilinmiyor` olur, hata fırlatmaz. → Task 1 testleri.
3. Unvanlı/rütbeli isimler doğru bölünür: "Şehit Polis Memuru Ahmet TÜRKOĞLU" → ad "Ahmet", soyad "TÜRKOĞLU", görev "Polis Memuru"; "ULŞ. UZM. ÇVŞ. ABDURRAHMAN HİLAL" → görev "Uzman Çavuş", ad "Abdurrahman", soyad "HİLAL"; Osmanlı dönemi tek isim "MUSTAFA" → soyad yok. → Task 1 testleri.
4. Tek bir bozuk kayıt ya da bir sayfadaki ağ hatası tüm aktarımı düşürmez: kayıt atlanır ve sayılır; sayfa hatasında imleç ilerlemez, komut anlamlı mesajla biter. → Task 4, Task 9 testleri.
5. Kapatılmış (listede olmayan) kaynağa hiçbir istek gitmez; zamanlayıcı testlerde ve `zamanlayici_aktif=False` iken başlamaz. → Task 2, Task 10 testleri.

---

## Dosya yapısı

```
app/kaynaklar/__init__.py   HamKayit dataclass, KaynakHatasi, KaynakIzniYok
app/kaynaklar/ayristir.py   tarih_coz, isim_ayir, kategori_bul, gorev_temizle
app/kaynaklar/getirici.py   Getirici (hız sınırı, robots, izin, yeniden deneme)
app/kaynaklar/egm.py        EGM listeleri
app/kaynaklar/sg.py         Sahil Güvenlik
app/kaynaklar/kahramanlar.py
app/kaynaklar/sehitlerimiz.py
app/aktarim.py              ham → kayıt: eşleştir, birleştir, kaydet; kaynak çalıştırıcıları
app/zamanlayici.py          APScheduler kurulumu, 12 saatlik iş
app/models.py               + isim_anahtari, Kaynak.kaynak_kodu/dis_kimlik, KaynakDurumu
migrations/versions/0002_aktarim.py
app/cli.py                  + aktar, sehitlerimiz-kontrol
tests/fixtures/kaynaklar/   örnek HTML/JSON (kısaltılmış)
tests/test_ayristir.py, test_getirici.py, test_aktarim.py, test_kaynak_egm.py,
tests/test_kaynak_sg.py, test_kaynak_kahramanlar.py, test_kaynak_sehitlerimiz.py, test_zamanlayici.py
```

---

### Task 1: Ayrıştırma yardımcıları ve ortak tipler

**Files:**
- Create: `app/kaynaklar/__init__.py`, `app/kaynaklar/ayristir.py`, `tests/test_ayristir.py`, `docs/superpowers/plans/kaynaklar/BULGULAR.md` (+ `veri/`)

**Interfaces:**
- Produces (`app/kaynaklar/__init__.py`):
  - `@dataclass HamKayit`: `kaynak_kodu: str`, `dis_kimlik: str`, `ad: str`, `soyad: str | None = None`, `lakap: str | None = None`, `tarih: date | None = None`, `hassasiyet: Hassasiyet = Hassasiyet.bilinmiyor`, `yil: int | None = None`, `gorev: str | None = None`, `kategori: Kategori = Kategori.asker`, `kurum: str | None = None`, `memleket: str | None = None`, `baba_adi: str | None = None`, `dogum_yili: int | None = None`, `donem: str | None = None`, `kaynak_adi: str = ""`, `kaynak_url: str | None = None`, `metin: str | None = None`
  - `class KaynakHatasi(Exception)`, `class KaynakIzniYok(KaynakHatasi)`
- Produces (`app/kaynaklar/ayristir.py`):
  - `tarih_coz(metin: str | None) -> tuple[date | None, Hassasiyet, int | None]` — `(tarih, hassasiyet, yil)`. Kabul: `GG.AA.YYYY`, `G.A.YYYY`, `YYYY-AA-GG`, `G <Türkçe ay> YYYY` (ay adları büyük/küçük ve şapkasız yazımlar dahil: Ocak…Aralık, "Subat", "Agustos", "Eylul", "Kasim", "Aralik"), yalnızca `YYYY` (1000–2100) → `yil`. Boş, `-`, geçersiz gün → `(None, bilinmiyor, None)`.
  - `isim_ayir(ham: str, *, soyadli: bool) -> tuple[str, str | None, str | None]` — `(ad, soyad, gorev)`. Baştaki "Şehit" sözcüğü ve bilinen unvan/rütbe önekleri atılıp `gorev` olarak döner (`RUTBE_ONEKLERI` sözlüğü: "Polis Memuru", "Kıdemli Başpolis Memuru", "Başpolis Memuru", "Komiser Yardımcısı", "Komiser", "Başkomiser", "Emniyet Amiri", "Emniyet Müdürü", "Bekçi", "Uzman Çavuş", "Uzman Onbaşı", "Astsubay", "Teğmen", "Üsteğmen", "Yüzbaşı", "Binbaşı", "Er", "Onbaşı", "Çavuş", "Sözleşmeli Er" ve kısaltmalar `UZM. ÇVŞ.`→"Uzman Çavuş", `ULŞ.` (atılır), `P.`→"Piyade", `J.`→"Jandarma", `KOM.`→"Komando", `ASTSB.`→"Astsubay", `ÜÇVŞ.`→"Üstçavuş", `ÜTĞM.`→"Üsteğmen", `TĞM.`→"Teğmen", `YZB.`→"Yüzbaşı"). `soyadli=True` ve ≥2 sözcük → son sözcük soyad; `soyadli=False` → hepsi ad, soyad `None`. Ad `ad_duzenle`, soyad `soyad_duzenle` ile döner (Plan 1 `app/text.py`).
  - `kategori_bul(*ipuclari: str | None) -> Kategori` — `katla` edilmiş ipuçlarında: "polis"/"emniyet"/"komiser"/"bekci" → `polis`; "jandarma" → `jandarma`; "ogretmen" → `ogretmen`; "korucu"/"sivil"/"memur" → `diger`; aksi `asker`.
  - `SOYADI_KANUNU_YILI = 1934`; `soyadli_mi(yil: int | None, donem: str | None) -> bool` — yıl ≥1934 ise True; yıl yoksa dönem metninde 1934 öncesi bir savaş adı ("BALKAN", "BİRİNCİ DÜNYA", "KURTULUŞ", "KIRIM", "OSMANLI", "TRABLUSGARP", "MİLLİ MÜCADELE", "MUHAREBE DIŞI DİĞER ŞEHİTLER (1853-1928)") geçiyorsa False; aksi True.

- [ ] **Step 1: Araştırma dosyalarını depoya al**

`C:/Users/vezir/AppData/Local/Temp/claude/C--Users-vezir-OneDrive-Desktop-Desktops-Apps-vatansagolsun/efa658f2-137c-4a92-9b9b-c2756000b968/scratchpad/kaynak-arastirma/BULGULAR.md` → `docs/superpowers/plans/kaynaklar/BULGULAR.md`; `veri/` içinden yalnızca şunları `docs/superpowers/plans/kaynaklar/veri/` altına kopyala: `egm_sehitlerimiz.html`, `egm_ajax_p2.html`, `egm_ajax_p90.html`, `egm_ozelharekat_sehitlerimiz.html`, `egm_istihbarat_istihbarat-sehitlerimiz.html`, `kh_p1.json`, `kh_polis.json`, `kh_msb26.json`, ve `sg`/`sehitlerimiz` ile başlayan tüm dosyalar (`msb.jar` alınmaz).

- [ ] **Step 2: Başarısız testleri yaz** — `tests/test_ayristir.py`

```python
from datetime import date
import pytest
from app.models import Hassasiyet as H, Kategori as K
from app.kaynaklar.ayristir import tarih_coz, isim_ayir, kategori_bul, soyadli_mi

@pytest.mark.parametrize("metin,beklenen", [
    ("22.07.2015", (date(2015, 7, 22), H.tam, 2015)),
    ("5.10.2015", (date(2015, 10, 5), H.tam, 2015)),
    ("2010-06-21", (date(2010, 6, 21), H.tam, 2010)),
    ("23 Aralık 2015", (date(2015, 12, 23), H.tam, 2015)),
    ("20 Kasım 2019", (date(2019, 11, 20), H.tam, 2019)),
    ("5 ekim 2015", (date(2015, 10, 5), H.tam, 2015)),
    ("17 Agustos 2016", (date(2016, 8, 17), H.tam, 2016)),
    ("1915", (None, H.yil, 1915)),
    ("", (None, H.bilinmiyor, None)),
    ("-", (None, H.bilinmiyor, None)),
    (None, (None, H.bilinmiyor, None)),
    ("31.02.2016", (None, H.bilinmiyor, None)),
    ("bilinmiyor", (None, H.bilinmiyor, None)),
])
def test_tarih_coz(metin, beklenen):
    assert tarih_coz(metin) == beklenen

def test_isim_ayir_unvanli():
    assert isim_ayir("Şehit Polis Memuru Ahmet TÜRKOĞLU", soyadli=True) == ("Ahmet", "TÜRKOĞLU", "Polis Memuru")
    assert isim_ayir("ULŞ. UZM. ÇVŞ. ABDURRAHMAN HİLAL", soyadli=True) == ("Abdurrahman", "HİLAL", "Uzman Çavuş")
    assert isim_ayir("Tayfun BAŞ", soyadli=True) == ("Tayfun", "BAŞ", None)
    assert isim_ayir("AHMET LÜTFİ", soyadli=False) == ("Ahmet Lütfi", None, None)
    assert isim_ayir("Ali Rıza Kaya", soyadli=True) == ("Ali Rıza", "KAYA", None)

def test_kategori_bul():
    assert kategori_bul("Polis", "POLİS ŞEHİDİ") == K.polis
    assert kategori_bul("Jandarma Uzman Çavuş") == K.jandarma
    assert kategori_bul(None, "Milli Eğitim Bakanlığı Öğretmen") == K.ogretmen
    assert kategori_bul("Sivil Şehit / Memur") == K.diger
    assert kategori_bul("Er / Erbaş", "BİRİNCİ DÜNYA SAVAŞI") == K.asker

def test_soyadli_mi():
    assert soyadli_mi(2015, None) is True
    assert soyadli_mi(1915, None) is False
    assert soyadli_mi(None, "BİRİNCİ DÜNYA SAVAŞI (1914-1918) ÇANAKKALE CEPHESİ") is False
    assert soyadli_mi(None, "TERÖRLE MÜCADELE") is True
```

- [ ] **Step 3: Testin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_ayristir.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.kaynaklar'`

- [ ] **Step 4: `app/kaynaklar/__init__.py` ve `app/kaynaklar/ayristir.py`'yi Interfaces'teki imzalarla yaz**

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `.venv/Scripts/python -m pytest -q`
Expected: tümü PASS

- [ ] **Step 6: Commit**

```bash
git add app/kaynaklar tests/test_ayristir.py docs/superpowers/plans/kaynaklar
git commit -m "feat: kaynak ayrıştırma yardımcıları (tarih, isim, kategori)"
```

---

### Task 2: Getirici (nazik HTTP istemcisi)

**Files:**
- Create: `app/kaynaklar/getirici.py`, `tests/test_getirici.py`
- Modify: `app/config.py` (`kaynak_izinleri`, `istek_araligi_sn`), `pyproject.toml` (`httpx>=0.28,<1` çalışma bağımlılığına; `selectolax>=0.3,<1`; `apscheduler>=3.10,<4`), `.env.example`

**Interfaces:**
- Consumes: `get_settings()`
- Produces:
  - `Settings.kaynak_izinleri: list[str] = ["egm", "sg", "kahramanlar", "sehitlerimiz"]`, `Settings.istek_araligi_sn: float = 2.0`
  - `class Getirici`:
    - `__init__(self, *, araligi_sn: float | None = None, transport: httpx.BaseTransport | None = None, uyku: Callable[[float], None] = time.sleep, saat: Callable[[], float] = time.monotonic, izinler: list[str] | None = None)` — `None` olanlar ayarlardan.
    - `metin(self, kaynak_kodu: str, url: str, *, params: dict | None = None) -> str` (GET)
    - `json(self, kaynak_kodu: str, url: str, *, params: dict | None = None) -> Any` (GET, JSON)
    - `post_json(self, kaynak_kodu: str, url: str, govde: dict, *, referer: str) -> str` (POST, `Content-Type: application/json`, `Referer`, yanıt metni)
    - Davranış: `kaynak_kodu` izinlerde yoksa `KaynakIzniYok` (istek atmadan). Her sunucu için ilk istekten önce `/robots.txt` bir kez okunur (`urllib.robotparser`, aynı UA); yasaklı yol → `KaynakHatasi("robots.txt ... yasaklıyor")`. robots.txt 4xx ise serbest kabul edilir. Aynı sunucuya ardışık iki istek arasında `saat()` farkı `araligi_sn`'den küçükse `uyku(fark)`. 429 ve 5xx: `uyku(30)`, `uyku(60)`, `uyku(120)` ile 3 yeniden deneme, sonra `KaynakHatasi`. Diğer 4xx → hemen `KaynakHatasi`. Zaman aşımı 30 sn. UA Global Constraints'teki metin.

- [ ] **Step 1: Başarısız testleri yaz** — `tests/test_getirici.py`

```python
import httpx, pytest
from app.kaynaklar import KaynakHatasi, KaynakIzniYok
from app.kaynaklar.getirici import Getirici

def _getirici(handler, **kw):
    uykular = []
    g = Getirici(transport=httpx.MockTransport(handler), uyku=uykular.append,
                 saat=kw.pop("saat", lambda: 0.0), izinler=kw.pop("izinler", ["egm"]), araligi_sn=2.0)
    return g, uykular

def test_izinsiz_kaynaga_istek_yok():
    cagrilar = []
    g, _ = _getirici(lambda r: cagrilar.append(r) or httpx.Response(200), izinler=["egm"])
    with pytest.raises(KaynakIzniYok):
        g.metin("sehitlerimiz", "https://sehitlerimiz.org.tr/arsiv")
    assert cagrilar == []

def test_robots_yasagi():
    def h(r):
        if r.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /ara\n")
        return httpx.Response(200, text="ok")
    g, _ = _getirici(h)
    with pytest.raises(KaynakHatasi):
        g.metin("egm", "https://x.test/ara?q=1")
    assert g.metin("egm", "https://x.test/sehitlerimiz") == "ok"

def test_hiz_siniri_bekler():
    zaman = iter([0.0, 0.5, 0.5])
    g, uykular = _getirici(lambda r: httpx.Response(404 if r.url.path == "/robots.txt" else 200, text="ok"),
                           saat=lambda: next(zaman, 10.0))
    g.metin("egm", "https://x.test/a"); g.metin("egm", "https://x.test/b")
    assert any(abs(u - 1.5) < 1e-6 for u in uykular)

def test_429_yeniden_dener_sonra_hata():
    g, uykular = _getirici(lambda r: httpx.Response(404 if r.url.path == "/robots.txt" else 429))
    with pytest.raises(KaynakHatasi):
        g.metin("egm", "https://x.test/a")
    assert [u for u in uykular if u >= 30] == [30, 60, 120]

def test_ua_ve_post_json():
    gorulen = {}
    def h(r):
        if r.url.path == "/robots.txt":
            return httpx.Response(404)
        gorulen.update(ua=r.headers["user-agent"], ct=r.headers.get("content-type"), ref=r.headers.get("referer"), govde=r.content)
        return httpx.Response(200, text="<div></div>")
    g, _ = _getirici(h)
    assert g.post_json("egm", "https://x.test/p", {"page": 2}, referer="https://x.test/s") == "<div></div>"
    assert "vatansagolsun-aktarim/1.0" in gorulen["ua"] and gorulen["ct"].startswith("application/json")
    assert gorulen["ref"] == "https://x.test/s" and b'"page"' in gorulen["govde"]
```

- [ ] **Step 2: Testin başarısız olduğunu gör** — Run: `.venv/Scripts/python -m pytest tests/test_getirici.py -v` — Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Bağımlılıkları ekle (`pip install -e ".[dev]"`), ayarları ve `Getirici`'yi yaz; `.env.example`'a `KAYNAK_IZINLERI=["egm","sg","kahramanlar","sehitlerimiz"]` ve açıklama satırı ("bir site itiraz ederse buradan çıkarın") ekle**

- [ ] **Step 4: Testlerin geçtiğini gör** — Run: `.venv/Scripts/python -m pytest -q` — Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add app tests pyproject.toml .env.example
git commit -m "feat: hız sınırlı, robots'a uyan, izin kontrollü kaynak istemcisi"
```

---

### Task 3: Model ve şema değişiklikleri

**Files:**
- Modify: `app/models.py`, `app/schemas.py` (gerekirse), `tests/test_models.py`
- Create: `migrations/versions/0002_aktarim.py`

**Interfaces:**
- Produces:
  - `Sehit.isim_anahtari: str` (index) — `alanlari_yenile` içinde `katla(" ".join([ad, soyad or "", lakap or ""]).strip())`.
  - `Kaynak.kaynak_kodu: str | None` (String(50)), `Kaynak.dis_kimlik: str | None` (String(300)); `UniqueConstraint("kaynak_kodu", "dis_kimlik", name="uq_kaynak_dis_kimlik")`.
  - `class KaynakDurumu(Base)` (`kaynak_durumlari`): `kaynak_kodu: str` (birincil anahtar, String(50)), `imlec: str | None` (String(300); kaynağa özgü: sayfa no, en büyük id), `tamamlandi: bool = False`, `son_calisma: datetime | None`, `son_durum: str | None` (String(20): `basarili`/`hata`), `son_mesaj: str | None` (Text), `eklenen: int = 0`, `birlesen: int = 0`, `atlanan: int = 0`, `hatali: int = 0`.
  - Alembic `0002_aktarim`: sütunları/tabloyu/index'i/unique'i ekler; mevcut satırlar için `isim_anahtari`'nı doldurur (Python ile `sehitler` üzerinde döngü, `katla` kullanarak); `downgrade` geri alır. SQLite için `batch_alter_table`.

- [ ] **Step 1: Başarısız testleri ekle** — `tests/test_models.py`

```python
def test_isim_anahtari(sehit_ekle):
    s = sehit_ekle(ad="ÖMER", soyad="şahin")
    assert s.isim_anahtari == "omer sahin"
    t = sehit_ekle(ad="İsmail", soyad=None, lakap="Aşçıoğullarından")
    assert t.isim_anahtari == "ismail asciogullarindan"

def test_kaynak_dis_kimlik_tekil(session, sehit_ekle):
    import pytest
    from sqlalchemy.exc import IntegrityError
    from app.models import Kaynak
    s = sehit_ekle()
    s.kaynaklar.append(Kaynak(kaynak_adi="EGM", kaynak_kodu="egm", dis_kimlik="/a"))
    s.kaynaklar.append(Kaynak(kaynak_adi="EGM", kaynak_kodu="egm", dis_kimlik="/a"))
    with pytest.raises(IntegrityError):
        session.commit()
```
- [ ] **Step 2: Testin başarısız olduğunu gör** — Run: `.venv/Scripts/python -m pytest tests/test_models.py -v` — Expected: FAIL (`AttributeError`/`TypeError`)

- [ ] **Step 3: Modelleri ve `0002_aktarim` taşımasını yaz**

- [ ] **Step 4: Taşımayı doğrula**

Run: `DATABASE_URL=sqlite:///./.tmp_mig.db .venv/Scripts/alembic upgrade head && DATABASE_URL=sqlite:///./.tmp_mig.db .venv/Scripts/alembic check; rm -f .tmp_mig.db`
Expected: `No new upgrade operations detected.`

- [ ] **Step 5: Testlerin geçtiğini gör** — Run: `.venv/Scripts/python -m pytest -q` — Expected: tümü PASS

- [ ] **Step 6: Commit**

```bash
git add app migrations tests
git commit -m "feat: isim anahtarı, kaynak dış kimliği ve kaynak durumu tablosu"
```

---

### Task 4: Aktarım çekirdeği (eşleştir, birleştir, kaydet)

**Files:**
- Create: `app/aktarim.py`, `tests/test_aktarim.py`
- Modify: `app/repo.py` (gerekirse yardımcı sorgu)

**Interfaces:**
- Consumes: `HamKayit`, `SehitVeri`, `repo.yeni_sehit`, `Sehit.alanlari_yenile`, `ONCELIK` (bu dosyada tanımlanır)
- Produces (`app/aktarim.py`):
  - `ONCELIK: dict[str, int]` (Global Constraints'teki değerler)
  - `ham_to_veri(ham: HamKayit) -> SehitVeri` — `resmi_teyit=True`, `isimsiz=False`; `SehitVeri` alan uzunluklarına sığmayan metinler kırpılır (ad/soyad/… 200, donem 100).
  - `eslesen_bul(s: Session, ham: HamKayit) -> Sehit | None` — durumdan bağımsız arar; `isim_anahtari == katla(ad soyad lakap)` olan adaylar içinde sırayla:
    1. ikisinin de `tam` tarihi var ve eşit;
    2. biri `yil` hassasiyetli, yıllar eşit;
    3. en az biri tarihsiz/yıl-hassas ve (dolu `baba_adi` eşit **veya** dolu `donem` eşit **veya** dolu `kurum` eşit);
    4. aday tek ve ikisinin de tarihi yok.
    Eşleşme yoksa `None`. İki tam tarih farklıysa asla eşleşmez.
  - `@dataclass Sonuc(durum: Literal["yeni", "birlesti", "atlandi", "hatali"], sehit_id: int | None, mesaj: str | None = None)`
  - `kayit_aktar(s: Session, ham: HamKayit, *, yeni_durum: Durum = Durum.yayinda) -> Sonuc`:
    - `Kaynak(kaynak_kodu=ham.kaynak_kodu, dis_kimlik=ham.dis_kimlik)` zaten varsa → `atlandi`.
    - Eşleşen yoksa `repo.yeni_sehit(..., durum=yeni_durum)` + `Kaynak` → `yeni`.
    - Eşleşen varsa birleştir: `ONCELIK[ham] > ONCELIK[mevcut.kaynak_kodu]` ise ad/soyad/lakap/tarih alanları/görev/kategori hamdan alınır ve `kaynak_kodu` güncellenir; aksi halde yalnızca mevcutta boş olan alanlar doldurulur (tarih yalnızca mevcut `bilinmiyor` ya da hamın hassasiyeti daha yüksekse: `bilinmiyor < yil < tam`). `durum` değişmez. `Kaynak` eklenir → `birlesti`.
    - `SehitVeri` doğrulama hatası ya da beklenmeyen istisna → işlem geri alınır, `hatali` (mesajla). Diğer kayıtları etkilemez (kayıt başına savepoint: `s.begin_nested()`).
  - `kaynak_calistir(s: Session, kaynak_kodu: str, sayfalar: Iterable[tuple[str, list[HamKayit]]], *, yeni_durum: Durum = Durum.yayinda) -> KaynakDurumu` — her `(imlec, kayitlar)` çifti için kayıtları aktarır, sayaçları artırır, sayfa bitince `KaynakDurumu.imlec = imlec` yazıp commit eder. Üretici `KaynakHatasi` fırlatırsa: `son_durum="hata"`, `son_mesaj` yazılır, imleç son başarılı sayfada kalır, istisna yutulmaz değil — `KaynakDurumu` döner. Üretici normal biterse `tamamlandi=True`, `son_durum="basarili"`. `son_calisma` her durumda UTC şimdi.
  - `kaynak_durumu(s: Session, kaynak_kodu: str) -> KaynakDurumu` (yoksa oluşturur).

- [ ] **Step 1: Başarısız testleri yaz** — `tests/test_aktarim.py`

```python
from datetime import date
from app import aktarim
from app.kaynaklar import HamKayit, KaynakHatasi
from app.models import Hassasiyet as H, Durum, Sehit

def ham(**kw):
    v = dict(kaynak_kodu="kahramanlar", dis_kimlik=kw.pop("dk", "k1"), ad="Tayfun", soyad="Baş",
             tarih=date(2026, 6, 14), hassasiyet=H.tam, yil=2026, kaynak_adi="kahramanlar.org.tr")
    v.update(kw); return HamKayit(**v)

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
```

- [ ] **Step 2: Testin başarısız olduğunu gör** — Run: `.venv/Scripts/python -m pytest tests/test_aktarim.py -v` — Expected: FAIL (`ImportError`)

- [ ] **Step 3: `app/aktarim.py`'yi yaz**

- [ ] **Step 4: Testlerin geçtiğini gör** — Run: `.venv/Scripts/python -m pytest -q` — Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "feat: aktarım çekirdeği — eşleştirme, öncelikli birleştirme, kaldığı yerden devam"
```

---

### Task 5: EGM okuyucu

**Files:**
- Create: `app/kaynaklar/egm.py`, `tests/test_kaynak_egm.py`, `tests/fixtures/kaynaklar/egm_liste.html`, `egm_ajax_dolu.html`, `egm_ajax_bos.html`, `egm_istihbarat.html` (araştırma dosyalarından kısaltılmış: liste 3 kart, ajax 2 kart, istihbarat 3 görsel)

**Interfaces:**
- Consumes: `Getirici`, `HamKayit`, `tarih_coz`, `isim_ayir`
- Produces (`app/kaynaklar/egm.py`):
  - Sabitler: `KOK = "https://www.egm.gov.tr"`, `AJAX = KOK + "/ISAYWebPart/ContentList/DahaFazlaYukle"`, `BOLUMLER = {"sehitlerimiz": ("/sehitlerimiz", "YNcLZaW4rMBeGR5FZn5E6A=="), "ozelharekat": ("/ozelharekat/sehitlerimiz", "MNwu2a6REuJpCzWh5FhgSg==")}`, `ISTIHBARAT = "/istihbarat/istihbarat-sehitlerimiz"`.
  - `kartlari_ayristir(html: str, *, bolum: str) -> list[HamKayit]` — seçiciler: `a.news-card-horizontal[href]`, içinde `.card-title` ("Şehit Polis Memuru Ahmet TÜRKOĞLU"), `.cardDate` ("08.10.2026"). `dis_kimlik` = href'in yol kısmı (`/sehit-polis-memuru-ahmet-turkoglu`); `kaynak_url` = `KOK + yol`; `kategori=polis`, `kurum="Emniyet Genel Müdürlüğü"` (özel harekât için `"Emniyet Genel Müdürlüğü — Özel Harekât"`), `kaynak_adi="Emniyet Genel Müdürlüğü"`, `isim_ayir(..., soyadli=True)`.
  - `istihbarat_ayristir(html: str) -> list[HamKayit]` — `img[alt]` değerleri (boş/“logo” içerenler hariç); tarih yok (`bilinmiyor`), `kurum="Emniyet Genel Müdürlüğü — İstihbarat"`, `dis_kimlik = "istihbarat:" + slug(alt)`.
  - `sayfalar(g: Getirici, *, baslangic: str | None) -> Iterator[tuple[str, list[HamKayit]]]` — imleç biçimi `"{bolum}:{sayfa}"`. Sıra: `sehitlerimiz` bölümü sayfa 1 (GET liste), sonra sayfa 2.. (POST AJAX gövdesi `{"page": N, "ContentTypeId": id, "OrderByAsc": "true", "ContentCount": "6"}`, `referer` liste URL'si) boş yanıt gelene kadar; sonra `ozelharekat` aynı şekilde; en son `istihbarat:1`. `baslangic` verilirse o imleçten **sonraki** sayfadan devam eder.

- [ ] **Step 1: Fixture dosyalarını oluştur** — `docs/superpowers/plans/kaynaklar/veri/` altındaki EGM dosyalarından kısalt; sahte veri uydurma.

- [ ] **Step 2: Başarısız testleri yaz** — `tests/test_kaynak_egm.py`

```python
from pathlib import Path
from datetime import date
from app.kaynaklar import egm
from app.models import Kategori

F = Path(__file__).parent / "fixtures" / "kaynaklar"
oku = lambda ad: (F / ad).read_text(encoding="utf-8")

def test_kartlar():
    k = egm.kartlari_ayristir(oku("egm_liste.html"), bolum="sehitlerimiz")
    assert len(k) == 3
    ilk = k[0]
    assert (ilk.ad, ilk.soyad, ilk.gorev, ilk.tarih) == ("Ahmet", "TÜRKOĞLU", "Polis Memuru", date(2026, 10, 8))
    assert ilk.dis_kimlik == "/sehit-polis-memuru-ahmet-turkoglu" and ilk.kategori == Kategori.polis
    assert ilk.kaynak_url == "https://www.egm.gov.tr/sehit-polis-memuru-ahmet-turkoglu"

def test_istihbarat_tarihsiz():
    k = egm.istihbarat_ayristir(oku("egm_istihbarat.html"))
    assert len(k) == 3 and all(x.tarih is None for x in k)
    assert any(x.soyad == "KILIÇTEPE" for x in k)

class SahteGetirici:
    def __init__(self, ajax_sayfalari): self.ajax, self.cagrilar = ajax_sayfalari, []
    def metin(self, kod, url, params=None):
        self.cagrilar.append(("GET", url)); return oku("egm_istihbarat.html") if "istihbarat" in url else oku("egm_liste.html")
    def post_json(self, kod, url, govde, *, referer):
        self.cagrilar.append(("POST", govde["page"], govde["ContentTypeId"]))
        return self.ajax.get((govde["ContentTypeId"], govde["page"]), "")

def test_sayfalar_ve_devam():
    g = SahteGetirici({("YNcLZaW4rMBeGR5FZn5E6A==", 2): oku("egm_ajax_dolu.html")})
    imlecler = [i for i, _ in egm.sayfalar(g, baslangic=None)]
    assert imlecler == ["sehitlerimiz:1", "sehitlerimiz:2", "ozelharekat:1", "istihbarat:1"]
    g2 = SahteGetirici({})
    assert [i for i, _ in egm.sayfalar(g2, baslangic="ozelharekat:1")] == ["istihbarat:1"]
```

- [ ] **Step 3: Testin başarısız olduğunu gör** — Run: `.venv/Scripts/python -m pytest tests/test_kaynak_egm.py -v` — Expected: FAIL

- [ ] **Step 4: `app/kaynaklar/egm.py`'yi yaz** (HTML için `selectolax.parser.HTMLParser`)

- [ ] **Step 5: Testlerin geçtiğini gör** — Run: `.venv/Scripts/python -m pytest -q` — Expected: tümü PASS

- [ ] **Step 6: Commit** — `git add app tests && git commit -m "feat: EGM şehit listeleri okuyucusu"`

---

### Task 6: Sahil Güvenlik okuyucu

**Files:**
- Create: `app/kaynaklar/sg.py`, `tests/test_kaynak_sg.py`, `tests/fixtures/kaynaklar/sg.html` (araştırma örneğinden 3 kart)

**Interfaces:**
- Produces: `KOK = "https://www.sg.gov.tr"`; `ayristir(html: str) -> list[HamKayit]` — `div.manager-vertical-card`; ad `.manager-name`; tarih `.manager-sm-card-body p` ("20 Kasım 2019") → `tarih_coz`; `dis_kimlik` = PDF href'i varsa onun yolu, yoksa `"sg:" + slug(ad)`; `kategori=asker`, `kurum="Sahil Güvenlik Komutanlığı"`, `kaynak_adi="Sahil Güvenlik Komutanlığı"`, `kaynak_url=KOK + "/sehitlerimiz"`. `sayfalar(g, *, baslangic) -> Iterator` — tek sayfa, imleç `"1"`; `baslangic == "1"` ise hiçbir şey üretmez.

- [ ] **Step 1: Fixture + başarısız testler** — `tests/test_kaynak_sg.py`:

```python
from pathlib import Path
from datetime import date
from app.kaynaklar import sg

def test_sg():
    k = sg.ayristir((Path(__file__).parent / "fixtures/kaynaklar/sg.html").read_text(encoding="utf-8"))
    assert len(k) == 3
    hakan = next(x for x in k if x.soyad == "KARATAŞ")
    assert (hakan.ad, hakan.tarih, hakan.kurum) == ("Hakan", date(2019, 11, 20), "Sahil Güvenlik Komutanlığı")
```

- [ ] **Step 2–5:** başarısız gör (`pytest tests/test_kaynak_sg.py -v`), yaz, tüm testleri geçir, commit: `git commit -m "feat: Sahil Güvenlik şehitleri okuyucusu"`

---

### Task 7: kahramanlar.org.tr okuyucu

**Files:**
- Create: `app/kaynaklar/kahramanlar.py`, `tests/test_kaynak_kahramanlar.py`, `tests/fixtures/kaynaklar/kh_sayfa.json` (araştırma `kh_p1.json` + `kh_polis.json` + `kh_msb26.json`'dan 6 kayıt, `has_more: true`), `kh_son.json` (1 kayıt, `has_more: false`)

**Interfaces:**
- Produces:
  - `API = "https://kahramanlar.org.tr/api.php"`, `LIMIT = 50`
  - `kayit_cevir(k: dict) -> HamKayit | None` — boş/"-" alanlar `None`. `dis_kimlik = "kh:" + sha1(json.dumps(k, sort_keys=True, ensure_ascii=False))[:20]`. Tarih `tarih_coz(k["sehadet_tarihi"])`; tarih yoksa `harp` içinde `(YYYY)` varsa → `yil` hassasiyeti o yıl. İsim: `isim_ayir(k["ad"], soyadli=soyadli_mi(yil, harp))`; `rutbe` "Er / Erbaş" gibi değerler `gorev`'e (isim_ayir'dan gelen görev öncelikli). `lakap` "ŞEHİT POLİS" gibi unvan ise atılır (lakap yalnızca `soyadli=False` iken tutulur). `memleketi` "TÜRKİYE"/"MSB" ise `None`; aksi `ad_duzenle(memleketi)`. `dogum_yili` sayı değilse `None`. `donem = harp`. `kategori = kategori_bul(rutbe, harp)`. `kaynak_adi="kahramanlar.org.tr"`, `kaynak_url="https://kahramanlar.org.tr/"`. Ad boşsa `None`.
  - `sayfalar(g, *, baslangic: str | None)` — imleç sayfa numarası; `baslangic` yoksa 1'den; her sayfa `g.json("kahramanlar", API, params={"page": n, "limit": LIMIT})`; `has_more` false olunca durur.

- [ ] **Step 1: Başarısız testler** — `tests/test_kaynak_kahramanlar.py`:

```python
from datetime import date
from app.kaynaklar import kahramanlar as kh
from app.models import Hassasiyet as H, Kategori as K

def test_modern_polis():
    h = kh.kayit_cevir({"ad":"Tayfun BAŞ","rutbe":"Polis","sehadet_tarihi":"14.06.2026","harp":"POLİS ŞEHİDİ","baba_adi":"","lakap":"","dogum_yili":"","memleketi":"","il_filtresi":"","sayfa":0})
    assert (h.ad, h.soyad, h.tarih, h.kategori, h.memleket) == ("Tayfun", "BAŞ", date(2026, 6, 14), K.polis, None)

def test_osmanli_tek_isim():
    h = kh.kayit_cevir({"ad":"MUSTAFA","rutbe":"Er / Erbaş","sehadet_tarihi":"","harp":"BİRİNCİ DÜNYA SAVAŞI (1914-1918) ÇANAKKALE CEPHESİ","baba_adi":"HASAN","lakap":"","dogum_yili":"1885","memleketi":"KASTAMONU ARAÇ","il_filtresi":"KASTAMONU","sayfa":0})
    assert (h.ad, h.soyad, h.hassasiyet, h.baba_adi, h.dogum_yili, h.memleket) == ("Mustafa", None, H.bilinmiyor, "Hasan", 1885, "Kastamonu Araç")

def test_msb_yil_parantezden():
    h = kh.kayit_cevir({"ad":"ULŞ. UZM. ÇVŞ. ABDURRAHMAN HİLAL","rutbe":"Uzman Çavuş","sehadet_tarihi":"","harp":"MSB GÜNCEL ŞEHİT VE VEFAT DUYURULARI (2026)","baba_adi":"","lakap":"","dogum_yili":"","memleketi":"TÜRKİYE","il_filtresi":"MSB","sayfa":0})
    assert (h.ad, h.soyad, h.gorev, h.hassasiyet, h.yil, h.memleket) == ("Abdurrahman", "HİLAL", "Uzman Çavuş", H.yil, 2026, None)

def test_ayni_kayit_ayni_kimlik():
    k = {"ad":"ALİ","rutbe":"Er / Erbaş","sehadet_tarihi":"","harp":"X","baba_adi":"","lakap":"","dogum_yili":"","memleketi":"","il_filtresi":"","sayfa":0}
    assert kh.kayit_cevir(dict(k)).dis_kimlik == kh.kayit_cevir(dict(k)).dis_kimlik

def test_sayfalar_has_more():
    import json; from pathlib import Path
    F = Path(__file__).parent / "fixtures/kaynaklar"
    yanitlar = {1: json.loads((F / "kh_sayfa.json").read_text(encoding="utf-8")), 2: json.loads((F / "kh_son.json").read_text(encoding="utf-8"))}
    class G:
        def json(self, kod, url, params=None): return yanitlar[params["page"]]
    assert [i for i, _ in kh.sayfalar(G(), baslangic=None)] == ["1", "2"]
    assert [i for i, _ in kh.sayfalar(G(), baslangic="1")] == ["2"]
```

- [ ] **Step 2–5:** başarısız gör, yaz, tüm testleri geçir, commit: `git commit -m "feat: kahramanlar.org.tr API okuyucusu"`

---

### Task 8: sehitlerimiz.org.tr okuyucu

**Files:**
- Create: `app/kaynaklar/sehitlerimiz.py`, `tests/test_kaynak_sehitlerimiz.py`, fixtures `sh_kayit.html` (bir kayıt sayfası, JSON-LD dahil), `sh_yil.html` (bir `/yil/` sayfası, 3 isim, `rel=next` var), `sh_yil_son.html` (`rel=next` yok), `sh_arsiv.html` (`#son-eklenenler` 3 kayıt)

**Interfaces:**
- Produces:
  - `KOK = "https://sehitlerimiz.org.tr"`, `KAYNAK_ADI = "sehitlerimiz.org.tr — Türkiye Şehit Arşivi"`
  - `kayit_id(url: str) -> int` — `/sehit/...-116814` → `116814`
  - `kayit_ayristir(html: str, url: str) -> HamKayit` — önce JSON-LD `Person` (`name`, `jobTitle`, `deathDate` ISO, `deathPlace.name`, `birthPlace.name`, `affiliation.name`); eksikler `dl.fields` (`dt` → `dd`: "Rütbe / Görev", "Baba Adı", "Doğum Yeri", "Memleket", "Şehadet Tarihi", "Şehadet Yeri", "Dönem / Cephe", "Kurum"). `memleket` = Memleket, yoksa Doğum Yeri. `dis_kimlik = str(kayit_id(url))`, `kaynak_url = KOK + yol`, `kaynak_adi = KAYNAK_ADI`. İsim `isim_ayir(name, soyadli=soyadli_mi(yil, donem))`. Kategori `kategori_bul(jobTitle, kurum, donem)`.
  - `yil_listesi_ayristir(html: str) -> tuple[list[str], bool]` — `ol.name-list li a[href^="/sehit/"]` yolları ve `link[rel=next]`/`a[rel=next]` var mı.
  - `son_eklenenler_ayristir(html: str) -> list[str]` — `#son-eklenenler ol.name-list li a[href^="/sehit/"]` yolları.
  - `sayfalar(g, *, baslangic: str | None, yillar: range | None = None) -> Iterator[tuple[str, list[HamKayit]]]` — toplu aktarım: varsayılan `yillar = range(2000, bugun().year + 1)`; her yıl için `/yil/{yyyy}?sayfa=N` (N=1..; 404 → yıl atlanır), listedeki her kayıt sayfasını ayrı GET ile çeker; imleç `"{yyyy}:{N}"`; `baslangic` sonrasından devam. (Spec 4.3: 2000 öncesi kayıtlar kahramanlar'dan gelir; tam tarihli 2000 sonrası kayıtlar buradan.)
  - `yeni_kayitlar(g, *, son_id: int) -> tuple[list[HamKayit], int]` — `/arsiv` sayfasındaki son eklenenlerden `kayit_id > son_id` olanların sayfalarını çeker; `(kayitlar, en_buyuk_id)` döner (yeni yoksa `([], son_id)`).

- [ ] **Step 1: Başarısız testler** — `tests/test_kaynak_sehitlerimiz.py`:

```python
from pathlib import Path
from datetime import date
from app.kaynaklar import sehitlerimiz as sh

F = Path(__file__).parent / "fixtures/kaynaklar"
oku = lambda ad: (F / ad).read_text(encoding="utf-8")

def test_kayit():
    h = sh.kayit_ayristir(oku("sh_kayit.html"), "/sehit/mustafa-aslan-116814")
    assert (h.ad, h.soyad, h.tarih, h.dis_kimlik) == ("Mustafa", "ASLAN", date(2026, 10, 14), "116814")
    assert h.kaynak_adi == "sehitlerimiz.org.tr — Türkiye Şehit Arşivi"
    assert h.kaynak_url == "https://sehitlerimiz.org.tr/sehit/mustafa-aslan-116814"

def test_yil_listesi():
    yollar, devam = sh.yil_listesi_ayristir(oku("sh_yil.html"))
    assert len(yollar) == 3 and devam is True
    assert sh.yil_listesi_ayristir(oku("sh_yil_son.html"))[1] is False

def test_yeni_kayitlar():
    class G:
        def __init__(s): s.cagrilar = []
        def metin(s, kod, url, params=None):
            s.cagrilar.append(url)
            return oku("sh_arsiv.html") if url.endswith("/arsiv") else oku("sh_kayit.html")
    g = G()
    yollar = sh.son_eklenenler_ayristir(oku("sh_arsiv.html"))
    en_buyuk = max(sh.kayit_id(y) for y in yollar)
    kayitlar, yeni_max = sh.yeni_kayitlar(g, son_id=en_buyuk - 1)
    assert len(kayitlar) == 1 and yeni_max == en_buyuk
    assert sh.yeni_kayitlar(G(), son_id=en_buyuk) == ([], en_buyuk)
```

(Fixture `sh_kayit.html` gerçek `/sehit/mustafa-aslan-116814` örneğinden; `sh_arsiv.html`'deki en büyük id bu kayıt olmalı, yoksa test fixture'a göre uyarlanır.)

- [ ] **Step 2–5:** başarısız gör, yaz, tüm testleri geçir, commit: `git commit -m "feat: sehitlerimiz.org.tr okuyucusu (kayıt, yıl listesi, son eklenenler)"`

---

### Task 9: `aktar` komutu

**Files:**
- Modify: `app/cli.py`, `app/aktarim.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: Task 4 `kaynak_calistir`, `kaynak_durumu`; Task 5–8 `sayfalar`
- Produces:
  - `aktarim.OKUYUCULAR: dict[str, Callable[[Getirici, str | None], Iterator]]` — `{"egm": ..., "sg": ..., "kahramanlar": ..., "sehitlerimiz": ...}`
  - `aktarim.kaynagi_aktar(s: Session, kod: str, g: Getirici, *, bastan: bool = False) -> KaynakDurumu` — `bastan` ise imleç ve `tamamlandi` sıfırlanır; `tamamlandi=True` ve `bastan=False` ise hiçbir şey yapmadan durumu döner; aksi `OKUYUCULAR[kod](g, durum.imlec)` ile `kaynak_calistir`. sehitlerimiz toplu aktarımı biterken `KaynakDurumu("sehitlerimiz_kontrol").imlec` = görülen en büyük kayıt id'si (12 saatlik kontrolün başlangıcı).
  - CLI: `python -m app.cli aktar <egm|sg|kahramanlar|sehitlerimiz|hepsi> [--bastan]` — `hepsi` sırası: `egm`, `sg`, `sehitlerimiz`, `kahramanlar` (yüksek öncelikli önce); izinsiz kaynak "atlandı: izin yok (KAYNAK_IZINLERI)" yazar, hata değil. Her kaynak sonunda tek satır özet: `egm: eklenen=… birlesen=… atlanan=… hatali=… durum=… imlec=…`. Hata durumunda çıkış kodu 1 ve "Kaldığı yerden devam etmek için aynı komutu tekrar çalıştırın." mesajı. Ctrl+C: o ana kadarki sayfalar kayıtlı kalır.
  - CLI: `python -m app.cli aktarim-durumu` — `KaynakDurumu` tablosunu yazdırır.

- [ ] **Step 1: Başarısız testler** — `tests/test_cli.py`'ye: (a) sahte okuyucu ile `kaynagi_aktar` iki kez çağrılınca ikincisinin hiçbir şey eklemediği ve kayıt sayısının değişmediği; (b) `bastan=True` ile imlecin sıfırlandığı; (c) okuyucu 2. sayfada `KaynakHatasi` fırlatınca CLI çıkış kodunun 1 olduğu ve tekrar çalıştırmanın 3. sayfadan devam ettiği; (d) `kaynak_izinleri=["egm"]` iken `aktar hepsi`'nin sehitlerimiz için "izin yok" yazdığı ve sahte getiricinin o kaynağa hiç çağrı almadığı. `OKUYUCULAR`, testlerde `monkeypatch.setitem` ile sahte üreticilerle değiştirilir.

- [ ] **Step 2–5:** başarısız gör, yaz, tüm testleri geçir, commit: `git commit -m "feat: aktar ve aktarim-durumu komutları"`

---

### Task 10: sehitlerimiz 12 saatlik kontrolü, zamanlayıcı, kurulum belgesi ve canlı deneme

**Files:**
- Create: `app/zamanlayici.py`, `tests/test_zamanlayici.py`
- Modify: `app/main.py` (lifespan), `app/config.py` (`zamanlayici_aktif: bool = False`), `app/cli.py` (`sehitlerimiz-kontrol`), `docker-compose.yml` (`ZAMANLAYICI_AKTIF=true`), `.env.example`, `README.md`

**Interfaces:**
- Produces:
  - `aktarim.sehitlerimiz_kontrol(s: Session, g: Getirici) -> KaynakDurumu` — `"sehitlerimiz"` izinlerde değilse hiçbir şey yapmaz (durum `son_mesaj="izin yok"`). Imleç (`sehitlerimiz_kontrol` durum kaydı) yoksa: `/arsiv`'deki en büyük id'yi imleç yapar, kayıt eklemez (ilk çalıştırma geçmişi taşımaz). Varsa `sh.yeni_kayitlar(g, son_id=imlec)` → her kayıt `kayit_aktar(..., yeni_durum=Durum.onay_bekliyor)`; imleç yeni en büyük id.
  - `app/zamanlayici.py`: `zamanlayici_kur(session_factory) -> BackgroundScheduler | None` — `zamanlayici_aktif` False ise `None`. True ise `BackgroundScheduler(timezone="Europe/Istanbul")`, iş `sehitlerimiz_kontrol` her **12 saatte** bir (`IntervalTrigger(hours=12)`, `max_instances=1`, `coalesce=True`, ilk çalışma başlangıçtan 5 dk sonra); her çalışma kendi oturumunu açar/kapatır, istisnaları loglar (yutmaz değil: loglayıp `KaynakDurumu`'na yazar).
  - `create_app` lifespan: başlangıçta `zamanlayici_kur(...)`, kapanışta `shutdown(wait=False)`. `app.state.zamanlayici`.
  - CLI: `python -m app.cli sehitlerimiz-kontrol` — elle tek çalıştırma.
  - README: "Geçmiş verileri aktarma" bölümü — kaynakları açıp kapatma (`KAYNAK_IZINLERI`; bir site itiraz ederse çıkarın, kayıtlarını API'den gizlemek için `API_HARIC_KAYNAKLAR`), komutlar (`docker compose exec app python -m app.cli aktar hepsi`, `aktarim-durumu`), tahmini süre (kahramanlar ≈1.850 istek × 2 sn ≈ 1 saat; sehitlerimiz 2000 sonrası kayıt sayfaları — yüzlerce/binlerce istek, saatler sürebilir; komut kesilirse tekrar çalıştırmak kaldığı yerden devam eder), arka planda çalıştırma (`docker compose exec -d ...` ya da `nohup`), 12 saatlik kontrolün sehitlerimiz kaynağı açıkken çalıştığı ve gelen kayıtların panelde onaya düştüğü.

- [ ] **Step 1: Başarısız testler** — `tests/test_zamanlayici.py`:

```python
from app import aktarim
from app.models import Durum, Sehit
from app.kaynaklar import HamKayit

def test_zamanlayici_kapaliyken_kurulmaz(app):
    from app.zamanlayici import zamanlayici_kur
    assert zamanlayici_kur(app.state.session_factory) is None

def test_kontrol_izin_yoksa_istek_atmaz(session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["egm"])
    class G:
        def metin(self, *a, **k): raise AssertionError("istek atılmamalı")
    d = aktarim.sehitlerimiz_kontrol(session, G())
    assert d.son_mesaj == "izin yok"

def test_kontrol_ilk_calisma_imlec_kurar_sonra_onaya_dusurur(session, monkeypatch):
    from app.config import get_settings
    from app.kaynaklar import sehitlerimiz as sh
    from datetime import date
    from app.models import Hassasiyet as H
    monkeypatch.setattr(get_settings(), "kaynak_izinleri", ["sehitlerimiz"])
    durum = {"max": 100}
    def sahte_yeni(g, *, son_id):
        if durum["max"] > son_id:
            return [HamKayit(kaynak_kodu="sehitlerimiz", dis_kimlik=str(durum["max"]), ad="Ali", soyad="Kaya",
                             tarih=date(2026, 10, 20), hassasiyet=H.tam, yil=2026, kaynak_adi=sh.KAYNAK_ADI)], durum["max"]
        return [], son_id
    monkeypatch.setattr(sh, "yeni_kayitlar", sahte_yeni)
    monkeypatch.setattr(sh, "en_buyuk_id", lambda g: 100, raising=False)
    aktarim.sehitlerimiz_kontrol(session, object())          # ilk: imleç=100, kayıt yok
    assert session.query(Sehit).count() == 0
    durum["max"] = 101
    aktarim.sehitlerimiz_kontrol(session, object())
    s = session.query(Sehit).one()
    assert s.durum == Durum.onay_bekliyor
```

(İlk çalıştırmada en büyük id'yi bulmak için `sh.en_buyuk_id(g) -> int` yardımcı fonksiyonu Task 8'deki `son_eklenenler_ayristir` + `kayit_id` ile bu görevde eklenir.)

- [ ] **Step 2: Testin başarısız olduğunu gör** — Run: `.venv/Scripts/python -m pytest tests/test_zamanlayici.py -v` — Expected: FAIL

- [ ] **Step 3: `sehitlerimiz_kontrol`, `en_buyuk_id`, `app/zamanlayici.py`, lifespan, CLI ve README/compose/.env.example değişikliklerini yaz**

- [ ] **Step 4: Testlerin geçtiğini gör** — Run: `.venv/Scripts/python -m pytest -q` — Expected: tümü PASS

- [ ] **Step 5: Küçük canlı deneme (yalnızca izinli resmî kaynaklar)**

Yerel `.env` ile, geçici bir SQLite dosyasına: `DATABASE_URL=sqlite:///./.canli_deneme.db .venv/Scripts/alembic upgrade head && DATABASE_URL=sqlite:///./.canli_deneme.db .venv/Scripts/python -m app.cli aktar sg && DATABASE_URL=sqlite:///./.canli_deneme.db .venv/Scripts/python -m app.cli aktar egm`
Expected: `sg: eklenen=19 ...`, `egm: eklenen≈400-550 ... durum=basarili`; ikinci kez aynı komutlar `eklenen=0`. Ardından iki arşivden yalnızca küçük bir parça: kahramanlar için ilk 2 sayfayı, sehitlerimiz için tek bir yılın ilk sayfasını getiren geçici bir Python betiği (scratch klasöründe, depoya girmez) okuyucuların canlı sayfada çalıştığını doğrular. Tam arşiv aktarımı burada yapılmaz (saatler sürer; sunucuda sahibi çalıştırır). Sonra `rm .canli_deneme.db`. Sonuç sayılarını rapora yaz.

- [ ] **Step 6: Commit**

```bash
git add app tests README.md docker-compose.yml .env.example
git commit -m "feat: sehitlerimiz 12 saatlik kontrolü, zamanlayıcı ve aktarım belgesi"
```
