# Sehit veri kaynaklari - bulgular (2026-10-23)
Ornek HTML/JSON: ./veri/ . Tum istekler tarayici UA, >=2 sn arayla.

## 1. EGM (egm.gov.tr) - 4 bolum
robots.txt: yalniz /kullanicilar /ortak_icerik /kurumlar Disallow (+arsiv botlari). Not: gorseller /kurumlar/... altinda -> robots'a gore gorsel indirilmemeli.
Anti-bot: yok; curl+UA ile hepsi 200 (WebFetch 500 verir). POST endpoint'e Referer + Content-Type: application/json yeterli. Yanlis endpoint 302 verir.

### /sehitlerimiz (ana liste, "taziye mesaji" haber listesi)
- Ilk sayfa 6 kart SSR. Devami AJAX: POST https://www.egm.gov.tr/ISAYWebPart/ContentList/DahaFazlaYukle
  body JSON: {"page":N,"ContentTypeId":"YNcLZaW4rMBeGR5FZn5E6A==","OrderByAsc":"true","ContentCount":"6"}  (N=2..; bos govde = son sayfa)
  (ContentFilter endpoint'i basTarih/bitTarih ister; page=1 ile 302 verdi.)
- Sayfa 2,60,75 dolu; 90,105,120,200 bos => ~60-89 sayfa = ~360-530 kayit. Siralama YENIDEN ESKIYE (2026-10-08 ... 2016-07-21). Liste 2016 sonrasini kapsar.
- Kart secicileri: `div.card-stretch a.news-card-horizontal[href]` (href `//www.egm.gov.tr/sehit-polis-memuru-ahmet-turkoglu`), `.card-title` (unvan+ad), `span.cardDate` (GG.AA.YYYY), img.card-img-top (cogu zaman jenerik taziye gorseli).
- Ornekler (verbatim):
  08.10.2026 | Şehit Polis Memuru Ahmet TÜRKOĞLU | //www.egm.gov.tr/sehit-polis-memuru-ahmet-turkoglu
  14.06.2026 | Şehit Polis Memuru Tayfun BAŞ
  21.07.2016 | Şehit Polis Memuru Ozan ÖZEN | /sehit-polis-memuru-ozan-ozen
- TARIH: TAM TARIH (GG.AA.YYYY), 2016+ icin var. kahramanlar.org'daki "POLİS ŞEHİDİ" kayitlari bu tarihlerle birebir ayni. Tarih haber/taziye yayin tarihi; sehadet gunuyle genelde ayni (dogrulanmadi).
- Detay sayfasi: `div.condolence-message`: `.martyr-name` ("Ahmet TÜRKOĞLU"), `.martyr-title` ("Polis Memuru"), `.condolence-message-detail p` serbest metin: "Ankara ili Pursaklar İlçe Emniyet Müdürlüğü kadrosunda görevli Polis Memuru Ahmet TÜRKOĞLU, görevi sırasında uğradığı menfur saldırıda yaralanmış ... şehit olmuştur." => gorev yeri (il/ilce birimi) yalniz serbest metinde; dogum yeri/memleket YOK.
- Yeni kayit tespiti: ana sayfa (SSR, ilk 6) + page=2; ilk href'leri bilinenlerle karsilastir.

### /ozelharekat/sehitlerimiz (ayni bilesen, ContentTypeId='MNwu2a6REuJpCzWh5FhgSg==', ContentCount 6, ayni endpoint)
- Tarihler: 05.10.2023, 18.08.2023, 24.10.2022, 22.04.2022, 22.03.2022 ... Detay (/ozelharekat/sehit-polis-memuru-aytac-altunors) = yalniz h2 baslik + `div.card-date` (22.04.2022) + tek gorsel (/kurumlar/.../387-_-ALTUNORS-Aytac.jpg), metin yok. Gorsel adindaki sayi sira no. Kayit sayisi onlarca.
### /istihbarat/istihbarat-sehitlerimiz: statik sayfa, ~34 <img> (alt="Bekir KILIÇTEPE", .../Sehitlerimiz/bekir_kilictepe.png), tarih/metin YOK.
### /havacilik/sehitlerimiz: kart/img yok (SSR'de bos); veri bulunamadi.
EGM sonuc: tek faydali yapisal kaynak = ana /sehitlerimiz (2016+, tam tarih, ~400-500 kayit).

## 2. Sahil Guvenlik (sg.gov.tr/sehitlerimiz)
- curl+UA: 200 (143 KB). robots EGM ile ayni sablon. Tek sayfa, sayfalama yok, 19 kayit.
- Secici: `div.manager-vertical-card`; `.manager-name` ad; `.manager-sm-card-body p` TAM TARIH ("20 Kasım 2019"); `.manager-sm-img a[href]` -> /kurumlar/sg.gov.tr/sehitlerimiz/pdf/HakanKaratas.pdf (PDF 418 KB, gorsel agirlikli; metin cikarilmadi); img data-src `/kurumlar/sg.gov.tr/sehitlerimiz/18_HAKAN-KARATAS_20-Kasim-2019.jpg` (sira_AD-SOYAD_tarih).
- Ornekler: Hakan KARATAŞ | 20 Kasım 2019 ; Sinan GÖKTAŞ | 17 Ağustos 2016 ; Ercan ARIKAN | 07 Haziran 2001 (en eski ikinci: Murat AYGEN 26 Aralık 2003, Süleyman SATIR 30 Temmuz 2005).
- Tarih tam, Turkce ay adli. Yeni kayit: ilk kart (en yeni ustte).

## 3. kahramanlar.org.tr/api.php
robots: `Content-Signal: search=yes,ai-train=no,use=reference`; ClaudeBot/CCBot/Google-Extended/Bytespider vb. Disallow. Sunucu tarafi rate-limit (check_rate_limit('arsiv'), 429). UA/anahtar gerekmedi. AI egitimi icin izin yok; referans kullanimi.
- Site JS (assets/app.js): GET api.php?page=&limit=&search=&il=&harp=&rutbe=&yil= (UI limit 50; istekler arasi 400 ms).
- MAX limit = 50 (limit=500 -> 50). Toplam 92114 -> ~1843 sayfa (tam tarama onerilmez).
- Yanit: {total,page,limit,has_more,meta:{iller(87),harpler(72),rutbeler(13),yillar(137)},data:[...]}; meta filtreli sonuclarda null olabilir.
- Filtre: harp/search/il/rutbe icerir-eslesme (harp=EMNİYET 391; harp=15 TEMMUZ 109; harp=TERÖRLE MÜCADELE 69 (kesin deger); search=ŞEYDA 2). `yil` = DOGUM yili. Turkce karakterler yuzde-kodlanmali (Git Bash argumani bozar -> yanlis 0 sonuc; ilk "filtre calismiyor" gozlemi buydu).
- Alanlar: ad, rutbe, sehadet_tarihi, harp, baba_adi, lakap, dogum_yili, memleketi, il_filtresi, sayfa. ID YOK. Siralama tarihe gore degil; cift kayit var (biri tarihli biri tarihsiz).
- sehadet_tarihi cogu bos. Dolu ise KARISIK format: "22.07.2015", "23 Aralık 2015", "5 Ekim 2015", "2010-06-21". Dolu olanlar: harp="POLİS ŞEHİDİ" (391 kayit, 44/50 dolu, 2016-2026 tam tarih, baba/memleket bos), harp="TERÖRLE MÜCADELE" (17/50), rutbe=Polis (24/50). "MSB GÜNCEL ŞEHİT VE VEFAT DUYURULARI (2026)" 7 kayit, TARIH BOS (ad "ULŞ. UZM. ÇVŞ. ABDURRAHMAN HİLAL", memleketi "TÜRKİYE", il_filtresi "MSB"). "15 TEMMUZ..." 109 kayit tarih bos. Tarihsel savaslar tarih bos.
- Ornekler:
 {"ad":"Tayfun BAŞ","rutbe":"Polis","sehadet_tarihi":"14.06.2026","harp":"POLİS ŞEHİDİ","baba_adi":"","lakap":"","dogum_yili":"","memleketi":"","il_filtresi":"","sayfa":0}
 {"ad":"FEYYAZ YUMUŞAK","rutbe":"Polis","sehadet_tarihi":"22.07.2015","harp":"TERÖRLE MÜCADELE","baba_adi":"-","lakap":"ŞEHİT POLİS","dogum_yili":"-","memleketi":"TÜRKİYE","il_filtresi":"TÜRKİYE","sayfa":0}
 {"ad":"MUSTAFA","rutbe":"Er / Erbaş","sehadet_tarihi":"","harp":"BİRİNCİ DÜNYA SAVAŞI (1914-1918) ÇANAKKALE CEPHESİ","baba_adi":"HASAN","lakap":"","dogum_yili":"1885","memleketi":"KASTAMONU ARAÇ","il_filtresi":"KASTAMONU","sayfa":0}
- Yeni kayit: ID/siralama yok; kucuk filtreli setleri (harp=MSB GÜNCEL..., POLİS ŞEHİDİ) total degisimiyle izle.

## 4. sehitlerimiz.org.tr
robots: Disallow /yonet.php /bildir.php /ara$ /ara? /_sk/ /arsiv/tam-liste-indir; Sitemap: /sitemap.xml ilan edilmis AMA /sitemap.xml, sitemap_index.xml, sitemap-index.xml, .gz hepsi 404 (llms.txt "Tum kayitlarin dizini: /sitemap.xml" diyor). "Toplu kopyalama sunucu tarafinda sinirlanir." Atif ("sehitlerimiz.org.tr — Türkiye Şehit Arşivi" + kayit linki) rica ediliyor. nginx, normal UA ile 200; Cache-Control max-age=1800; Last-Modified var.
- llms.txt: 115.886 kayit, 1856-2026; desenler /sehit/{slug}-{id}, /il/, /donem/, /kurum/, /yil/{yyyy} (85 yil sayfasi), /arsiv.
- Kayit (/sehit/mustafa-aslan-116814): JSON-LD Person: name, description, jobTitle, birthPlace.name, deathDate "2026-10-14" (ISO), deathPlace.name, affiliation.name, citation{name,url}. HTML `article.record`: h1, p.kicker (rutbe), p.record-years "Şehadet: 14 Ekim 2026", `dl.fields > div > dt/dd` (Rütbe / Görev, Baba Adı, Doğum Yeri, Memleket, Şehadet Tarihi "14.10.2026", Şehadet Yeri "Hakkâri", Dönem / Cephe, Kurum), `p.source-line` (kaynak + url). Bos alan hic yazilmaz.
- Tarih: post-2000 kayitlarda genelde tam tarih; tarihsel kayitlarda yalniz yil.
- Liste /yil/2016: 200 kayit/sayfa, ?sayfa=N (rel=next), ALFABETIK, ad + (varsa) memleket; TARIH YOK; 1.023 kayit = 6 sayfa. Secici `ol.name-list li a[href^="/sehit/"]`, `span.li-meta`.
- ID'ler ~101xxx-116826, ekleme sirasi (116826 = Enver Pasa 1922; tarih sirasi degil); ardisik degil.
- EN UCUZ YENI KAYIT KONTROLU: GET /arsiv (12 kayit) veya / (24 kayit): `#son-eklenenler ol.name-list li a` + li-meta (tarih/yil/memleket); max id 116826. 12 saatte 1 istek; max id > bilinen ise yeni kayit sayfalarini cek (10 KB/kayit). Bosluk riski: 12 saatte >24 ekleme. Ek sinyal: footer "Son güncelleme: 19.10.2026" + toplam sayi.
- Polis: /donem/polis-sehidi 1.929; /kurum/emniyet-genel-mudurlugu 2.042; /kurum/sahil-guvenlik-komutanligi 17.

## 5. MSB (msb.gov.tr)
- curl: JS/cookie challenge. Her yol 302 (Set-Cookie Ref=JWT(remote_addr), Server Harpp-foton/openresty); cookie jar + -L ile dongu veya challenge sayfasi (robots.txt -> 404 + meta refresh + #challenge div). robots.txt, sitemap, ana sayfa okunamadi. Tarayici (JS) gerekir.
- WebSearch msb.gov.tr Şehit Bilgi Kapısı'nı indekslemiyor; duyurular haber ajanslari uzerinden. Resmi liste/RSS URL'si dogrulanamadi. sehitlerimiz.org.tr kaynak olarak "MSB Şehit Bilgi Kapısı"ni gosteriyor; kahramanlar.org "MSB GÜNCEL ŞEHİT VE VEFAT DUYURULARI (2025/2026)" kayitlari tarihsiz.
