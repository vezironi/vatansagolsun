/* Sitenin açılır menüleri: her <select>, site temasına uygun özel bir liste kutusuyla değiştirilir.
 *
 * Asıl <select> sayfada (gizli) kalır ve değeri her seçimde güncellenir; form gönderimi ve
 * "change" dinleyicileri değişmeden çalışır. JavaScript yoksa tarayıcının kendi menüsü görünür.
 * Klavye: ok tuşları, Home/End, Enter/Boşluk seçer, Esc kapatır, harf yazınca o harfe atlar.
 */
(function () {
  "use strict";
  var sayac = 0;

  function kur(select) {
    var kimlik = "secim-" + (++sayac);
    var kap = document.createElement("div");
    kap.className = "secim";
    select.parentNode.insertBefore(kap, select);
    kap.appendChild(select);
    select.classList.add("secim-yerel");
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");

    var dugme = document.createElement("button");
    dugme.type = "button";
    dugme.className = "secim-dugme";
    dugme.setAttribute("aria-haspopup", "listbox");
    dugme.setAttribute("aria-expanded", "false");
    dugme.setAttribute("aria-controls", kimlik);
    var etiket = select.getAttribute("aria-label");
    var deger = document.createElement("span");
    deger.className = "secim-deger";
    var ok = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    ok.setAttribute("class", "secim-ok");
    ok.setAttribute("viewBox", "0 0 10 6");
    ok.setAttribute("aria-hidden", "true");
    ok.innerHTML = '<path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>';
    dugme.appendChild(deger);
    dugme.appendChild(ok);

    var liste = document.createElement("ul");
    liste.className = "secim-liste";
    liste.id = kimlik;
    liste.setAttribute("role", "listbox");
    liste.tabIndex = -1;
    if (etiket) liste.setAttribute("aria-label", etiket);
    liste.hidden = true;

    var ogeler = Array.prototype.map.call(select.options, function (secenek, i) {
      var li = document.createElement("li");
      li.id = kimlik + "-" + i;
      li.setAttribute("role", "option");
      li.textContent = secenek.textContent;
      li.dataset.sira = i;
      liste.appendChild(li);
      return li;
    });
    var enUzun = ogeler.reduce(function (m, li) { return Math.max(m, li.textContent.length); }, 0);
    dugme.style.minWidth = (enUzun + 5) + "ch";  // seçim değişince düğme genişliği oynamasın
    kap.appendChild(dugme);
    kap.appendChild(liste);

    var etkin = select.selectedIndex;

    function yansit() {
      var secili = select.selectedIndex;
      deger.textContent = secili >= 0 ? select.options[secili].textContent : "";
      dugme.setAttribute("aria-label", (etiket ? etiket + ": " : "") + deger.textContent);
      ogeler.forEach(function (li, i) { li.setAttribute("aria-selected", i === secili ? "true" : "false"); });
    }

    function etkinlestir(i) {
      if (i < 0 || i >= ogeler.length) return;
      if (ogeler[etkin]) ogeler[etkin].classList.remove("etkin");
      etkin = i;
      ogeler[i].classList.add("etkin");
      liste.setAttribute("aria-activedescendant", ogeler[i].id);
      ogeler[i].scrollIntoView({ block: "nearest" });
    }

    function acik() { return !liste.hidden; }

    function ac() {
      if (acik()) return;
      document.dispatchEvent(new CustomEvent("secim:ac", { detail: kap }));
      liste.hidden = false;
      kap.classList.add("acik");
      dugme.setAttribute("aria-expanded", "true");
      etkinlestir(Math.max(select.selectedIndex, 0));
      liste.focus({ preventScroll: true });
    }

    function kapat(odakla) {
      if (!acik()) return;
      liste.hidden = true;
      kap.classList.remove("acik");
      dugme.setAttribute("aria-expanded", "false");
      if (odakla) dugme.focus();
    }

    function sec(i) {
      if (i !== select.selectedIndex) {
        select.selectedIndex = i;
        yansit();
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      kapat(true);
    }

    var aranan = "", aramaZamani = null;
    function harfleAtla(harf) {
      clearTimeout(aramaZamani);
      aranan += harf.toLocaleLowerCase("tr");
      aramaZamani = setTimeout(function () { aranan = ""; }, 600);
      // tek harf: bir sonrakinden aramaya başlar (aynı harfe basmak sıradakine geçer)
      var bas = aranan.length > 1 ? etkin : etkin + 1;
      for (var k = 0; k < ogeler.length; k++) {
        var i = (bas + k) % ogeler.length;
        if (ogeler[i].textContent.toLocaleLowerCase("tr").indexOf(aranan) === 0) { etkinlestir(i); return; }
      }
    }

    dugme.addEventListener("click", function () { if (acik()) kapat(true); else ac(); });
    dugme.addEventListener("keydown", function (e) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].indexOf(e.key) >= 0) { e.preventDefault(); ac(); }
    });

    liste.addEventListener("keydown", function (e) {
      switch (e.key) {
        case "ArrowDown": e.preventDefault(); etkinlestir(etkin + 1); break;
        case "ArrowUp": e.preventDefault(); etkinlestir(etkin - 1); break;
        case "Home": e.preventDefault(); etkinlestir(0); break;
        case "End": e.preventDefault(); etkinlestir(ogeler.length - 1); break;
        case "PageDown": e.preventDefault(); etkinlestir(Math.min(etkin + 8, ogeler.length - 1)); break;
        case "PageUp": e.preventDefault(); etkinlestir(Math.max(etkin - 8, 0)); break;
        case "Enter": case " ": e.preventDefault(); sec(etkin); break;
        case "Escape": e.preventDefault(); e.stopPropagation(); kapat(true); break;
        case "Tab": kapat(false); break;
        default:
          if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) harfleAtla(e.key);
      }
    });
    liste.addEventListener("mousemove", function (e) {
      var li = e.target.closest("li");
      if (li && Number(li.dataset.sira) !== etkin) etkinlestir(Number(li.dataset.sira));
    });
    liste.addEventListener("click", function (e) {
      var li = e.target.closest("li");
      if (li) sec(Number(li.dataset.sira));
    });
    document.addEventListener("pointerdown", function (e) { if (!kap.contains(e.target)) kapat(false); });
    document.addEventListener("secim:ac", function (e) { if (e.detail !== kap) kapat(false); });
    select.addEventListener("change", yansit);  // dışarıdan değiştirilirse de görünüm güncellenir
    if (select.form) select.form.addEventListener("reset", function () { setTimeout(yansit, 0); });

    yansit();
  }

  document.querySelectorAll("select:not([multiple])").forEach(kur);
})();
