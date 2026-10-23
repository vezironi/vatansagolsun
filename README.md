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

## Geliştiriciler için

- Testler: `.venv/Scripts/python -m pytest`
- API belgesi: `/api/belgeler`
- İstek sınırı IP başınadır (`ISTEK_SINIRI`); uygulama yalnızca Caddy arkasında çalıştırılır ve `X-Forwarded-For` başlığına güvenir. Uygulama portunu (8000) internete açmayın.
