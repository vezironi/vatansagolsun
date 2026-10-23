# vatansagolsun — Plan 1: Çekirdek (veri modeli, API, site, onay paneli) Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Şehit kayıtlarını tutan veritabanı, herkese açık JSON API, B temalı herkese açık site ve yalnızca yöneticinin girdiği onay paneli; Docker ile tek komutla ayağa kalkar.

**Architecture:** Tek bir FastAPI uygulaması üç yönlendirici sunar: `/api` (JSON), herkese açık sayfalar (Jinja2, sunucu tarafı) ve `/panel` (oturumlu yönetim). Tüm sorgular `app/repo.py` içindeki fonksiyonlardan geçer; site, API ve panel aynı fonksiyonları kullanır. Türkçe metin işlemleri (büyük/küçük harf, slug, arama) `app/text.py` içinde toplanır. Testler SQLite bellek içi veritabanıyla, üretim PostgreSQL ile çalışır; şema taşınabilir tutulur (tarih parçaları ayrı tamsayı sütunlarında).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL 16 (psycopg 3), Jinja2, pydantic-settings, Starlette SessionMiddleware (itsdangerous), bcrypt, slowapi, tzdata, pytest + httpx. Dağıtım: Docker Compose + Caddy.

**Spec:** `docs/superpowers/specs/2026-10-23-vatansagolsun-design.md`

**Bu plan kapsamı dışında (sonraki planlar):** Plan 2 — geçmiş veri aktarımı (resmî kaynaklar, kahramanlar, sehitlerimiz). Plan 3 — 30 dakikalık toplayıcı, Claude Haiku analizi, sehitlerimiz 12 saatlik kontrolü, paneldeki toplayıcı durum bölümü. Bu plandaki `Sehit.kaynak_kodu`, `resmi_teyit`, `isimsiz` alanları ve `Kaynak` tablosu o planlar için hazırlanır.

## Global Constraints

- Arayüz ve API alan adları Türkçe; Türkçe karakterler (İ/ı, Ş, Ğ, Ç, Ö, Ü) arama, büyük/küçük harf ve slug üretiminde doğru işlenir.
- Saat dilimi `Europe/Istanbul`: "bugün", "bu yıl" hep Türkiye saatine göre.
- Site ve API yalnızca `durum == "yayinda"` kayıtları gösterir.
- "Bugün"/yıl dönümü listesi: `tarih_hassasiyeti == "tam"` ve `yil >= 2000` ve gün/ay eşleşmesi.
- Sayımlar: Toplam = yayındaki tüm kayıtlar; Bu yıl = şehadet yılı bu takvim yılı olan yayındaki kayıtlar. Sitede "kayıt sayısı resmî toplam değildir" notu.
- API: anahtarsız, JSON, IP başına istek sınırı (varsayılan `60/minute`), `adet` en fazla 100, site tablosu sayfa başına 25.
- Kalıcı kayıt adresi: `/sehit/{slug}-{id}`.
- Görsel dil: koyu arka plan, vurgu `#e30a17`, isimlerde Cormorant Garamond, metinde Inter; referans `docs/superpowers/specs/mockups/ana-sayfa-b.html` ("sayacın üstünde" düzeni; alttaki tema geçiş çubuğu alınmaz, "Önizleme" şeridi alınmaz).
- Özel kaydırma çubuğu: ince, koyu; tutamaç koyu gri, üzerine gelince kırmızı; `::-webkit-scrollbar` + Firefox `scrollbar-color`/`scrollbar-width`.
- Dar ekranda (≤700px) tablonun Memleket ve Kurum sütunları gizlenir.
- Commit mesajları şu satırla biter: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. Türkçe arama: "sahin", "Şahin", "ŞAHİN", "şahİn" aynı kişiyi bulur; "ISIK" araması "Işık"ı bulur. → Task 1 ve Task 3 testleri.
2. Gece yarısı saat dilimi: UTC 21:30 (İstanbul 00:30, ertesi gün) anında "bugün" İstanbul tarihidir. → Task 2 testi.
3. 29 Şubat: artık olmayan yıllarda 28 Şubat yıl dönümü listesi 29 Şubat şehitlerini de içerir. → Task 3 testi.
4. Soyadsız/tarihsiz eski kayıtlar: görünen ad lakapla oluşur, sıralamada en sona düşer, "2000 öncesi" filtresinde görünür, sayfalar hata vermeden çizilir. → Task 1, 3, 5 testleri.
5. Onay bekleyen/reddedilen kayıtlar hiçbir yoldan sızmaz: sayaç, liste, bugün kutusu, `/api/sehitler/{id}`, `/sehit/...` sayfası. → Task 3, 4, 6 testleri.

---

## Dosya yapısı

```
pyproject.toml                 bağımlılıklar, pytest ayarı
.env.example                   örnek ortam değişkenleri
Dockerfile, docker-compose.yml, Caddyfile
alembic.ini, migrations/       şema taşımaları (PostgreSQL)
README.md                      Türkçe, adım adım kurulum
app/
  config.py      Settings
  db.py          Base, motor, oturum, get_session
  text.py        Türkçe metin yardımcıları
  dates.py       bugun()
  models.py      Sehit, Kaynak, Bildirim + enum'lar
  repo.py        tüm okuma/yazma fonksiyonları
  schemas.py     API yanıt modelleri, SehitVeri (düzenlenebilir alanlar)
  api.py         /api yönlendiricisi
  site.py        herkese açık sayfalar
  admin.py       /panel yönlendiricisi + kimlik doğrulama
  cli.py         sifre-olustur, ornek-veri
  main.py        create_app()
  templates/     base.html, index.html, _bugun.html, _tablo.html, sehit.html,
                 yil_donumleri.html, hakkinda.html, bildir.html,
                 panel/{base,giris,liste,duzenle,bildirimler}.html
  static/        site.css, site.js, panel.css
tests/
  conftest.py    session, client, sehit_ekle fabrikası, panel_client
  test_text.py, test_dates.py, test_repo.py, test_api.py, test_site.py, test_admin.py
```

---

### Task 1: Proje iskeleti ve Türkçe metin yardımcıları

**Files:**
- Create: `pyproject.toml`, `app/__init__.py`, `app/text.py`, `tests/__init__.py`, `tests/test_text.py`

**Interfaces:**
- Produces (`app/text.py`):
  - `tr_lower(s: str) -> str` — `I→ı`, `İ→i`, sonra `lower()`
  - `tr_upper(s: str) -> str` — `i→İ`, `ı→I`, sonra `upper()`
  - `ad_duzenle(s: str) -> str` — her kelime Türkçe kurallarla baş harfi büyük: `"AHMET LÜTFİ" → "Ahmet Lütfi"`, `"ismail" → "İsmail"`
  - `soyad_duzenle(s: str) -> str` — `tr_upper` + boşluk kırpma
  - `katla(s: str) -> str` — arama/slug için: `tr_lower`, sonra `ç→c ğ→g ı→i ö→o ş→s ü→u â→a î→i û→u`, birden çok boşluk tek boşluk
  - `slug(s: str) -> str` — `katla` + harf/rakam dışını `-` yap, baştaki/sondaki `-` sil: `"Ahmet Yılmaz" → "ahmet-yilmaz"`
  - `gorunen_ad(ad: str, soyad: str | None, lakap: str | None) -> str` — soyad varsa `"Ad SOYAD"`; yoksa lakap varsa `"Ad — Lakap"`; yoksa `"Ad"`

- [ ] **Step 1: `pyproject.toml` oluştur**

Proje adı `vatansagolsun`, `requires-python = ">=3.12"`. Bağımlılıklar: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0`, `alembic`, `psycopg[binary]`, `jinja2`, `python-multipart`, `pydantic-settings`, `itsdangerous`, `bcrypt`, `slowapi`, `tzdata`. Opsiyonel `dev`: `pytest`, `httpx`. `[tool.pytest.ini_options] testpaths = ["tests"]`. Kur: `python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"` (Windows; Linux'ta `.venv/bin/pip`).

- [ ] **Step 2: Başarısız testleri yaz** — `tests/test_text.py`

```python
from app.text import tr_lower, tr_upper, ad_duzenle, soyad_duzenle, katla, slug, gorunen_ad

def test_tr_buyuk_kucuk():
    assert tr_lower("IŞIK İLHAN") == "ışık ilhan"
    assert tr_upper("işık ılgaz") == "IŞIK ILGAZ"

def test_ad_duzenle():
    assert ad_duzenle("AHMET LÜTFİ") == "Ahmet Lütfi"
    assert ad_duzenle("ismail") == "İsmail"
    assert ad_duzenle("  ışıl  ") == "Işıl"

def test_soyad_duzenle():
    assert soyad_duzenle(" yılmaz ") == "YILMAZ"
    assert soyad_duzenle("şimşek") == "ŞİMŞEK"

def test_katla_esitler():
    assert katla("ŞAHİN") == katla("Şahin") == katla("sahin") == "sahin"
    assert katla("ISIK") == katla("Işık") == "isik"
    assert katla("Ahmet   Çağrı") == "ahmet cagri"

def test_slug():
    assert slug("Ahmet Yılmaz") == "ahmet-yilmaz"
    assert slug("İsmail — Aşçıoğullarından") == "ismail-ascioglullarindan"

def test_gorunen_ad():
    assert gorunen_ad("Ahmet", "YILMAZ", None) == "Ahmet YILMAZ"
    assert gorunen_ad("İsmail", None, "Aşçıoğullarından") == "İsmail — Aşçıoğullarından"
    assert gorunen_ad("Mehmet", None, None) == "Mehmet"
```

- [ ] **Step 3: Testin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_text.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.text'`

- [ ] **Step 4: `app/text.py` fonksiyonlarını yukarıdaki imzalarla yaz**

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `.venv/Scripts/python -m pytest tests/test_text.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml app tests
git commit -m "feat: proje iskeleti ve Türkçe metin yardımcıları"
```

---

### Task 2: Ayarlar, veritabanı, modeller, bugün tarihi

**Files:**
- Create: `app/config.py`, `app/db.py`, `app/dates.py`, `app/models.py`, `tests/conftest.py`, `tests/test_dates.py`, `tests/test_models.py`

**Interfaces:**
- Consumes: `app.text.katla`, `slug`, `ad_duzenle`, `soyad_duzenle`
- Produces:
  - `app/config.py`: `class Settings(BaseSettings)` alanları: `database_url: str = "sqlite:///./yerel.db"`, `secret_key: str = "degistir"`, `admin_kullanici: str = "admin"`, `admin_sifre_hash: str = ""`, `api_haric_kaynaklar: list[str] = []`, `istek_siniri: str = "60/minute"`, `site_url: str = "http://localhost:8000"`; `.env` dosyasından okur. `get_settings() -> Settings` (`lru_cache`).
  - `app/db.py`: `class Base(DeclarativeBase)`, `motor_olustur(url: str) -> Engine`, `get_session() -> Iterator[Session]` (FastAPI bağımlılığı; `app.state.session_factory` kullanır).
  - `app/dates.py`: `TZ = ZoneInfo("Europe/Istanbul")`; `bugun(simdi: datetime | None = None) -> date` — `simdi` verilmezse `datetime.now(TZ)`; verilirse `simdi.astimezone(TZ).date()`.
  - `app/models.py`:
    - `class Durum(StrEnum)`: `onay_bekliyor`, `yayinda`, `reddedildi`
    - `class Hassasiyet(StrEnum)`: `tam`, `yil`, `bilinmiyor`
    - `class Kategori(StrEnum)`: `asker`, `jandarma`, `polis`, `ogretmen`, `diger`
    - `class Sehit(Base)` (`sehitler`): `id`, `ad: str`, `soyad: str | None`, `lakap: str | None`, `tarih_hassasiyeti: Hassasiyet`, `sehadet_tarihi: date | None`, `yil: int | None` (index), `ay: int | None`, `gun: int | None` (`(ay, gun)` bileşik index), `gorev: str | None`, `kategori: Kategori`, `kurum: str | None`, `memleket: str | None`, `baba_adi: str | None`, `dogum_yili: int | None`, `donem: str | None`, `durum: Durum` (index, varsayılan `onay_bekliyor`), `resmi_teyit: bool = False`, `isimsiz: bool = False`, `kaynak_kodu: str` (index; ör. `haber`, `egm`, `kahramanlar`, `sehitlerimiz`, `ornek`), `slug: str`, `arama_metni: str` (index), `olusturma`, `guncelleme` (UTC datetime). İlişki: `kaynaklar: list[Kaynak]` (cascade delete-orphan). Özellikler: `gorunen_ad -> str` (`text.gorunen_ad`), `url -> str` (`f"/sehit/{slug}-{id}"`).
    - `Sehit.alanlari_yenile(self) -> None`: `ad/lakap ← ad_duzenle`, `soyad ← soyad_duzenle` (boşsa `None`); `slug ← slug(gorunen_ad)`; `arama_metni ← katla(" ".join([ad, soyad, lakap, memleket, gorev, kurum] dolu olanlar))`; `tam` ise `yil/ay/gun ← sehadet_tarihi`; `yil` ise `ay = gun = sehadet_tarihi = None`; `bilinmiyor` ise dördü de `None`.
    - `class Kaynak(Base)` (`kaynaklar`): `id`, `sehit_id` FK, `url: str | None`, `baslik: str | None`, `metin: str | None`, `kaynak_adi: str`, `eklenme`.
    - `class Bildirim(Base)` (`bildirimler`): `id`, `sehit_id: int | None` FK, `mesaj: str`, `iletisim: str | None`, `kapandi: bool = False`, `tarih`.
  - `tests/conftest.py`: fikstürler `session` (SQLite `sqlite://` + `StaticPool`, `Base.metadata.create_all`), `sehit_ekle(**alanlar) -> Sehit` fabrikası (varsayılanlar: `ad="Ahmet"`, `soyad="Yılmaz"`, `kategori="asker"`, `kaynak_kodu="test"`, `durum="yayinda"`, `tarih_hassasiyeti="tam"`, `sehadet_tarihi=date(2016, 10, 23)`; `alanlari_yenile()` çağırıp commit eder).

- [ ] **Step 1: Başarısız testleri yaz** — `tests/test_dates.py`, `tests/test_models.py`

```python
# tests/test_dates.py
from datetime import datetime, timezone, date
from app.dates import bugun

def test_bugun_istanbul_gece_yarisi():
    # UTC 22 Ekim 21:30 = İstanbul 23 Ekim 00:30
    assert bugun(datetime(2026, 10, 22, 21, 30, tzinfo=timezone.utc)) == date(2026, 10, 23)

def test_bugun_parametresiz_tarih_doner():
    assert isinstance(bugun(), date)
```

```python
# tests/test_models.py
from datetime import date

def test_alanlari_yenile_tam_tarih(sehit_ekle):
    s = sehit_ekle(ad="AHMET LÜTFİ", soyad="şimşek", memleket="Sivas", sehadet_tarihi=date(2011, 10, 23))
    assert (s.ad, s.soyad) == ("Ahmet Lütfi", "ŞİMŞEK")
    assert (s.yil, s.ay, s.gun) == (2011, 10, 23)
    assert s.slug == "ahmet-lutfi-simsek"
    assert "simsek" in s.arama_metni and "sivas" in s.arama_metni
    assert s.url == f"/sehit/ahmet-lutfi-simsek-{s.id}"

def test_alanlari_yenile_sadece_yil(sehit_ekle):
    s = sehit_ekle(tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=1915)
    assert (s.yil, s.ay, s.gun, s.sehadet_tarihi) == (1915, None, None, None)

def test_soyadsiz_lakapli(sehit_ekle):
    s = sehit_ekle(ad="İSMAİL", soyad=None, lakap="AŞÇIOĞULLARINDAN", tarih_hassasiyeti="bilinmiyor", sehadet_tarihi=None)
    assert s.gorunen_ad == "İsmail — Aşçıoğullarından"
    assert s.yil is None
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_dates.py tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: `app/config.py`, `app/db.py`, `app/dates.py`, `app/models.py`, `tests/conftest.py`'yi Interfaces'teki imzalarla yaz**

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/Scripts/python -m pytest -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "feat: ayarlar, veritabanı modelleri ve İstanbul saatine göre bugün"
```

---

### Task 3: Sorgu ve yazma fonksiyonları (`repo.py`)

**Files:**
- Create: `app/schemas.py` (yalnızca `SehitVeri`), `app/repo.py`, `tests/test_repo.py`

**Interfaces:**
- Consumes: Task 2 modelleri, `app.text.katla`, `app.config.get_settings`
- Produces:
  - `app/schemas.py`: `class SehitVeri(BaseModel)` — düzenlenebilir alanlar: `ad`, `soyad`, `lakap`, `tarih_hassasiyeti`, `sehadet_tarihi`, `yil`, `gorev`, `kategori`, `kurum`, `memleket`, `baba_adi`, `dogum_yili`, `donem`, `resmi_teyit`, `isimsiz`, `kaynak_kodu`. `model_validator`: `tam` ise `sehadet_tarihi` zorunlu; `yil` ise `yil` zorunlu; aksi halde `ValueError("...")`.
  - `app/repo.py`:
    - `YilFiltre = int | Literal["2000-oncesi"] | None`
    - `@dataclass Istatistik(toplam: int, bu_yil: int, yil: int)`
    - `@dataclass Sayfa(toplam: int, kayitlar: list[Sehit])`
    - `istatistik(s: Session, bugun: date, *, api: bool = False) -> Istatistik`
    - `listele(s: Session, *, yil: YilFiltre = None, q: str | None = None, sayfa: int = 1, adet: int = 25, api: bool = False) -> Sayfa` — sıralama: `yil DESC NULLS LAST, ay DESC, gun DESC, id DESC` (SQLite ve PostgreSQL'de aynı sonucu vermesi için `yil IS NULL` ifadesiyle önce sırala). `"2000-oncesi"` = `yil < 2000 OR yil IS NULL`. `q` → `arama_metni LIKE %katla(q)%` (her kelime ayrı ayrı AND).
    - `yil_donumu(s: Session, ay: int, gun: int, *, artik_yil: bool, api: bool = False) -> list[Sehit]` — `tam` + `yil >= 2000` + eşleşme; `(ay, gun) == (2, 28) and not artik_yil` ise 29 Şubat'ı da kat. Sıralama: `yil DESC, id`.
    - `getir(s: Session, sehit_id: int, *, sadece_yayinda: bool = True, api: bool = False) -> Sehit | None`
    - `yeni_sehit(s: Session, veri: SehitVeri, *, durum: Durum = Durum.onay_bekliyor) -> Sehit`
    - `sehit_guncelle(s: Session, sehit: Sehit, veri: SehitVeri) -> Sehit`
    - `durum_degistir(s: Session, sehit: Sehit, durum: Durum) -> None`
    - `birlestir(s: Session, hedef: Sehit, fazla: Sehit) -> Sehit` — `fazla`nın kaynakları `hedef`e taşınır; `hedef`te boş olan alanlar `fazla`dan doldurulur; `fazla` silinir.
    - `bildirim_ekle(s: Session, *, mesaj: str, iletisim: str | None, sehit_id: int | None) -> Bildirim`
    - Ortak kural: her okuma fonksiyonu `durum == yayinda` filtreler (`getir(sadece_yayinda=False)` hariç); `api=True` ise `kaynak_kodu NOT IN settings.api_haric_kaynaklar`. Her yazma `alanlari_yenile()` çağırır ve commit eder.

- [ ] **Step 1: Başarısız testleri yaz** — `tests/test_repo.py`

```python
from datetime import date
from app import repo
from app.models import Durum

def test_istatistik_sadece_yayinda(session, sehit_ekle):
    sehit_ekle(sehadet_tarihi=date(2026, 3, 1))
    sehit_ekle(sehadet_tarihi=date(2016, 3, 1))
    sehit_ekle(sehadet_tarihi=date(2026, 4, 1), durum="onay_bekliyor")
    sehit_ekle(sehadet_tarihi=date(2026, 4, 2), durum="reddedildi")
    assert repo.istatistik(session, date(2026, 10, 23)) == repo.Istatistik(toplam=2, bu_yil=1, yil=2026)

def test_listele_siralama_ve_tarihsizler_sonda(session, sehit_ekle):
    a = sehit_ekle(sehadet_tarihi=date(2011, 1, 1))
    b = sehit_ekle(tarih_hassasiyeti="bilinmiyor", sehadet_tarihi=None)
    c = sehit_ekle(sehadet_tarihi=date(2016, 5, 5))
    d = sehit_ekle(tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=1915)
    assert [x.id for x in repo.listele(session).kayitlar] == [c.id, a.id, d.id, b.id]

def test_listele_2000_oncesi_tarihsizleri_icerir(session, sehit_ekle):
    sehit_ekle(sehadet_tarihi=date(2011, 1, 1))
    eski = sehit_ekle(tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=1915)
    bilinmeyen = sehit_ekle(tarih_hassasiyeti="bilinmiyor", sehadet_tarihi=None)
    ids = {x.id for x in repo.listele(session, yil="2000-oncesi").kayitlar}
    assert ids == {eski.id, bilinmeyen.id}

def test_listele_turkce_arama(session, sehit_ekle):
    s = sehit_ekle(ad="Ömer", soyad="Şahin", memleket="Muş")
    sehit_ekle(ad="Ali", soyad="Kaya")
    for q in ["sahin", "ŞAHİN", "Şahin", "omer sahin", "mus"]:
        assert [x.id for x in repo.listele(session, q=q).kayitlar] == [s.id], q

def test_listele_sayfalama(session, sehit_ekle):
    for i in range(30):
        sehit_ekle(sehadet_tarihi=date(2016, 1, 1))
    s2 = repo.listele(session, sayfa=2, adet=25)
    assert s2.toplam == 30 and len(s2.kayitlar) == 5
    assert repo.listele(session, sayfa=99).kayitlar == []

def test_yil_donumu_kurallari(session, sehit_ekle):
    ok = sehit_ekle(sehadet_tarihi=date(2011, 10, 23))
    sehit_ekle(sehadet_tarihi=date(1998, 10, 23))                       # 2000 öncesi
    sehit_ekle(tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=2011)  # tarih tam değil
    sehit_ekle(sehadet_tarihi=date(2016, 10, 23), durum="onay_bekliyor")
    assert [x.id for x in repo.yil_donumu(session, 10, 23, artik_yil=False)] == [ok.id]

def test_yil_donumu_29_subat(session, sehit_ekle):
    s = sehit_ekle(sehadet_tarihi=date(2016, 2, 29))
    assert [x.id for x in repo.yil_donumu(session, 2, 28, artik_yil=False)] == [s.id]
    assert repo.yil_donumu(session, 2, 28, artik_yil=True) == []

def test_api_haric_kaynak(session, sehit_ekle, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "api_haric_kaynaklar", ["sehitlerimiz"])
    gizli = sehit_ekle(kaynak_kodu="sehitlerimiz")
    acik = sehit_ekle(kaynak_kodu="egm")
    assert [x.id for x in repo.listele(session, api=True).kayitlar] == [acik.id]
    assert repo.getir(session, gizli.id, api=True) is None
    assert repo.getir(session, gizli.id) is not None  # sitede görünür

def test_getir_onay_bekleyen_sizmaz(session, sehit_ekle):
    s = sehit_ekle(durum="onay_bekliyor")
    assert repo.getir(session, s.id) is None
    assert repo.getir(session, s.id, sadece_yayinda=False).id == s.id

def test_birlestir(session, sehit_ekle):
    from app.models import Kaynak
    hedef = sehit_ekle(memleket=None)
    fazla = sehit_ekle(memleket="Van", durum="onay_bekliyor")
    fazla.kaynaklar.append(Kaynak(kaynak_adi="Hürriyet", url="https://x"))
    session.commit()
    sonuc = repo.birlestir(session, hedef, fazla)
    assert sonuc.memleket == "Van" and len(sonuc.kaynaklar) == 1
    assert repo.getir(session, fazla.id, sadece_yayinda=False) is None

def test_sehitveri_dogrulama():
    import pytest
    from app.schemas import SehitVeri
    with pytest.raises(ValueError):
        SehitVeri(ad="Ali", kategori="asker", kaynak_kodu="panel", tarih_hassasiyeti="tam", sehadet_tarihi=None)
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_repo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.repo'`

- [ ] **Step 3: `app/schemas.py` (`SehitVeri`) ve `app/repo.py`'yi Interfaces'teki imzalarla yaz**

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/Scripts/python -m pytest -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "feat: şehit sorguları, yıl dönümü, Türkçe arama ve birleştirme"
```

---

### Task 4: Herkese açık JSON API

**Files:**
- Create: `app/api.py`, `app/main.py`, `tests/test_api.py`
- Modify: `app/schemas.py` (yanıt modelleri), `tests/conftest.py` (`client` fikstürü)

**Interfaces:**
- Consumes: `repo.istatistik`, `repo.listele`, `repo.yil_donumu`, `repo.getir`, `dates.bugun`
- Produces:
  - `app/main.py`: `create_app(settings: Settings | None = None) -> FastAPI` — motoru ve `app.state.session_factory`'yi kurar, `SessionMiddleware(secret_key)` ekler, `/static` bağlar, slowapi sınırlayıcıyı (`app.state.limiter`, anahtar: istemci IP'si) kurar, `api`, `site`, `admin` yönlendiricilerini ekler (site/admin sonraki görevlerde). FastAPI belgeleri `docs_url="/api/belgeler"`, `openapi_url="/api/openapi.json"`. Modül sonunda `app = create_app()`.
  - `tests/conftest.py`: `client` fikstürü — `create_app()` + `get_session` bağımlılığını test `session`ına yönlendirir, `TestClient` döndürür.
  - Yanıt şekilleri (`app/schemas.py`):
    - `SehitOzet`: `id, ad, soyad, lakap, gorunen_ad, sehadet_yili, sehadet_tarihi, tarih_hassasiyeti, gorev, kategori, memleket, url`
    - `SehitDetay(SehitOzet)`: `+ kurum, baba_adi, dogum_yili, donem, kaynaklar: list[{kaynak_adi, url}]`
    - `IstatistikYanit`: `toplam, bu_yil, yil`
    - `ListeYanit`: `toplam, sayfa, adet, kayitlar: list[SehitOzet]`
    - `BugunYanit`: `tarih: "AA-GG"`, `kayitlar: list[SehitOzet + yil_donumu: int]`
  - Uç noktalar (`app/api.py`, `APIRouter(prefix="/api")`, hepsi `api=True` ile çağırır, hepsi `settings.istek_siniri` ile sınırlı):
    - `GET /api/istatistik`
    - `GET /api/sehitler?yil=&q=&sayfa=1&adet=25` — `yil`: tamsayı veya `2000-oncesi`, başka değer 422; `sayfa >= 1`; `1 <= adet <= 100`
    - `GET /api/sehitler/{id}` — yoksa/yayında değilse 404
    - `GET /api/bugun?tarih=AA-GG` — `tarih` yoksa `bugun()`; biçim `^\d{2}-\d{2}$` ve geçerli gün/ay değilse 422 (29 Şubat geçerli); `yil_donumu = bugunun_yili - kayit.yil`; `artik_yil` bugünün yılından hesaplanır.

- [ ] **Step 1: Başarısız testleri yaz** — `tests/test_api.py`

```python
from datetime import date

def test_istatistik(client, sehit_ekle, monkeypatch):
    monkeypatch.setattr("app.api.bugun", lambda: date(2026, 10, 23))
    sehit_ekle(sehadet_tarihi=date(2026, 3, 1)); sehit_ekle(sehadet_tarihi=date(2011, 3, 1))
    assert client.get("/api/istatistik").json() == {"toplam": 2, "bu_yil": 1, "yil": 2026}

def test_sehitler_listesi_alanlari(client, sehit_ekle):
    s = sehit_ekle(ad="Ömer", soyad="Şahin", sehadet_tarihi=date(2016, 7, 15))
    j = client.get("/api/sehitler", params={"yil": 2016}).json()
    assert j["toplam"] == 1 and j["sayfa"] == 1 and j["adet"] == 25
    k = j["kayitlar"][0]
    assert (k["ad"], k["soyad"], k["sehadet_yili"], k["gorunen_ad"]) == ("Ömer", "ŞAHİN", 2016, "Ömer ŞAHİN")
    assert k["url"] == s.url

def test_sehitler_gecersiz_parametreler(client):
    assert client.get("/api/sehitler", params={"adet": 101}).status_code == 422
    assert client.get("/api/sehitler", params={"sayfa": 0}).status_code == 422
    assert client.get("/api/sehitler", params={"yil": "dun"}).status_code == 422
    assert client.get("/api/sehitler", params={"yil": "2000-oncesi"}).status_code == 200

def test_detay_onay_bekleyen_404(client, sehit_ekle):
    s = sehit_ekle(durum="onay_bekliyor")
    assert client.get(f"/api/sehitler/{s.id}").status_code == 404

def test_bugun(client, sehit_ekle, monkeypatch):
    monkeypatch.setattr("app.api.bugun", lambda: date(2026, 10, 23))
    sehit_ekle(sehadet_tarihi=date(2011, 10, 23))
    j = client.get("/api/bugun").json()
    assert j["tarih"] == "10-23" and j["kayitlar"][0]["yil_donumu"] == 15
    assert client.get("/api/bugun", params={"tarih": "13-40"}).status_code == 422
    assert client.get("/api/bugun", params={"tarih": "02-29"}).status_code == 200
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api'`

- [ ] **Step 3: `app/schemas.py` yanıt modellerini, `app/api.py`'yi, `app/main.py`'yi ve `client` fikstürünü yaz**

`app/api.py` içinde `from app.dates import bugun` (test bunu `app.api.bugun` üzerinden değiştirir).

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/Scripts/python -m pytest -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "feat: herkese açık JSON API (istatistik, liste, detay, bugün)"
```

---

### Task 5: Herkese açık ana sayfa (B teması + "Bugün" kutusu)

**Files:**
- Create: `app/site.py`, `app/templates/base.html`, `app/templates/index.html`, `app/templates/_bugun.html`, `app/templates/_tablo.html`, `app/static/site.css`, `app/static/site.js`, `tests/test_site.py`
- Modify: `app/main.py` (site yönlendiricisini ekle)

**Interfaces:**
- Consumes: `repo.istatistik`, `repo.listele`, `repo.yil_donumu`, `dates.bugun`
- Produces:
  - `app/site.py`: `router = APIRouter()`; `templates = Jinja2Templates("app/templates")`; `GET /` parametreleri `yil` (tamsayı, `2000-oncesi` veya `tumu`; varsayılan bugünün yılı), `q`, `sayfa` (varsayılan 1). Geçersiz `yil`/`sayfa` 422 değil, varsayılana düşer (insan ziyaretçi için). Şablona: `bugun_tarihi`, `bugun_kayitlari` (yıl dönümü sayısıyla), `istatistik`, `yillar` (bugünün yılından 2000'e azalan + `2000 öncesi` + `Tümü`), `secili_yil`, `q`, `sayfa_sonucu`, `sayfa_sayisi`.
  - `base.html`: üst menü (logo `VATAN<b>SAĞOLSUN</b>`, Ara → `/#ara`, Yıl Dönümleri → `/yil-donumleri`, Hakkında → `/hakkinda`, API → `/api/belgeler`), alt bilgi (spec 4.6 madde 7 metinleri; API adresleri; "Hatalı kayıt bildir" → `/bildir`; "Buradaki sayılar arşivimizdeki kayıt sayısıdır, resmî toplam değildir."), Google Fonts (Cormorant Garamond 500/600, Inter 400/500/600).
  - `site.css`: mockup'taki `:root` renkleri ve B görünümü sınıfları (`.hero`, `.stats`, `.years`, `.tools`, `.search`, `table`, `.tag`, `.r-asker` … `.r-diger`, `.pager`, `.today`, `.today-grid`, `.tcard`, `footer`, `.modal-bg`, `.modal`) + özel kaydırma çubuğu:

```css
* { scrollbar-color: #3a3f48 var(--bg); scrollbar-width: thin; }
::-webkit-scrollbar { width: 10px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: #3a3f48; border-radius: 8px; border: 2px solid var(--bg); }
::-webkit-scrollbar-thumb:hover { background: var(--red); }
```
    (Firefox tutamaç üzerine gelme rengini desteklemez; orada ince koyu çubuk yeterli.)
  - `site.js`: (1) `[data-hedef]` sayaçları 1,4 sn ease-out ile sıfırdan sayar, `tr-TR` biçimi; (2) `tr[data-id]` ve `.tcard[data-id]` tıklanınca `/api/sehitler/{id}` çekip modalı doldurur (Ad SOYAD, görev, Şehadet Tarihi, Memleket, Baba Adı, Kurum, kaynak linkleri, "Mekânı cennet olsun." ve "Kayıt sayfası" linki); Esc ve dış tık kapatır.
  - Yerleşim (yukarıdan aşağı): `_bugun.html` (kayıt yoksa hiç çizilmez) → sayaç (`Toplam Şehit`, `{yil} Yılında`) → yıl seçici (linkler `/?yil=...`) → `<form id="ara">` arama + "{yil} yılında N şehit" satırı → `_tablo.html` (Ad Soyad, Şehadet Tarihi, Görev etiketi, Memleket `.h-m`, Kurum `.h-m`; tarih `tam` ise `GG.AA.YYYY`, `yil` ise `YYYY`, `bilinmiyor` ise boş) → sayfalama (ilk 3, son 2, seçilinin ±1, arada `…`; mevcut `yil`/`q` korunur).

- [ ] **Step 1: Başarısız testleri yaz** — `tests/test_site.py`

```python
from datetime import date

def _sabit_gun(monkeypatch):
    monkeypatch.setattr("app.site.bugun", lambda: date(2026, 10, 23))

def test_ana_sayfa_bugun_kutusu_ve_sayac(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    sehit_ekle(ad="Hasan", soyad="Tekin", sehadet_tarihi=date(2011, 10, 23))
    h = client.get("/").text
    assert "Bugün, 23 Ekim" in h and "Hasan TEKİN" in h and "15. yıl dönümü" in h
    assert 'data-hedef="1"' in h  # toplam sayaç
    assert h.index("Bugün, 23 Ekim") < h.index("Toplam Şehit")

def test_bugun_kutusu_bossa_gizli(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    sehit_ekle(sehadet_tarihi=date(2011, 5, 5))
    assert "Bugün, 23 Ekim" not in client.get("/").text

def test_tablo_varsayilan_bu_yil_ve_arama(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    sehit_ekle(ad="Ali", soyad="Kaya", sehadet_tarihi=date(2026, 2, 2))
    sehit_ekle(ad="Veli", soyad="Şahin", sehadet_tarihi=date(2016, 2, 2))
    h = client.get("/").text
    assert "Ali KAYA" in h and "Veli ŞAHİN" not in h
    h = client.get("/", params={"yil": "tumu", "q": "sahin"}).text
    assert "Veli ŞAHİN" in h and "Ali KAYA" not in h

def test_eski_kayitlar_ciziliyor(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    sehit_ekle(ad="İsmail", soyad=None, lakap="Aşçıoğullarından", tarih_hassasiyeti="bilinmiyor", sehadet_tarihi=None)
    sehit_ekle(ad="Mehmet", soyad=None, tarih_hassasiyeti="yil", sehadet_tarihi=None, yil=1915)
    r = client.get("/", params={"yil": "2000-oncesi"})
    assert r.status_code == 200
    assert "İsmail — Aşçıoğullarından" in r.text and "1915" in r.text

def test_onay_bekleyen_sayfada_yok(client, sehit_ekle, monkeypatch):
    _sabit_gun(monkeypatch)
    sehit_ekle(ad="Gizli", soyad="Kayit", sehadet_tarihi=date(2026, 10, 23), durum="onay_bekliyor")
    assert "Gizli" not in client.get("/").text

def test_gecersiz_parametre_varsayilana_duser(client, monkeypatch):
    _sabit_gun(monkeypatch)
    assert client.get("/", params={"yil": "abc", "sayfa": "-3"}).status_code == 200

def test_ozel_kaydirma_cubugu_css(client):
    css = client.get("/static/site.css").text
    assert "::-webkit-scrollbar-thumb:hover" in css and "scrollbar-color" in css
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_site.py -v`
Expected: FAIL — `/` 404 döner

- [ ] **Step 3: `app/site.py`, şablonları, `site.css`, `site.js`'yi yaz; `main.py`'ye yönlendiriciyi ekle**

Görünümü `docs/superpowers/specs/mockups/ana-sayfa-b.html`'den al (CSS'i oradan taşı; JS'teki örnek veri üretimi ve tema geçiş çubuğu alınmaz). Ay adları: Ocak … Aralık.

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/Scripts/python -m pytest -v`
Expected: tümü PASS

(Gözle kontrol — mockup'la masaüstü ve 375px karşılaştırması — örnek veri komutu hazır olunca Task 10 Step 2'de yapılır.)

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "feat: herkese açık ana sayfa (bugün kutusu, sayaç, yıl seçici, tablo)"
```

---

### Task 6: Diğer herkese açık sayfalar (şehit, yıl dönümleri, hakkında, bildir)

**Files:**
- Create: `app/templates/sehit.html`, `app/templates/yil_donumleri.html`, `app/templates/hakkinda.html`, `app/templates/bildir.html`
- Modify: `app/site.py`, `tests/test_site.py`

**Interfaces:**
- Consumes: `repo.getir`, `repo.yil_donumu`, `repo.bildirim_ekle`
- Produces (rotalar):
  - `GET /sehit/{slug_id}` — `slug_id` son `-`'den sonrası tamsayı id; kayıt yoksa/yayında değilse 404; slug eşleşmiyorsa doğru `url`'e 301. Sayfa: görünen ad, görev, tüm alanlar, kaynak linkleri, `<title>{gorunen_ad} — vatansagolsun</title>`, `<meta name="description">`.
  - `GET /yil-donumleri?ay=&gun=` — varsayılan bugün; ay (1–12) ve gün seçici formu; sonuçlar `_bugun.html` kart düzeninde; geçersiz değer → bugün.
  - `GET /hakkinda` — amaç, veri kaynakları (resmî kurumlar, sehitlerimiz.org.tr — "sehitlerimiz.org.tr — Türkiye Şehit Arşivi" atfıyla, kahramanlar.org.tr), doğrulama süreci, "kayıt sayısı resmî toplam değildir".
  - `GET /bildir?sehit=<id>` formu (mesaj zorunlu, ≤2000 karakter; iletişim isteğe bağlı) ve `POST /bildir` → `repo.bildirim_ekle` → "Teşekkürler, bildiriminiz incelenecek." sayfası. Boş mesaj → form hata mesajıyla tekrar.

- [ ] **Step 1: Başarısız testleri ekle** — `tests/test_site.py`

```python
def test_sehit_sayfasi_ve_yonlendirme(client, sehit_ekle):
    s = sehit_ekle(ad="Hasan", soyad="Tekin")
    r = client.get(s.url)
    assert r.status_code == 200 and "<title>Hasan TEKİN — vatansagolsun</title>" in r.text
    r = client.get(f"/sehit/yanlis-{s.id}", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == s.url

def test_sehit_sayfasi_onay_bekleyen_404(client, sehit_ekle):
    s = sehit_ekle(durum="onay_bekliyor")
    assert client.get(f"/sehit/x-{s.id}").status_code == 404
    assert client.get("/sehit/abc").status_code == 404

def test_yil_donumleri_sayfasi(client, sehit_ekle):
    sehit_ekle(ad="Cem", soyad="Uçar", sehadet_tarihi=date(2016, 7, 15))
    assert "Cem UÇAR" in client.get("/yil-donumleri", params={"ay": 7, "gun": 15}).text
    assert client.get("/yil-donumleri", params={"ay": 13, "gun": 99}).status_code == 200

def test_bildir(client, session):
    from app.models import Bildirim
    r = client.post("/bildir", data={"mesaj": "Tarih yanlış", "iletisim": ""})
    assert "Teşekkürler" in r.text
    assert session.query(Bildirim).one().mesaj == "Tarih yanlış"
    assert "Teşekkürler" not in client.post("/bildir", data={"mesaj": "  "}).text
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_site.py -v`
Expected: yeni testler FAIL (404)

- [ ] **Step 3: Rotaları ve şablonları yaz**

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/Scripts/python -m pytest -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "feat: şehit sayfası, yıl dönümleri, hakkında ve hatalı kayıt bildirimi"
```

---

### Task 7: Panel girişi (kimlik doğrulama, CSRF, şifre aracı)

**Files:**
- Create: `app/admin.py`, `app/cli.py`, `app/templates/panel/base.html`, `app/templates/panel/giris.html`, `app/static/panel.css`, `tests/test_admin.py`
- Modify: `app/main.py`, `tests/conftest.py` (`panel_client` fikstürü)

**Interfaces:**
- Produces:
  - `app/admin.py`: `router = APIRouter(prefix="/panel")`; `sifre_hashle(sifre: str) -> str` ve `sifre_dogru(sifre: str, hash_: str) -> bool` (bcrypt); bağımlılık `yonetici_gerekli(request) -> str` — oturumda `kullanici` yoksa `/panel/giris`'e 303 yönlendirme (bir `HTTPException` alt sınıfı + istisna işleyicisiyle); `csrf_token(request) -> str` (oturumda yoksa `secrets.token_urlsafe` üretir) ve `csrf_dogrula(request, token: str) -> None` (uyuşmazsa 403). Tüm panel POST formları gizli `csrf` alanı taşır.
  - Rotalar: `GET /panel/giris`, `POST /panel/giris` (CSRF istemez — oturum çerezi `SameSite=Lax`; yanlışsa "Kullanıcı adı veya şifre hatalı", 401; `admin_sifre_hash` boşsa giriş her zaman reddedilir; başarılıysa oturumu yeniler ve `/panel`'e 303), `POST /panel/cikis`, `GET /panel` (Task 8 içeriği; şimdilik boş liste sayfası).
  - Basit kaba kuvvet koruması: aynı IP'den dakikada 10'dan fazla hatalı giriş → 429 (slowapi ile `POST /panel/giris`'e `10/minute`).
  - `app/cli.py`: `python -m app.cli sifre-olustur` — şifreyi iki kez sorar (`getpass`), `.env`'e yazılacak `ADMIN_SIFRE_HASH=...` satırını basar.
  - `tests/conftest.py` fikstürleri: `ayarli_sifre` — ayarlara `admin_sifre_hash = sifre_hashle("test-sifre")` koyar; `panel_client` — `ayarli_sifre` kullanır, `admin`/`test-sifre` ile giriş yapmış `TestClient` (aynı test `session`ına bağlı); `csrf` — `Callable[[TestClient], str]` döndürür: `GET /panel` sayfasındaki `name="csrf"` gizli alanının değerini okur.

- [ ] **Step 1: Başarısız testleri yaz** — `tests/test_admin.py`

```python
def test_panel_girissiz_yonlendirir(client):
    r = client.get("/panel", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel/giris"

def test_yanlis_sifre(client, ayarli_sifre):
    r = client.post("/panel/giris", data={"kullanici": "admin", "sifre": "yanlis"})
    assert r.status_code == 401 and "hatalı" in r.text

def test_dogru_giris_ve_cikis(panel_client, csrf):
    assert panel_client.get("/panel").status_code == 200
    panel_client.post("/panel/cikis", data={"csrf": csrf(panel_client)})
    assert panel_client.get("/panel", follow_redirects=False).status_code == 303

def test_csrf_yoksa_403(panel_client):
    assert panel_client.post("/panel/cikis", data={"csrf": "sahte"}).status_code == 403

def test_bos_hash_ile_giris_kapali(client):
    r = client.post("/panel/giris", data={"kullanici": "admin", "sifre": ""})
    assert r.status_code == 401
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_admin.py -v`
Expected: FAIL — `/panel` 404

- [ ] **Step 3: `app/admin.py`, `app/cli.py`, şablonları ve fikstürleri yaz; yönlendiriciyi `main.py`'ye ekle**

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/Scripts/python -m pytest -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "feat: panel girişi, CSRF koruması ve şifre oluşturma aracı"
```

---

### Task 8: Onay iş akışı (bekleyenler, düzenle, onayla, reddet, kaldır)

**Files:**
- Create: `app/templates/panel/liste.html`, `app/templates/panel/duzenle.html`
- Modify: `app/admin.py`, `tests/test_admin.py`

**Interfaces:**
- Consumes: `repo.getir(sadece_yayinda=False)`, `repo.yeni_sehit`, `repo.sehit_guncelle`, `repo.durum_degistir`, `SehitVeri`
- Produces (rotalar, hepsi `yonetici_gerekli`, POST'lar `csrf_dogrula`):
  - `GET /panel` — "Onay bekleyenler": `durum == onay_bekliyor`, en yeni önce; her satırda görünen ad, tarih, görev, kategori, memleket, `isimsiz` ve `resmi_teyit == False` için uyarı rozetleri ("İsimsiz", "Resmî teyit yok"), kaynakların adı + linki + metninin ilk 300 karakteri. Üstte sayılar: bekleyen / yeni bildirim.
  - `GET /panel/yayinda?q=` — yayındaki kayıtları `repo.listele` mantığıyla arar (50'şer).
  - `GET /panel/sehit/yeni`, `GET /panel/sehit/{id}` — düzenleme formu (`SehitVeri` alanları; kategori ve hassasiyet açılır liste).
  - `POST /panel/sehit/yeni` → `yeni_sehit(..., durum=onay_bekliyor)`; `kaynak_kodu="panel"`.
  - `POST /panel/sehit/{id}` → `sehit_guncelle` → aynı düzenleme sayfasına 303; doğrulama hatası formu Türkçe hata mesajıyla geri çizer (400).
  - `POST /panel/sehit/{id}/onayla` → `yayinda`; `/reddet` → `reddedildi`; `/kaldir` (yayındaki kaydı yayından kaldırır) → `reddedildi`. Hepsi `/panel`'e 303.
  - Formdaki "Kaydet ve onayla" düğmesi: güncelle + onayla tek adımda.

- [ ] **Step 1: Başarısız testleri ekle** — `tests/test_admin.py`

```python
from datetime import date

def test_bekleyenler_listesi(panel_client, sehit_ekle):
    sehit_ekle(ad="Bekleyen", soyad="Kişi", durum="onay_bekliyor", resmi_teyit=False, isimsiz=False)
    sehit_ekle(ad="Yayinda", soyad="Kişi")
    h = panel_client.get("/panel").text
    assert "Bekleyen KİŞİ" in h and "Resmî teyit yok" in h and "Yayinda KİŞİ" not in h

def test_onayla_yayina_alir(panel_client, csrf, sehit_ekle, client):
    s = sehit_ekle(durum="onay_bekliyor", sehadet_tarihi=date(2016, 1, 1))
    panel_client.post(f"/panel/sehit/{s.id}/onayla", data={"csrf": csrf(panel_client)})
    assert client.get(f"/api/sehitler/{s.id}").status_code == 200

def test_reddet_ve_kaldir(panel_client, csrf, sehit_ekle, client):
    a = sehit_ekle(durum="onay_bekliyor"); b = sehit_ekle()
    panel_client.post(f"/panel/sehit/{a.id}/reddet", data={"csrf": csrf(panel_client)})
    panel_client.post(f"/panel/sehit/{b.id}/kaldir", data={"csrf": csrf(panel_client)})
    assert client.get(f"/api/sehitler/{b.id}").status_code == 404

def test_duzenle_ve_hata(panel_client, csrf, sehit_ekle, session):
    s = sehit_ekle(durum="onay_bekliyor")
    form = {"csrf": csrf(panel_client), "ad": "mehmet", "soyad": "kaya", "kategori": "polis",
            "tarih_hassasiyeti": "tam", "sehadet_tarihi": "2026-10-20", "kaynak_kodu": "haber"}
    r = panel_client.post(f"/panel/sehit/{s.id}", data=form, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/panel/sehit/{s.id}"
    session.refresh(s)
    assert (s.ad, s.soyad, s.kategori, s.gun) == ("Mehmet", "KAYA", "polis", 20)
    form["sehadet_tarihi"] = ""
    assert panel_client.post(f"/panel/sehit/{s.id}", data=form).status_code == 400
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_admin.py -v`
Expected: yeni testler FAIL

- [ ] **Step 3: Rotaları ve şablonları yaz**

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/Scripts/python -m pytest -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "feat: onay paneli — bekleyenler, düzenleme, onay/ret/kaldırma"
```

---

### Task 9: Birleştirme ve bildirimler

**Files:**
- Create: `app/templates/panel/bildirimler.html`
- Modify: `app/admin.py`, `app/templates/panel/duzenle.html`, `tests/test_admin.py`

**Interfaces:**
- Consumes: `repo.birlestir`, `Bildirim`
- Produces:
  - Düzenleme sayfasında "Başka bir kayıtla birleştir" formu: hedef kayıt id'si girilir → `POST /panel/sehit/{id}/birlestir` (`hedef_id`) → `repo.birlestir(hedef, fazla=bu kayıt)` → hedefin düzenleme sayfasına 303. Hedef yoksa ya da kendisiyse 400.
  - `GET /panel/bildirimler` — açık bildirimler en yeni önce; ilgili şehit varsa linki; `POST /panel/bildirimler/{id}/kapat`.

- [ ] **Step 1: Başarısız testleri ekle** — `tests/test_admin.py`

```python
def test_birlestir_rotasi(panel_client, csrf, sehit_ekle, session):
    hedef = sehit_ekle(memleket=None); fazla = sehit_ekle(memleket="Van", durum="onay_bekliyor")
    r = panel_client.post(f"/panel/sehit/{fazla.id}/birlestir",
                          data={"csrf": csrf(panel_client), "hedef_id": hedef.id}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/panel/sehit/{hedef.id}"
    session.refresh(hedef)
    assert hedef.memleket == "Van"
    assert panel_client.post(f"/panel/sehit/{hedef.id}/birlestir",
                             data={"csrf": csrf(panel_client), "hedef_id": hedef.id}).status_code == 400

def test_bildirimler(panel_client, csrf, client, session):
    from app.models import Bildirim
    client.post("/bildir", data={"mesaj": "İsim yanlış yazılmış"})
    assert "İsim yanlış yazılmış" in panel_client.get("/panel/bildirimler").text
    b = session.query(Bildirim).one()
    panel_client.post(f"/panel/bildirimler/{b.id}/kapat", data={"csrf": csrf(panel_client)})
    assert "İsim yanlış yazılmış" not in panel_client.get("/panel/bildirimler").text
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/Scripts/python -m pytest tests/test_admin.py -v`
Expected: yeni testler FAIL

- [ ] **Step 3: Rotaları ve şablonları yaz**

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/Scripts/python -m pytest -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "feat: panelde kayıt birleştirme ve hatalı kayıt bildirimleri"
```

---

### Task 10: Şema taşıma, örnek veri, Docker ve kurulum belgesi

**Files:**
- Create: `alembic.ini`, `migrations/env.py`, `migrations/versions/0001_ilk_sema.py`, `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `.env.example`, `README.md`
- Modify: `app/cli.py`, `.gitignore`

**Interfaces:**
- Consumes: `Base.metadata`, `get_settings().database_url`
- Produces:
  - Alembic: `migrations/env.py` URL'yi `get_settings()`'ten alır; `0001_ilk_sema` üç tabloyu ve index'leri oluşturur (`alembic revision --autogenerate` ile üretip gözden geçir).
  - `python -m app.cli ornek-veri` — 2000–bugün arası ~300 yayında + 5 onay bekleyen + 20 eski (yıl/bilinmiyor) örnek kayıt, `kaynak_kodu="ornek"`; aynı komutun `--sil` seçeneği `kaynak_kodu="ornek"` kayıtları siler. Komut, `database_url` `postgresql` ile başlıyorsa ve `--eminim` verilmemişse çalışmayı reddeder (üretime örnek veri karışmasın).
  - `Dockerfile`: `python:3.12-slim`, `pip install .`, başlangıçta `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"`.
  - `docker-compose.yml`: `db` (`postgres:16`, kalıcı volume, sağlık kontrolü), `app` (`.env`, `DATABASE_URL=postgresql+psycopg://...@db/vatansagolsun`, `db` sağlıklı olunca başlar), `caddy` (`caddy:2`, 80/443, `Caddyfile`, sertifika volume'u). İstek sınırının gerçek IP'yi görmesi için uvicorn proxy başlıkları açık.
  - `Caddyfile`: `{$ALAN_ADI} { reverse_proxy app:8000 }`.
  - `.env.example`: `ALAN_ADI`, `SECRET_KEY`, `ADMIN_KULLANICI`, `ADMIN_SIFRE_HASH`, `POSTGRES_PASSWORD`, `API_HARIC_KAYNAKLAR=[]`, `ISTEK_SINIRI=60/minute`, `SITE_URL`.
  - `README.md` (Türkçe, teknik bilgisi olmayan biri için): bilgisayarda çalıştırma; VPS kiralama (Hetzner örneği), alan adını sunucuya yönlendirme (A kaydı), sunucuya Docker kurma, projeyi kopyalama, `.env` doldurma (`SECRET_KEY` üretme komutu, `sifre-olustur`), `docker compose up -d`, panele giriş, güncelleme (`git pull && docker compose up -d --build`), yedek alma (`pg_dump` komutu).

- [ ] **Step 1: Alembic'i kur ve ilk taşımayı üret; SQLite'a karşı uygula**

Run: `.venv/Scripts/alembic upgrade head` (varsayılan `sqlite:///./yerel.db`)
Expected: hatasız; `yerel.db` içinde `sehitler`, `kaynaklar`, `bildirimler` tabloları

- [ ] **Step 2: `ornek-veri` komutunu yaz ve çalıştır**

Run: `.venv/Scripts/python -m app.cli ornek-veri && .venv/Scripts/uvicorn app.main:app`
Expected: `http://localhost:8000` sayaç, bugün kutusu ve tablo dolu; `/panel` girişe yönlendirir. Ana sayfayı masaüstü ve 375px genişlikte `docs/superpowers/specs/mockups/ana-sayfa-b.html` ile karşılaştır (Task 5'in gözle kontrolü).

- [ ] **Step 3: Docker dosyalarını yaz ve yerelde ayağa kaldır**

`.env`'i `.env.example`'dan oluştur (`ALAN_ADI=localhost`).
Run: `docker compose up -d --build` ardından `curl -sk https://localhost/api/istatistik`
Expected: `{"toplam":0,"bu_yil":0,"yil":2026}` (boş veritabanı)

- [ ] **Step 4: Tüm testleri çalıştır**

Run: `.venv/Scripts/python -m pytest -v`
Expected: tümü PASS

- [ ] **Step 5: `docker compose down` ile kapat, `README.md`'yi yaz, commit**

`.gitignore`'a `yerel.db` ekle.

```bash
git add .
git commit -m "feat: Alembic şeması, örnek veri, Docker kurulumu ve Türkçe kurulum belgesi"
```
