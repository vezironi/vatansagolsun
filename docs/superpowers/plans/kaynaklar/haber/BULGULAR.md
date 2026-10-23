# Sehit haber kaynaklari - bulgular (2026-10-23, ~10:10 TR)
Istek sayisi: Hurriyet 8 (robots, tag, tag?p=2, /rss, rss/gundem, rss/sondakika, 2 makale), Sabah 6. UA: Chrome 124, aralik 2 sn. Ornekler: veri/

## 1. Hurriyet
robots.txt: `User-agent:*` yalniz /ad/ /api/ /widgets/ /_includes* /arama/ vb. yasak. /haberleri/sehit, /rss/gundem, makaleler IZINLI. (GPTBot/ClaudeBot/anthropic-ai/PerplexityBot vb. adlari `Disallow: /`; bizim UA tarayici UA'si, ama ajan kimligi olarak bildirilirse yasak.)
Anti-bot: yok (hepsi 200, captcha/cookie duvari yok). Gzip yok iken tag sayfa 149 KB, RSS 967 KB.
### Etiket sayfasi https://www.hurriyet.com.tr/haberleri/sehit
- 44 oge/sayfa, sunucu tarafi HTML. Oge: `div.tag__list__item` > `a.tag__list__item--cover[href]` (goreli URL /gundem/<slug>-<8 haneli id>), `a[data-tag=h3] h3` baslik, `a[data-tag=p] p` ozet, `a.tag__list__item--tag` etiket.
- LISTEDE TARIH YOK (ne <time> ne JSON-LD; JSON-LD yalniz BreadcrumbList). Tarih icin makaleye gitmek gerekir.
- Siralama yaklasik yeni->eski (ilk oge 20 Ekim 21:47 +03:00; id'ler 43349029, 43342055, 43341600... kabaca azalan, kesin sorted degil). Yani ilk sayfa ~3+ gunu kapsiyor ama 30 dk penceresi icin tarihsiz.
- Sayfalama: "Daha Fazla Icerik Goster" butonu JS (`#newsLoadMoreButton`, `.tag__list[total-count=10000 request-count=28 page-count=1]`). `?p=2` YOKSAYILIYOR (43/44 oge ayni). Uc nokta bulunamadi/denenmedi (/api/ robots'ta yasak) -> yalniz ilk sayfa kullanilabilir.
- Stabil id: URL sonundaki sayi (8 hane, ornek 43349029); RSS'te de ayni.
### Makale (ornek veri/h_art.html)
- JSON-LD `NewsArticle`: datePublished/dateModified ISO `2026-10-20T21:47:48+03:00` (acik +03:00), headline, description, keywords, author. `articleBody` COP (yalniz "Haberlerimizi Google'da Takip Edin...") -> kullanma. Ayrica `<meta name="datePublished" content=ISO+03:00>`.
- Govde: `.news-content` icindeki `h2` (spot) + `p` ler; gorunur tarih `span.news-date` "Olusturulma Tarihi: Ekim 20, 2026 21:47".
### RSS (cok daha ucuz/sade): https://www.hurriyet.com.tr/rss/gundem
- application/rss+xml, 100 item, pubDate azalan, AMA kuyrukta 2020'ye kadar eski haberler karisik (64'u 2026, ~51'i son 3 gun). 30 dk ve 3 gun penceresi birinci istekte kapsanir (en yeni 07:02Z = 10:02 TR).
- Alanlar: title, link (=guid, /gundem/<slug>-<id>), description, pubDate ("Fri, 23 Oct 2026 07:02:00 Z" -> gercekten UTC; dc:modified/dateTimeWritten "+00:00"), category/subcategory, `<text>` (HTML govde, tam metin!), abstract. Xpath: `//item`. Ad alani `https://purl.org/...` (https!) dikkat.
- Sehit filtresi olan feed YOK. Tum feed'te "sehit" gecen 1 item (istemci filtresi: baslik+description+text'te regex sehit|sehid|şehit). /rss ve /rss/sondakika RSS DEGIL (son-dakika HTML sayfasina yonlendiriyor, 158 KB). Boyut 967 KB -> tek istek ama agir; Accept-Encoding gzip kullan.
- Oneri: 30 dk'da bir /rss/gundem (guid'e gore dedupe) + istemci tarafi sehit filtresi; kacirilanlar/yedek icin gunde birkac kez /haberleri/sehit ilk sayfa (id seti farki -> yeni ID'lerin makalesini cek).

## 2. Sabah
robots.txt: `Disallow: /arama`, /get/arama, /json, /ajax, /partial/, */infinite/*, /iframe/*. IZINLI: /rss/*.xml, /haberleri/sehit, makaleler. Sitemap: /sitemap/news.xml, /sitemap/index.xml (denenmedi). Anti-bot yok (hepsi 200).
### Etiket sayfasi https://www.sabah.com.tr/haberleri/sehit (264 KB)
- ESKI->YENI DEGIL, ilgiye gore karisik: ilk kart 2026/10/07 (Pursaklar polis), sonra 2024 haberleri. "Guncelleme Tarihi: 22.10.2026 00:00" sabit. Haber basina tarih sadece URL'de (/gundem/2026/10/07/..) -> yeni-haber toplayici icin GUVENILMEZ. ~9 benzersiz makale, cogu eski. Sayfalama "infinite" (robots yasak).
### RSS (izinli ve tarihli)
- https://www.sabah.com.tr/rss/gundem.xml: 10 item, 16 KB, ~11 saat (09:20 -> onceki gun 23:53 +03:00). https://www.sabah.com.tr/rss/sondakika.xml: 23 item, 23 KB, 4 saat (10:10 -> 06:40). Yeni->eski. Diger feed listesi: /rss-bilgi (yonlendirilen /rss): /rss/anasayfa.xml, /rss/turkiye.xml?(dizinde il bazli: /rss/ankara.xml vb., /rss/dunya.xml, /rss/ekonomi.xml...). "sehit" etiketli feed YOK; 0/33 item sehit iceriyordu bugun.
- Alanlar: title, link (=guid), description (gundem'de `<img>` + HTML, sondakika'da duz metin), category, pubDate `Fri, 23 Oct 2026 09:20:31 +0300` (acik +03:00), enclosure/content (gundem). Xpath `//item`. Stabil id: gundem linkinde yok (tarih+slug), makale URL'si /yasam/<slug>-7675335 -> sondaki 7 hane id; yoksa guid=URL kullan.
- Kapsam: 10-23 item = 30 dk icin yeter, 3 gunluk catch-up icin YETMEZ (sondakika ~4 saat).
### Makale (veri/s_art.html)
- JSON-LD NewsArticle: datePublished `2026-10-07T01:13:16+03:00`, dateModified, dateCreated, headline, description, `articleBody` DOLU (duz metin), keywords, author. Govde ayrica `div.newsBox > p`. Meta datePublished da var.
- Arama: /arama yasak -> kullanma.

## 3. AA ve TRT (izinli, tarihli)
- AA robots: `Allow: /`, yasak /api/, /*?s=*. Feed: https://www.aa.com.tr/tr/rss/default?cat=guncel -> 30 item, 22 KB, pubDate `+0300`, alanlar guid (sayisal id, orn 4098028), link, title, description, image. ~8 saat. Bugun 0 sehit. (cat=turkiye denenmedi.) `?s=` yasak ama `?cat=` degil.
- TRT robots: `Allow: /`, yasak /arama.html. Feed: https://www.trthaber.com/sondakika.rss -> 50 item, 54 KB, pubDate `+0300`, alanlar title, link (.../<slug>-960972.html; id=960972), description (bosluklu), category, guid=link, imageUrl. ~17 saat; 1 sehit item ("Sehit ve gazi cocuklarina 609 milyon TL'lik egitim destegi", 22 Ekim 18:42). Hurriyet'ten farkli: filtre yok, istemci regex.
- Anti-bot yok. Ikisi de resmi egilimli, sagduyulu: AA/TRT RSS en iyi yeni-haber sinyali (10 sn parse, tarih acik).

## Genel oneri
- 30 dk toplayici: RSS'ler (Sabah sondakika+gundem, Hurriyet gundem, TRT sondakika, AA guncel) -> pubDate ISO'ya cevir, baslik+ozet+(varsa body)'de `şehit|sehit|şehid|şehadet` regex (Turkce i/İ dikkat: casefold oncesi `.replace('İ','i').replace('I','ı')`), sonra yalniz eslesen makalelerden JSON-LD datePublished + body cek.
- 3 gun catch-up: yalniz Hurriyet RSS (100 item) kapsiyor; Sabah/AA/TRT icin 3 gun karsilamaz; Hurriyet etiket sayfasi ilk 44 haber ~3+ gun (tarihsiz) -> makale tarihi cek.
- Tekrarlar: ayni olay 4 kaynakta farkli URL/baslikla gelir; id'ler kaynaklar arasi ortak degil -> kaynak+id/URL ile dedupe, olay-bazli birlestirme ayri (tarih+isim+yer) gerekir. Hurriyet RSS ile etiket sayfasi ayni id uzayini kullanir.

## 4. Uygulama notları (Plan 3 Task 2)
- Hürriyet makalesinde `.news-content` yalnızca gövde `p` etiketlerini taşır; spot `h2` kardeş `.news-content__inf` içindedir (gövdeye dahil edilmez; özet RSS'te var).
- Sabah makale gövdesi JSON-LD `articleBody`den alınır (`div.newsBox p` sonunda "Sabah.com.tr Uygulamamızı İndirin" çöpü var); JSON-LD yoksa seçiciye düşülür.
- DOĞRULANMADI: AA (`div.detay-icerik`) ve TRT (`div.news-content`) makale gövde seçicileri. Araştırmada bu sitelerden yalnızca RSS örneği alındı, makale sayfası alınmadı; seçiciler tahmindir. İki kaynak varsayılan kapalıdır; açmadan önce gerçek bir makale sayfasıyla doğrulanmalı.
- Sabah RSS bağlantılarında sayısal kimlik yok: `kimlik` = guid/URL. AA'da URL `/4098028` ile biter (tiresiz), kimlik guid'den gelir.
