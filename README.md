# Vatan Sağ Olsun

Şehitlerimizi anan, herkesin görebileceği bir site ve açık (anahtarsız) bir API. Bu belge teknik bilgisi olmayan biri için yazıldı: komutları olduğu gibi kopyalayıp yapıştırmanız yeterli.

---

## 1. Kendi bilgisayarınızda denemek

Python 3.12 gerekir (https://www.python.org/downloads/).

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # Mac/Linux: .venv/bin/pip ...
.venv/Scripts/alembic upgrade head          # veritabanı tablolarını oluşturur
.venv/Scripts/python -m app.cli ornek-veri  # sahte örnek kayıtlar ekler
.venv/Scripts/uvicorn app.main:app
```

Tarayıcıda http://localhost:8000 adresini açın. Örnek kayıtları silmek için:
`.venv/Scripts/python -m app.cli ornek-veri --sil`

> Örnek veri gerçek değildir. Komut, gerçek (PostgreSQL) veritabanına yanlışlıkla örnek veri eklememeniz için `--eminim` yazmadıkça çalışmayı reddeder. Gerçek sitede bu komutu **kullanmayın**.

Yerelde yönetici paneli için `.env` dosyası gerekir (bkz. bölüm 5).

---

## 2. Sunucu (VPS) kiralama

1. https://www.hetzner.com/cloud adresinde hesap açın ve bir sunucu kiralayın (örnek: **CX22**, işletim sistemi **Ubuntu 24.04**). Aylık birkaç euro yeterlidir.
2. Kurulum sırasında bir SSH anahtarı ekleyin ya da e-postanıza gelen root şifresini kullanın.
3. Sunucunun **IP adresini** not alın (örnek: `203.0.113.10`).

## 3. Alan adını sunucuya yönlendirme

Alan adını aldığınız firmanın (GoDaddy, Natro, Cloudflare vb.) DNS ayarlarına girin ve şu kaydı ekleyin:

| Tür | Ad | Değer |
|-----|----|-------|
| A | `@` (ya da boş) | sunucunun IP adresi |
| A | `www` | sunucunun IP adresi |

Değişikliğin yayılması birkaç dakika ile birkaç saat sürebilir. HTTPS sertifikası, alan adı sunucuya ulaştığında otomatik alınır.

## 4. Sunucuya Docker kurma ve projeyi kopyalama

Bilgisayarınızdan sunucuya bağlanın: `ssh root@203.0.113.10`

```bash
curl -fsSL https://get.docker.com | sh      # Docker'ı kurar
apt-get install -y git
git clone <PROJENİN-GITHUB-ADRESİ> vatansagolsun
cd vatansagolsun
```

## 5. `.env` dosyasını doldurma

```bash
cp .env.example .env
nano .env        # kaydet: Ctrl+O, Enter; çık: Ctrl+X
```

Doldurmanız gerekenler:

- `ALAN_ADI` ve `SITE_URL`: kendi alan adınız (`ornek.com` / `https://ornek.com`).
- `OTURUM_HTTPS=true`: olduğu gibi bırakın (sunucuda HTTPS ile çalışır). Yalnızca bilgisayarınızda HTTP ile deneyecekseniz `OTURUM_HTTPS=false` yazın (ya da satırı silin).
- `SECRET_KEY`: **en az 32 rastgele karakter olmalıdır.** Kısa ya da `degistir` kalırsa **yönetici paneli kilitli kalır**. Üretmek için:

  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

  Çıkan metni `SECRET_KEY=` satırına yapıştırın. (Bilgisayarınızda Windows ise `python` yazın.)
- `POSTGRES_PASSWORD`: uzun bir şifre yazın (yalnızca harf ve rakam kullanın).
- `ADMIN_KULLANICI`: panele girişte kullanacağınız ad.
- `ADMIN_SIFRE_HASH`: panel şifrenizin güvenli (şifrelenmiş) hâli. Şifrenizi **düz yazmayın**; şu komutla üretin:

  ```bash
  docker compose run --rm app python -m app.cli sifre-olustur
  ```

  (Bilgisayarda deniyorsanız: `.venv/Scripts/python -m app.cli sifre-olustur`.) Şifrenizi iki kez sorar ve şuna benzer bir satır basar:

  ```
  ADMIN_SIFRE_HASH='$2b$12$abc...'
  ```

  Bu satırı **tek tırnaklarla birlikte, olduğu gibi** `.env` içindeki `ADMIN_SIFRE_HASH=` satırının yerine yapıştırın. Tek tırnaklar önemlidir: Docker Compose, tırnaksız `$` işaretini değişken sanıp şifreyi bozar. Tek tırnaklı hâli hem Docker'da hem yerel çalıştırmada denendi ve doğru çalışıyor.

`.env` dosyasını kimseyle paylaşmayın, GitHub'a yüklemeyin.

## 6. Siteyi başlatma

```bash
docker compose up -d --build
```

İlk seferde birkaç dakika sürer. Bittiğinde `https://alanadiniz.com` açılır. Kontrol: `curl https://alanadiniz.com/api/istatistik` bir sayı döndürmelidir. Tabloları uygulama açılırken kendisi oluşturur.

Panele giriş: `https://alanadiniz.com/panel` adresine gidin, `.env` içindeki kullanıcı adı ve (hash'i üretirken yazdığınız) şifre ile girin. Giremiyorsanız `SECRET_KEY` en az 32 karakter mi diye bakın.

Logları görmek: `docker compose logs -f app`

## 7. Güncelleme

```bash
cd vatansagolsun
git pull && docker compose up -d --build
```

## 8. Yedek alma

Veritabanının yedeğini alın (düzenli olarak, örneğin haftada bir):

```bash
docker compose exec -T db pg_dump --clean --if-exists -U vatansagolsun vatansagolsun > yedek-$(date +%F).sql
```

Yedeği geri yüklemek için önce uygulamayı durdurun, yükleyin, sonra yeniden başlatın:

```bash
docker compose stop app
docker compose exec -T db psql -U vatansagolsun vatansagolsun < yedek-2026-01-01.sql
docker compose start app
```

Yedek dosyasını sunucudan başka bir yere (kendi bilgisayarınıza) kopyalamayı unutmayın.

---

## 9. Geçmiş verileri aktarma

Site, kamuya açık resmî arşivlerden geçmiş şehit kayıtlarını kendisi toplayabilir. Kaynaklar: `egm` (Emniyet), `sg` (Sahil Güvenlik), `kahramanlar` (kahramanlar.org.tr, 2000 öncesi), `sehitlerimiz` (sehitlerimiz.org.tr, 2000 sonrası). Siteler her istek arasında en az 2 saniye beklenerek, nazikçe taranır.

### Kaynakları açıp kapatma

`.env` içindeki `KAYNAK_IZINLERI` satırı hangi kaynaklardan veri alınacağını belirler:

```
KAYNAK_IZINLERI=["egm","sg","kahramanlar","sehitlerimiz"]
```

Bir site itiraz ederse o kaynağın adını listeden **çıkarın** (örnek: `["egm","sg","kahramanlar"]`) ve `docker compose up -d` çalıştırın; o kaynağa artık hiç istek gitmez. O kaynaktan gelmiş kayıtları API'den de gizlemek isterseniz adını `API_HARIC_KAYNAKLAR=["sehitlerimiz"]` satırına yazın.

### Komutlar

```bash
docker compose exec app python -m app.cli aktar hepsi     # tüm kaynakları sırayla aktarır
docker compose exec app python -m app.cli aktar egm       # tek kaynak: egm | sg | kahramanlar | sehitlerimiz
docker compose exec app python -m app.cli aktarim-durumu  # her kaynak için sayılar ve son durum
```

Toplu aktarımla gelen kayıtlar doğrudan yayına girer. Aynı kayıt iki kez eklenmez; komutu tekrar çalıştırmak güvenlidir.

### Ne kadar sürer?

- `egm` ve `sg`: birkaç dakika.
- `kahramanlar`: yaklaşık 1.850 istek x 2 saniye, yani **yaklaşık 1 saat**.
- `sehitlerimiz`: 2000 sonrası her kaydın kendi sayfası alınır; yüzlerce, hatta binlerce istek demektir ve **saatler sürebilir**.

Komut yarıda kesilirse (bağlantı koptu, Ctrl+C, sunucu yeniden başladı) **aynı komutu tekrar çalıştırın**; kaldığı yerden devam eder. Uzun işleri bağlantınız kopsa da sürsün diye arka planda çalıştırın:

```bash
docker compose exec -d app python -m app.cli aktar hepsi
```

(`-d`: arka planda çalıştırır.) İlerlemeyi `aktarim-durumu` ile izleyin.

### 12 saatlik otomatik kontrol

`sehitlerimiz` kaynağı açıkken site, 12 saatte bir sehitlerimiz.org.tr'nin "son eklenenler" listesine bakar (sunucu açıldıktan 5 dakika sonra ilk kontrol yapılır). Yeni bir kayıt bulursa onu **yayına almaz**; yönetici panelinde **onay bekleyenler** arasına düşer, siz onaylayınca yayınlanır. Elle tek seferlik çalıştırmak için:

```bash
docker compose exec app python -m app.cli sehitlerimiz-kontrol
```

> Toplu aktarım (`aktar sehitlerimiz` ya da `aktar hepsi`) sürerken `sehitlerimiz-kontrol`'ü elle çalıştırmayın: ikisi aynı siteye aynı anda istek atar ve aynı kayıtları farklı durumlarla (toplu aktarım yayında, kontrol onay bekliyor) almaya çalışır. Aktarım bitince çalıştırın.

İlk çalıştırmada kontrol yalnızca "şu an sitedeki en son kayıt" noktasını işaretler, geçmişi getirmez (geçmiş için yukarıdaki `aktar` komutu vardır). Bu kontrol `docker-compose.yml` içindeki `ZAMANLAYICI_AKTIF=true` ayarıyla çalışır; yerelde kapalıdır.

> Uygulama Docker'da **tek** süreç olarak çalışır. `uvicorn`'a `--workers` ekleyip birden fazla süreç çalıştırırsanız her süreç kendi zamanlayıcısını başlatır ve kontrol birden fazla kez yapılır.

---

## 10. Yeni şehitleri otomatik toplama

Site, **30 dakikada bir** (sunucu açıldıktan 2 dakika sonra ilk tur) yeni şehit haberlerini kendisi arar. Bunun için `.env` içinde `ZAMANLAYICI_AKTIF=true` olmalıdır (`docker-compose.yml` bunu zaten açar). Her tur şunlara bakar:

- Resmî sayfalar: Emniyet (`egm`) ve Sahil Güvenlik (`sg`) sitelerinin en yeni kayıtları.
- Haber siteleri: **Hürriyet** ve **Sabah**. Bu sitelerin haber akışındaki, şehitlik içeren haberler yapay zekâ (Claude) ile okunur; haberde geçen şehitlerin adı, görevi, tarihi çıkarılır. Her haber yalnızca bir kez okunur.
- AA ve TRT de desteklenir ama **varsayılan kapalıdır**. Açmak için `.env` içindeki `KAYNAK_IZINLERI` listesine `"aa"` ve/veya `"trt"` ekleyip `docker compose up -d` çalıştırın.

**Toplayıcı hiçbir kaydı kendi başına yayına almaz.** Bulduğu her yeni kayıt panelde **onay bekleyenler** arasına düşer; siz bakıp onaylayınca yayınlanır.

### Claude API anahtarı

Haber okuma için bir Claude API anahtarı gerekir (resmî sayfa taraması anahtarsız da çalışır):

1. https://console.anthropic.com adresinde hesap açın, faturalandırma bilgisi ekleyin.
2. **API Keys** bölümünden yeni bir anahtar oluşturun ve kopyalayın (yalnızca bir kez gösterilir).
3. `.env` dosyasındaki satıra yapıştırın: `ANTHROPIC_API_KEY=sk-ant-...`
4. `docker compose up -d` ile yeniden başlatın.

Anahtarı kimseyle paylaşmayın; panelde de gösterilmez, yalnızca "yapılandırıldı" ya da "anahtar yok" yazar. Anahtar yoksa haber siteleri atlanır ("API anahtarı yok" durumu), resmî sayfalar taranmaya devam eder. Bu yüzden anahtar eklenene kadar panelin üstünde "Toplayıcıda hata var" uyarısı görünür; bu beklenen bir durumdur, anahtarı ekleyince kaybolur.

**Tahmini maliyet:** günde birkaç düzine haber okunur. Küçük ve ucuz model (Haiku 5.5) kullanıldığı için olağan bir ayda maliyet birkaç doların altında kalır. Güvenlik için günlük okuma sayısı `GUNLUK_ANALIZ_SINIRI` (varsayılan 200) ile sınırlıdır.

**Üst sınır:** yoğun bir dönemde her gün 200 sınırına ulaşılır ve haberler uzunsa, aylık maliyet **onlarca dolara** çıkabilir. Daha düşük bir tavan için `.env` dosyasında `GUNLUK_ANALIZ_SINIRI` değerini küçültün (örneğin `GUNLUK_ANALIZ_SINIRI=50`) ve `docker compose up -d` ile yeniden başlatın. Sınır dolunca o günün kalan haberleri ertesi güne kalır (3 güne kadar telafi edilir). Ayrıca console.anthropic.com'da aylık harcama limiti koymanızı öneririz.

### Panelde izleme

Panelde **Toplayıcı** sekmesi her kaynağın son çalışma zamanını, durumunu ve kaç kayıt eklediğini gösterir; bugün kaç haberin okunduğunu ve anahtarın tanımlı olup olmadığını da yazar. **Şimdi çalıştır** düğmesi turu beklemeden başlatır (bir tur zaten sürüyorsa "Toplayıcı zaten çalışıyor; bittiğinde tekrar deneyin" yazar). Eklenen/Birleşen/Atlanan/Hatalı sütunları ilk çalışmadan bu yana **toplam** sayılardır. Toplayıcıda hata varsa ana panelin üstünde kısa bir uyarı çıkar. Zamanlayıcı kapalıysa elle çalıştırın:

```bash
docker compose exec app python -m app.cli topla
```

### Rozetler

- **Resmî teyit yok**: kayıt yalnızca haberden çıkarıldı; haberde resmî bir kurum (bakanlık, Emniyet vb.) açıklaması geçmiyor. Onaylamadan önce kaynağı kontrol edin.
- **İsimsiz**: haber şehit olduğunu söylüyor ama isimleri henüz açıklanmamış. Kayıt tek bir "İsimsiz" taslağı olarak gelir; isimler açıklanınca düzenleyip adı yazabilir ya da gerçek kayıtla birleştirebilirsiniz.

### Bilmeniz gerekenler

- Emniyet ve Sahil Güvenlik sayfaları, o kaynağın **toplu aktarımı yapılmadan taranmaz** (aksi halde yüzlerce eski kayıt onay bekleyene düşerdi). Önce bölüm 9'daki `aktar egm` ve `aktar sg` komutlarını çalıştırın; o zamana kadar durum "önce aktar çalıştırın" yazar.
- Sunucu bir süre kapalı kalırsa toplayıcı, açıldığında **en fazla 3 gün** geriye giderek kaçırılan haberleri telafi eder.
- X (Twitter) hesapları kaynak olarak **kullanılmaz**: X, otomatik okumaya izin vermiyor ve ücretli API gerektiriyor; ayrıca doğrulanmamış paylaşımlar bu site için güvenilir değil.

---

## Geliştiriciler için

- Testler: `.venv/Scripts/python -m pytest`
- API belgesi: `/api/belgeler`
- İstek sınırı IP başınadır (`ISTEK_SINIRI`); uygulama yalnızca Caddy arkasında çalıştırılır ve `X-Forwarded-For` başlığına güvenir. Uygulama portunu (8000) internete açmayın.
