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

  // (2) Modal
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
    [["Şehadet Tarihi", tarihMetni(k)], ["Memleket", k.memleket], ["Baba Adı", k.baba_adi], ["Kurum", k.kurum]]
      .forEach(function (s) {
        if (!s[1]) return;
        metin(dl, "dt", "", s[0]);
        metin(dl, "dd", "", s[1]);
      });
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

  function ac(id) {
    fetch("/api/sehitler/" + encodeURIComponent(id))
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (k) { doldur(k); modal.classList.add("show"); })
      .catch(function () { window.location.href = "/sehit/x-" + encodeURIComponent(id); });
  }
  function kapat() { modal.classList.remove("show"); }

  document.querySelectorAll("tr[data-id], .tcard[data-id]").forEach(function (el) {
    el.addEventListener("click", function () { ac(el.getAttribute("data-id")); });
  });
  modal.addEventListener("click", function (e) { if (e.target === modal) kapat(); });
  modal.querySelector(".x").addEventListener("click", kapat);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") kapat(); });
})();
