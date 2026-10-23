(function () {
  "use strict";
  var sayiBicimi = new Intl.NumberFormat("tr-TR");

  // (1) Sayaçlar: sıfırdan hedefe, 1,4 sn ease-out
  document.querySelectorAll("[data-hedef]").forEach(function (el) {
    var hedef = parseInt(el.getAttribute("data-hedef"), 10);
    if (!isFinite(hedef) || hedef <= 0) return;
    var t0 = performance.now(), sure = 1400;
    el.textContent = sayiBicimi.format(0);
    function adim(t) {
      var k = Math.min(1, (t - t0) / sure), e = 1 - Math.pow(1 - k, 3);
      el.textContent = sayiBicimi.format(Math.round(hedef * e));
      if (k < 1) requestAnimationFrame(adim);
    }
    requestAnimationFrame(adim);
  });

  // (2) Canlı arama: yazdıkça (kısa bir beklemeyle) sonuçlar yenilenir, kutu boşalınca
  // liste kendiliğinden sıfırlanır. Sayfa yeniden yüklenmez; adres çubuğu güncellenir.
  var form = document.getElementById("ara");
  if (form && window.fetch && window.DOMParser) {
    var giris = form.querySelector('input[name="q"]');
    var temizle = form.querySelector(".ara-temizle");
    var BEKLEME = 300;
    var zamanlayici = null, denetleyici = null, sonAranan = giris.value.trim();

    var getir = function () {
      clearTimeout(zamanlayici);
      var q = giris.value.trim();
      if (q === sonAranan) return;
      sonAranan = q;
      var parametreler = new URLSearchParams(new FormData(form));
      if (q) parametreler.set("q", q); else parametreler.delete("q");
      var adres = "/?" + parametreler.toString();
      if (denetleyici) denetleyici.abort();  // eski yanıt yenisinin üstüne yazmasın
      denetleyici = window.AbortController ? new AbortController() : null;
      form.classList.add("yukleniyor");
      fetch(adres, { signal: denetleyici && denetleyici.signal })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(function (html) {
          var yeni = new DOMParser().parseFromString(html, "text/html");
          ["yillar", "sayim", "sonuclar"].forEach(function (id) {
            var kaynak = yeni.getElementById(id), hedef = document.getElementById(id);
            if (kaynak && hedef) hedef.innerHTML = kaynak.innerHTML;
          });
          history.replaceState(null, "", adres);
          form.classList.remove("yukleniyor");
        })
        .catch(function (e) {
          if (e.name === "AbortError") return;
          window.location.href = adres;  // bir şey ters giderse klasik sayfa yüklemesi
        });
    };

    var temizleGoster = function () { temizle.hidden = !giris.value; };

    giris.addEventListener("input", function () {
      temizleGoster();
      clearTimeout(zamanlayici);
      if (!giris.value.trim()) getir();  // silindi: hemen sıfırla
      else zamanlayici = setTimeout(getir, BEKLEME);
    });
    giris.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && giris.value) {
        e.stopPropagation();
        giris.value = "";
        temizleGoster();
        getir();
      }
    });
    temizle.addEventListener("click", function () {
      giris.value = "";
      temizleGoster();
      getir();
      giris.focus();
    });
    form.addEventListener("submit", function (e) { e.preventDefault(); getir(); });
  }

  // (3) Modal
  var modal = document.getElementById("modal");
  if (!modal) return;

  function metin(parent, etiket, ad, deger) {
    var e = document.createElement(etiket);
    e.textContent = deger;
    if (ad) e.className = ad;
    parent.appendChild(e);
    return e;
  }

  function tarihMetni(k) {
    if (k.tarih_hassasiyeti === "tam" && k.sehadet_tarihi) {
      var p = k.sehadet_tarihi.split("-");
      return p[2] + "." + p[1] + "." + p[0];
    }
    if (k.tarih_hassasiyeti === "yil" && k.sehadet_yili) return String(k.sehadet_yili);
    return "";
  }

  function doldur(k) {
    document.getElementById("m-ad").textContent = k.gorunen_ad;
    document.getElementById("m-gorev").textContent = k.gorev || "";
    var dl = document.getElementById("m-dl");
    dl.textContent = "";
    [["Şehadet Tarihi", tarihMetni(k)], ["Şehadet Yeri", k.sehadet_yeri], ["Memleket", k.memleket],
     ["Baba Adı", k.baba_adi], ["Kurum", k.kurum]]
      .forEach(function (s) {
        if (!s[1]) return;
        metin(dl, "dt", "", s[0]);
        metin(dl, "dd", "", s[1]);
      });
    var foto = document.getElementById("m-foto");
    foto.hidden = true;
    foto.removeAttribute("src");
    if (k.fotograf_url && /^https?:\/\//i.test(k.fotograf_url)) {
      foto.alt = k.gorunen_ad;
      foto.src = k.fotograf_url;  // yüklenince görünür; hata verirse gizli kalır
    }
    var olay = document.getElementById("m-olay");
    olay.querySelector("p").textContent = k.sehadet_olayi || "";
    olay.hidden = !k.sehadet_olayi;
    var kaynak = document.getElementById("m-kaynak");
    kaynak.textContent = "";
    if (k.kaynaklar && k.kaynaklar.length) {
      kaynak.appendChild(document.createTextNode("Kaynak: "));
      k.kaynaklar.forEach(function (ks, i) {
        if (i) kaynak.appendChild(document.createTextNode(", "));
        if (ks.url && /^https?:\/\//i.test(ks.url)) {
          var a = metin(kaynak, "a", "", ks.kaynak_adi);
          a.href = ks.url; a.target = "_blank"; a.rel = "noopener noreferrer";
        } else {
          kaynak.appendChild(document.createTextNode(ks.kaynak_adi));
        }
      });
    }
    document.getElementById("m-link").href = k.url;
  }

  var mFoto = document.getElementById("m-foto");
  mFoto.addEventListener("load", function () { if (mFoto.getAttribute("src")) mFoto.hidden = false; });
  mFoto.addEventListener("error", function () { mFoto.hidden = true; });

  function ac(id) {
    fetch("/api/sehitler/" + encodeURIComponent(id))
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (k) { doldur(k); modal.classList.add("show"); })
      .catch(function () { window.location.href = "/sehit/x-" + encodeURIComponent(id); });
  }
  function kapat() { modal.classList.remove("show"); }

  // olay yetkilendirme: canlı aramayla yenilenen satırlar da modal açar
  document.addEventListener("click", function (e) {
    var el = e.target.closest && e.target.closest("tr[data-id], .tcard[data-id]");
    if (el) ac(el.getAttribute("data-id"));
  });
  modal.addEventListener("click", function (e) { if (e.target === modal) kapat(); });
  modal.querySelector(".x").addEventListener("click", kapat);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") kapat(); });
})();
