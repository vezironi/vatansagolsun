# vatansagolsun — Tasarım Belgesi

Tarih: 2026-10-23
Durum: Onay bekliyor
Önizleme tasarımı: `docs/superpowers/specs/mockups/ana-sayfa-b.html`

İşaretler: **[Kullanıcı]** = kullanıcının kendi kararı. **[Benim kararım]** = kullanıcının bana bıraktığı ya da benim önerip itiraz görmeyen seçim; gerekirse değişebilir.

---

## 1. Amaç ve neden

**vatansagolsun**, Türk askerleri, polisleri, öğretmenleri ve görev başında hayatını kaybeden diğer şehitler için bir dijital anıt ve açık API'dir. [Kullanıcı]

Örnek alınan site anitsayac.com'dur: tek sayfada bir sayaç, yıl seçici ve isim listesi; verinin haberlerden toplanıp elle doğrulanması. Kullanıcı bu sitenin "her şeyini" (düzen, veri toplama şekli, sade anma dili) örnek almak istiyor. [Kullanıcı]

Sistem üç iş yapar:
1. Kırım Savaşı'ndan (1856) bugüne tüm şehitleri isim isim listeler, toplam ve bu yılın sayısını gösterir.
2. Yeni şehit haberlerini 30 dakikada bir otomatik toplar; kullanıcı onaylayınca yayına alır.
3. Bunların hepsini herkese açık bir API ile sunar; özellikle "bugün yıl dönümü olan şehitler" (2000 sonrası).

## 2. Hedefler, hedef olmayanlar, anti-hedefler

**Hedefler**
- Toplam şehit sayısı ve bu yıl şehit düşenlerin sayısı (sitede ve API'de). [Kullanıcı]
- Tüm şehitlerin listesi: ad soyad + şehadet yılı (sitede ve API'de). [Kullanıcı]
- "Bugün" listesi: şehadet tarihi 2000 ve sonrası olup, gün/ayı bugüne denk gelen şehitler. 2000 öncesi savaşlar bu listeye girmez. [Kullanıcı]
- 30 dakikada bir yeni haberleri tarayan otomatik toplayıcı. [Kullanıcı]
- Hiçbir yeni kayıt kullanıcı onaylamadan yayına girmez; onay bir web paneli üzerinden yapılır. [Kullanıcı]

**Hedef olmayanlar (şimdilik)**
- X (Twitter) hesaplarını okumak. Ücretli API gerektirdiği için sonraya bırakıldı. [Kullanıcı] Ancak toplayıcı, kaynak eklemek kolay olacak şekilde tasarlanmalı ki X sonradan bir kaynak olarak eklenebilsin.
- Kullanıcı hesapları, yorum, bağış, sosyal özellikler. [Benim kararım]
- Mobil uygulama. Site mobilde düzgün çalışır, o kadar. [Benim kararım]

**Anti-hedefler (çalışsa bile başarısızlık sayılır)**
- Yanlış isimle, yanlış tarihle ya da hiç şehit olmamış birinin şehit olarak yayımlanması. Doğruluk hızdan önemlidir; şüpheli her şey onaya düşer.
- Aynı şehidin iki kez sayılması (MSB ve beş haber sitesi aynı kişiyi yazar).
- Kaynak sitelere zarar verecek, kullanım koşullarını çiğneyecek ya da onları yükleyecek veri çekimi.
- Siyasi, kışkırtıcı ya da sansasyonel bir dil. Ton sade ve ağırbaşlıdır.

## 3. Kısıtlar

- Kullanıcı teknik seçimleri bilmiyor ve bana bıraktı; kurulum ve işletim adımları açık, adım adım yazılmalı. [Kullanıcı]
- Bütçe düşük olmalı: ayda ~5–10 $ sunucu + birkaç $ yapay zekâ maliyeti. X API gibi ciddi aylık maliyetler kapsam dışı. [Kullanıcı / Benim kararım]
- Arayüz dili Türkçe. Türkçe karakterler (İ/ı, Ş, Ğ) arama, sıralama, büyük/küçük harf ve URL (slug) üretiminde doğru işlenmeli.
- Saat dilimi: Europe/Istanbul. "Bugün", "bu yıl" ve "sadece bugünün haberleri" hep Türkiye saatine göre hesaplanır.

## 4. Kararlaştırılanlar

### 4.1 Teknoloji [Benim kararım]

| Parça | Seçim |
|---|---|
| Dil | Python |
| Web/API | FastAPI; site ve panel sunucu tarafında Jinja2 şablonlarıyla üretilir |
| Veritabanı | PostgreSQL |
| Zamanlayıcı | Uygulama içinde 30 dakikalık iş (APScheduler veya eşdeğeri) |
| Haber analizi | Anthropic Claude Haiku (`claude-haiku-5-5`) |
| Dağıtım | Docker Compose; tek bir ucuz VPS (ör. Hetzner); HTTPS (ör. Caddy) |
| Alan adı | vatansagolsun.com veya benzeri (kullanıcı alır) |

### 4.2 Veri modeli (şehit kaydı)

Her kayıtta en az şunlar bulunur:
- ad, soyad (eski kayıtlarda soyad yoktur — bkz. 4.3)
- şehadet tarihi + **tarih hassasiyeti**: `tam` (gün/ay/yıl), `yil` (sadece yıl) veya `bilinmiyor`
- görev/rütbe (ör. "Piyade Uzman Çavuş", "Öğretmen")
- kategori: `asker`, `jandarma`, `polis`, `ogretmen`, `diger` (korucu, sivil vb.) — sitedeki renkli etiketler buna göre
- kurum (TSK, Jandarma, Emniyet, MEB, ...)
- memleket (il, varsa ilçe/köy), baba adı, doğum yılı (varsa)
- dönem/cephe (ör. "Birinci Dünya Savaşı — Çanakkale Cephesi", "Terörle Mücadele")
- kaynaklar (bir veya birden fazla link/metin; aynı kişi birden çok kaynakta geçebilir)
- durum: `onay_bekliyor`, `yayinda`, `reddedildi`
- kalıcı, paylaşılabilir adres: `/sehit/{ad-soyad}-{id}`

**Kim şehit sayılır** [Benim kararım; kullanıcı bana bıraktı]: Resmî bir kurumun (MSB, EGM, Jandarma, Sahil Güvenlik, MEB, valilik vb.) "şehit" olarak duyurduğu herkes. Bunun dışında, sadece haber sitesinin "şehit" demesine dayanan durumlar (ör. trafik kazası, hastalık, terör saldırısında ölen siviller) otomatik reddedilmez ama panelde "resmî teyit yok" uyarısıyla düşer; karar kullanıcınındır. Böylece site kendi başına siyasi/editoryal tanım yapmaz.

**Sayımlar:** "Toplam" = yayındaki tüm kayıtlar. "Bu yıl" = şehadet tarihi bu takvim yılında olan yayındaki kayıtlar. Bu sayılar "arşivimizdeki kayıt sayısı"dır, resmî toplam değildir; sitede bunu belirten kısa bir not bulunur. [Benim kararım — kaynak arşiv de aynı uyarıyı yapıyor]

### 4.3 Geçmiş verinin aktarımı (bir kerelik)

Kullanıcı tüm şehitlerin (1856'dan bugüne) sistemde olmasını istiyor. [Kullanıcı]

Araştırılan kaynaklar:
- **sehitlerimiz.org.tr** (kullanıcının önerisi): ~115.886 kayıt, 1856–2026. Kayıt alanları: ad soyad, memleket, baba adı, şehadet tarihi, şehadet yeri, kurum/birlik, dönem/cephe. 2000 sonrası kayıtların çoğunda tam tarih var (ör. `/yil/2016` sayfası). robots.txt'de "Otomatik araçlarla toplu kopyalama sunucu tarafında sınırlanır" yazıyor ve tam liste indirme sayfası kapalı. **Karar (2026-10-23):** Kullanıcı, verilerin MSB ve haber kaynaklarının kamuya açıkladığı bilgiler olduğunu belirterek izin beklemeden aktarılmasına karar verdi. [Kullanıcı] Koşullar: yavaş çekim (aynı sunucuya en az 2 sn arayla), robots.txt'nin yasakladığı yollara girilmez, her kayıtta kaynak gösterilir, kaynak `.env` ayarıyla tek satırda kapatılabilir. Bilinen risk: derlenmiş veritabanının toplu kopyalanması FSEK'teki veri tabanı korumasına takılabilir; site sahibi itiraz ederse kaynak kapatılıp kayıtları API'den çıkarılır. Kaynak gösterimi zorunlu.
- **kahramanlar.org.tr açık JSON API'si** (`https://kahramanlar.org.tr/api.php`): ~92.114 kayıt, sayfalı (`page`, `limit`, `has_more`). Alanlar: `ad`, `rutbe`, `sehadet_tarihi`, `harp`, `baba_adi`, `lakap`, `dogum_yili`, `memleketi`, `il_filtresi`. Açık bir API olduğu için izin sorunu daha az; yine de nazikçe (yavaş, kaynak göstererek) çekilir. Gözlem: örnek kayıtların çoğu eski savaşlardan ve `sehadet_tarihi` alanı boş; filtre parametreleri belgelenmemiş.
- Her iki arşiv de kayıtları MSB Şehit Bilgi Kapısı, Emniyet, Jandarma ve valiliklerin kamuya açık verilerinden derlediğini söylüyor; gerekirse asıl kaynaklara gidilebilir.

Kurallar:
- Aktarılan geçmiş kayıtlar onaydan geçmeden doğrudan `yayinda` olarak girer (115 bin kaydı elle onaylamak imkânsız). [Benim kararım]
- Toplu aktarım bir kerelik yapılır; aktarım betiği tekrar çalıştırılabilir olur (yeni kayıtları ekler, var olanları çoğaltmaz). [Benim kararım] Sonrasında sehitlerimiz.org.tr'ye 12 saatte bir yalnızca yeni kayıtlar için bakılır (bkz. 4.4) [Kullanıcı]; arşivlerin eski kayıtlarda yaptığı düzeltmeler otomatik çekilmez, "Hatalı kayıt bildir" ve panel üzerinden gelir. [Benim kararım]
- Her kaydın hangi kaynaktan geldiği saklanır; böylece bir kaynak itiraz ederse o kaynağın kayıtları API'den çıkarılabilir (`API_HARIC_KAYNAKLAR`) ya da kaynak tamamen kapatılabilir (`KAYNAK_IZINLERI`). [Benim kararım]
- İki kaynak birleştirilirken aynı kişi tek kayda indirilir (ad + baba adı + memleket + dönem gibi alanlarla eşleştirme).
- Soyadı Kanunu (1934) öncesi kayıtlarda soyad yoktur. Bu kayıtlarda "ad soyad" yerine ad + lakap (ör. "İSMAİL — Aşçıoğullarından") gösterilir; API'de `soyad` boş, `lakap` dolu döner.
- Kaynak verideki BÜYÜK HARF isimler okunur hale getirilir (ör. "Ahmet YILMAZ"), Türkçe kurallarına göre.

**Geçmiş veri için öncelik** [Kullanıcı]: Önce resmî kaynaklar (EGM ve Sahil Güvenlik şehit sayfaları, MSB) — bunlar 2000 sonrası tam tarihli kayıtların da ana kaynağıdır. sehitlerimiz.org.tr en son, eksikleri tamamlamak için kullanılır. Resmî kaynaklarda olan bir kayıt, arşivlerden gelen aynı kişiye tercih edilir (tarih ve isim yazımı resmî kaynaktan alınır). [Tercih sırası: benim kararım]

**Risk:** "Bugün" özelliği tam tarihli 2000 sonrası kayıtlara dayanıyor. TSK/Jandarma şehitleri için resmî tarafın toplu listesi (MSB Şehit Bilgi Kapısı) henüz incelenmedi; builder ilk iş olarak bunu ve EGM detay sayfalarında tarih alanı olup olmadığını kontrol etmeli.

### 4.4 Toplayıcı (her 30 dakikada bir)

[Kullanıcı] tarafından tarif edildiği şekilde:
- Her kaynak için **en son okunan haber** (imleç) saklanır — kullanıcının deyişiyle "Y haberi".
- Her çalışmada kaynağın en yeni haberinden başlanır, geriye doğru okunur; Y haberine ulaşınca durulur. Arada 10 yeni haber geldiyse sadece o 10'u okunur. Sonra imleç en yeni habere taşınır.
- Sadece **o günün tarihli** haberleri incelenir; daha eski tarihli bir habere gelinirse de durulur.
- İlk çalışmada (imleç yokken) sadece bugünün haberleri okunur. [Benim kararım]

Kaynaklar, **bu öncelik sırasıyla** [Kullanıcı]:
1. **Resmî kurum sayfaları** (önce bunlar kontrol edilir):
   - Emniyet: `https://www.egm.gov.tr/sehitlerimiz`, `https://www.egm.gov.tr/ozelharekat/sehitlerimiz`, `https://www.egm.gov.tr/istihbarat/istihbarat-sehitlerimiz`, `https://www.egm.gov.tr/havacilik/sehitlerimiz`
   - Sahil Güvenlik: `https://www.sg.gov.tr/sehitlerimiz`
   - MSB'nin resmî duyuruları. [Kullanıcı: önceki konuşmada "MSB resmi hesabı"]
   - Gözlem: EGM sayfaları fotoğraflı listelerdir; her şehidin ayrı bir detay sayfası vardır (ör. `/ozelharekat/sehit-polis-memuru-aytac-altunors`) ve kayıtlar numaralıdır (ör. "389 - Yusuf Çağatay SANALP"). robots.txt bu sayfalara izin veriyor. Bazı sunucular otomatik araçlara 500 hatası döndürebiliyor; tarayıcı benzeri istek başlığı ve yavaş çekim gerekir.
2. **Haber siteleri:**
   - Sabah: `https://www.sabah.com.tr/arama?query=sehit` — kullanıcının verdiği adres. Not: Sabah'ın robots.txt'si `/arama` yolunu yasaklıyor; bu yüzden aynı haberler Sabah'ın RSS akışından ya da ilgili kategori sayfasından alınır. [Benim kararım]
   - Hürriyet: `https://www.hurriyet.com.tr/haberleri/sehit` (izinli).
3. **X hesapları:** `x.com/bpthaber`, `x.com/ConflictTR`, `x.com/pusholder`. [Kullanıcı] İlk sürümde **yok**; ücretli API gerektirdiği için sonraya bırakıldı (kullanıcının önceki "sonra yapalım" kararı; son soruda bu konu yeniden cevaplanmadı). Toplayıcı bu üç hesabı sonradan kaynak olarak ekleyebilecek şekilde yapılır.
4. **sehitlerimiz.org.tr:** en son bakılan kaynak. [Kullanıcı] İlk kurulumda geçmişin tamamı alınır; sonra **12 saatte bir** sadece yeni eklenen kayıtlara bakılır — diğer kaynakların kaçırdığı şehitleri yakalayan bir güvenlik ağı. Buradan gelen yeni kayıtlar da diğerleri gibi onaya düşer. [Kullanıcı; onaya düşmesi benim kararım] Arşivin en yeni kayıtlarını görmek için hafif bir yol kullanılır (ör. sitemap ya da en yeni kayıtlar sayfası), tüm arşiv yeniden taranmaz.

Kaynak listesi bir ayar dosyasında/tabloda tutulur; yeni kaynak eklemek kod değişikliği gerektirmemeli (her kaynak türü için bir okuyucu: resmî liste sayfası, haber listesi/RSS, X).

Her haber için iki temel kontrol [Kullanıcı]:
- **Tarih:** Haber yeni mi (bugünün mü)?
- **Tekrar:** Bu şehit adı ve bilgileri veritabanında zaten var mı? Varsa yeniden eklenmez.

Adımlar:
1. Claude Haiku'ya haber metni verilir ve yapılandırılmış bir cevap istenir: şehit haberi mi; şehit(ler)in adı, soyadı, şehadet tarihi, görevi/rütbesi, kategorisi, memleketi; isim belli mi.
2. Şehit haberi değilse atlanır.
3. Şehit haberiyse her kişi için **onay bekleyen** bir taslak kayıt oluşturulur; haber linki ve metni kayda eklenir.
4. İsimsiz haberler ("2 askerimiz şehit oldu") de "isimsiz" taslak olarak panele düşer; isimler genelde ertesi gün ayrı bir haberde açıklanır. Kullanıcı bunları sonradan gelen isimli kayıtla birleştirebilir ya da reddedebilir.
5. Aynı kişi zaten kayıtlı ya da onay bekliyorsa yeni kayıt açılmaz; yeni haber mevcut kayda ek kaynak olarak eklenir.

Hata durumunda (kaynak erişilemez, model hatası) o kaynak için imleç ilerletilmez; bir sonraki çalışmada tekrar denenir. Panelde son çalışmaların durumu görünür.

**Kesinti sonrası telafi** [Benim kararım]: "Sadece bugünün haberleri" kuralı normal işleyişte geçerlidir. Sunucu ya da model gece yarısını geçen bir süre çalışamadıysa, sonraki çalışma imleçten (Y haberinden) itibaren okur ve en fazla 3 gün geriye gider. Böylece kesinti yüzünden haber kaybolmaz; kullanıcının "Y haberine gelince dur" kuralı da korunur.

### 4.5 Onay paneli

[Kullanıcı]: yayından önce kullanıcı onaylar; panel bir web sitesi (Discord değil).

- Sadece kullanıcı girer: kullanıcı adı + şifre. [Benim kararım]
- "Onay bekleyenler" listesi: her taslakta çıkarılan bilgiler + kaynak haber(ler)in linki ve metni.
- Her alan düzenlenebilir; sonra **Onayla** (yayına girer) veya **Reddet**.
- Yayındaki bir kaydı sonradan düzeltme/kaldırma.
- İki taslağı tek kayıtta birleştirme (isimsiz + isimli, ya da tekrar eden kayıtlar).
- Sitedeki "Hatalı kayıt bildir" formundan gelen bildirimler de burada görünür. [Benim kararım]
- Toplayıcının son çalışmaları: ne zaman çalıştı, kaç haber okudu, hata var mı.

### 4.6 Herkese açık site

[Kullanıcı] seçti: Tema B (tablo) + C'deki "Bugün" kutusu, **sayacın üstünde**. Referans tasarım: `docs/superpowers/specs/mockups/ana-sayfa-b.html` (tarayıcıda açılır; içindeki isimler örnek veridir; alttaki geçiş çubuğu sadece önizleme içindir, "sayacın üstünde" seçeneği geçerlidir).

Ana sayfa, yukarıdan aşağıya:
1. Üst menü: logo (VATAN**SAĞOLSUN**), Ara, Yıl Dönümleri, Hakkında, API.
2. **"Bugün, 23 Ekim" kutusu**: 2000 sonrası, bugünün gün/ayında şehit düşenler kart olarak; her kartta ad SOYAD, tarih, görev, memleket ve "N. yıl dönümü". O gün kimse yoksa kutu gizlenir. [Gizleme: benim kararım]
3. Sayaç: Toplam Şehit + {bu yıl} Yılında; açılışta sıfırdan sayarak gelir.
4. Yıl seçici: Tümü, 2026 … 2000, 2000 öncesi.
5. Arama kutusu (isim, il, görev) + tablo: Ad Soyad, Şehadet Tarihi, Görev (kategori rengiyle etiket), Memleket, Kurum. Sayfa başına 25 kayıt, sayfalama. Tarihi sadece yıl olanlarda yıl, bilinmeyenlerde boş gösterilir.
6. Kayda tıklayınca detay penceresi: tarih, memleket, baba adı, kurum, kaynak linki. Ayrıca her şehidin kendi sayfası (`/sehit/...`) vardır; paylaşılabilir ve arama motorlarında çıkar. [Benim kararım]
7. Alt bilgi: proje açıklaması, verinin kaynakları, "kayıt sayısı resmî toplam değildir" notu, API adresleri, "Hatalı kayıt bildir" formu linki.

Menüdeki diğer sayfalar [Benim kararım]:
- **Ara**: ana sayfadaki arama kutusuna götürür (ayrı sayfa yok).
- **Yıl Dönümleri**: bir gün/ay seçilen basit bir sayfa; o tarihte (2000 sonrası) şehit düşenleri "Bugün" kutusuyla aynı kart düzeninde gösterir (`/api/bugun?tarih=` ile aynı sorgu).
- **Hakkında**: projenin amacı, veri kaynakları, doğrulama süreci, iletişim.
- **API**: API belge sayfası.

Görsel dil: koyu arka plan, bayrak kırmızısı (#e30a17) vurgu, isimlerde serif (Cormorant Garamond), metinde Inter. Ton sade ve ağırbaşlı.

**Özel kaydırma çubuğu** [Kullanıcı]: sitenin genelinde (sayfa, yıl seçici, tablo) temaya uyan ince, koyu bir kaydırma çubuğu; tutamaç koyu gri, üzerine gelince kırmızıya döner. Chrome/Edge/Safari (`::-webkit-scrollbar`) ve Firefox (`scrollbar-color`, `scrollbar-width`) için.

Mobilde düzgün çalışır; dar ekranda tablonun Memleket ve Kurum sütunları gizlenir.

### 4.7 Açık API

Herkese açık, anahtar gerektirmez, JSON döner, sadece yayındaki kayıtları gösterir. Kötüye kullanıma karşı IP başına istek sınırı vardır. [Anahtarsız + sınır: benim kararım]

| Uç nokta | Döndürdüğü |
|---|---|
| `GET /api/istatistik` | `toplam`, `bu_yil`, `yil` (ve isteğe bağlı yıllara göre dağılım) |
| `GET /api/sehitler?yil=&q=&sayfa=&adet=` | Sayfalı liste; her kayıtta en az `id`, `ad`, `soyad`, `sehadet_yili`; ayrıca tarih (hassasiyetiyle), görev, kategori, memleket. `adet` en fazla 100. |
| `GET /api/sehitler/{id}` | Tek kaydın tüm herkese açık alanları ve kaynakları |
| `GET /api/bugun` | Şehadet tarihi ≥ 2000 olup gün/ayı bugüne (Türkiye saati) denk gelen kayıtlar; isteğe bağlı `?tarih=AA-GG` ile başka bir gün |

[Kullanıcı] istedi: istatistik, tüm liste (ad soyad + yıl), bugün listesi. Filtreler, tek kayıt uç noktası ve `?tarih=` parametresi benim eklemem.

API için kısa bir belge sayfası (`/api` → otomatik dokümantasyon) sitede bağlantılıdır.

## 5. Builder'a bırakılanlar

- Kod yapısı, tablo şemasının ayrıntıları, ORM ve migration seçimi.
- Tekrar eden kayıtları eşleştirme algoritmasının ayrıntıları.
- Claude'a giden komut (prompt) ve yapılandırılmış çıktı biçimi.
- Kahramanlar API'sinin filtre parametrelerini keşfetmek ve iki arşivi birleştirme sırası.
- Başlangıç haber sitesi/RSS listesi önerisi (kullanıcıya gösterilip onaylatılır).
- İstek sınırı değerleri, önbellekleme, yedekleme.
- Kurulum belgesi: sunucu kiralama, alan adı, `.env` (Anthropic API anahtarı, panel şifresi) — teknik bilgisi olmayan biri için adım adım.

## 6. Sonraya bırakılanlar

- X (Twitter) kaynakları (ücretli API). Toplayıcı kaynak eklenebilir yapıda olduğu için sonradan eklenir.
- Telegram/Discord bildirimleri (ör. onay bekleyen kayıt gelince haber verme).
