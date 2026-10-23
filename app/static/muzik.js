/* Sitenin sol altındaki minimal müzik çalar (HTML5 <audio>, sitemizden sunulan MP3).
 *
 * Sayfa açılınca çalmayı dener. Tarayıcılar etkileşimsiz sesli oynatmayı engellerse
 * ziyaretçinin sayfadaki ilk tıklaması / dokunuşu / tuş basışıyla başlar. Ziyaretçi
 * duraklatırsa bu tercih hatırlanır ve sonraki sayfalarda kendiliğinden başlamaz.
 * Sayfa değişince kaldığı saniyeden devam eder.
 */
(function () {
  var kok = document.getElementById("muzik");
  if (!kok) return;
  var ANAHTAR = "vatansagolsun.muzik";
  var ses = document.getElementById("muzik-ses-dosyasi");
  var oynat = document.getElementById("muzik-oynat");
  var sessiz = document.getElementById("muzik-sessiz");
  var kaydirici = document.getElementById("muzik-ses");
  var varsayilan = Number(kok.dataset.ses);
  var ETKILESIMLER = ["pointerdown", "keydown", "touchstart"];
  var durum = oku();

  function oku() {
    try { return JSON.parse(localStorage.getItem(ANAHTAR)) || {}; } catch (e) { return {}; }
  }
  function yaz() {
    try { localStorage.setItem(ANAHTAR, JSON.stringify(durum)); } catch (e) { /* özel pencere vb. */ }
  }

  var duzey = typeof durum.ses === "number" ? durum.ses : (isNaN(varsayilan) ? 0.4 : varsayilan);
  ses.volume = Math.min(1, Math.max(0, duzey));
  ses.muted = !!durum.sessiz;
  kaydirici.value = Math.round(ses.volume * 100);

  function guncelle() {
    var caliyor = !ses.paused;
    kok.classList.toggle("caliyor", caliyor);
    oynat.setAttribute("aria-label", caliyor ? "Duraklat" : "Oynat");
    var kapali = ses.muted || ses.volume === 0;
    kok.classList.toggle("sessizde", kapali);
    sessiz.setAttribute("aria-label", kapali ? "Sesi aç" : "Sesi kapat");
  }

  function kaldigiYer() {
    if (typeof durum.saniye === "number" && ses.currentTime < 1 && (!ses.duration || durum.saniye < ses.duration)) {
      try { ses.currentTime = durum.saniye; } catch (e) { /* meta veri gelince ayarlanır */ }
    }
  }

  function cal() {
    kaldigiYer();
    var p = ses.play();
    if (p && p.catch) { p.catch(function () { ilkEtkilesimdeCal(); guncelle(); }); }
  }

  function etkilesimdeBaslat(e) {
    // Çaların kendi düğmelerine yapılan tıklama zaten kendi işini görür.
    if (kok.contains(e.target)) return;
    birak();
    if (ses.paused && !durum.durdurdu) { cal(); }
  }
  function ilkEtkilesimdeCal() {
    ETKILESIMLER.forEach(function (t) { document.addEventListener(t, etkilesimdeBaslat, { capture: true }); });
  }
  function birak() {
    ETKILESIMLER.forEach(function (t) { document.removeEventListener(t, etkilesimdeBaslat, { capture: true }); });
  }

  ses.addEventListener("loadedmetadata", kaldigiYer);
  ses.addEventListener("play", function () { birak(); guncelle(); });
  ses.addEventListener("pause", function () { durum.saniye = ses.currentTime; yaz(); guncelle(); });
  ses.addEventListener("volumechange", guncelle);

  oynat.addEventListener("click", function () {
    if (ses.paused) { durum.durdurdu = false; yaz(); cal(); }
    else { durum.durdurdu = true; yaz(); ses.pause(); }
  });
  sessiz.addEventListener("click", function () {
    if (ses.muted || ses.volume === 0) {
      ses.muted = false;
      if (ses.volume === 0) { ses.volume = 0.4; kaydirici.value = 40; }
    } else { ses.muted = true; }
    durum.sessiz = ses.muted; durum.ses = ses.volume; yaz();
  });
  kaydirici.addEventListener("input", function () {
    ses.volume = Number(kaydirici.value) / 100;
    if (ses.volume > 0 && ses.muted) { ses.muted = false; }
    durum.ses = ses.volume; durum.sessiz = ses.muted; yaz();
  });
  window.addEventListener("pagehide", function () {
    if (!ses.paused) { durum.saniye = ses.currentTime; yaz(); }
  });

  guncelle();
  if (!durum.durdurdu) { cal(); }
})();
