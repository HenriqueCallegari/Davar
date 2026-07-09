/* Página de leitura: grifos, notas, favoritos, TTS, foco, pomodoro e progresso. */
(function () {
  "use strict";

  var versesEl = document.getElementById("verses");
  if (!versesEl) return;

  var ABBREV = versesEl.dataset.abbrev;
  var BOOK = versesEl.dataset.book;
  var CHAPTER = Number(versesEl.dataset.chapter);
  var PLANO = versesEl.dataset.plano ? Number(versesEl.dataset.plano) : null;
  var COLORS = ["amarelo", "azul", "verde", "vermelho", "roxo"];
  var verseItems = Array.prototype.slice.call(versesEl.querySelectorAll(".verse"));

  // ---------- Fonte ----------
  var size = parseInt(localStorage.getItem("kja_font") || "20", 10);
  function applyFont() {
    versesEl.querySelectorAll(".verse__text").forEach(function (el) { el.style.fontSize = size + "px"; });
    try { localStorage.setItem("kja_font", size); } catch (e) {}
  }
  document.getElementById("fontUp").addEventListener("click", function () { size = Math.min(34, size + 1); applyFont(); });
  document.getElementById("fontDown").addEventListener("click", function () { size = Math.max(13, size - 1); applyFont(); });
  applyFont();

  // ---------- Modo foco ----------
  document.getElementById("focusBtn").addEventListener("click", function () {
    document.body.classList.toggle("focus-mode");
  });

  // ---------- Copiar ----------
  versesEl.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".copy-btn");
    if (!btn) return;
    var li = btn.closest(".verse");
    var text = li.querySelector(".verse__text").innerText.trim() + " (" + BOOK + " " + CHAPTER + ":" + li.dataset.verse + ")";
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () { window.showToast("Versículo copiado", ""); });
  });

  // ---------- Favoritar ----------
  versesEl.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".fav-btn");
    if (!btn) return;
    var li = btn.closest(".verse");
    window.postJSON("/api/estudo/favorito", {
      abbrev: ABBREV, capitulo: CHAPTER, versiculo: Number(li.dataset.verse)
    }).then(function (res) {
      li.classList.toggle("is-fav", res.favorito);
      btn.textContent = res.favorito ? "★" : "☆";
    }).catch(function () { window.showToast("Erro ao favoritar", ""); });
  });

  // ---------- Popover de marcação ----------
  var pop = document.getElementById("markPop");
  var noteField = document.getElementById("markNote");
  var current = null;

  function openPop(li) {
    if (current) current.classList.remove("is-open");
    current = li;
    li.classList.add("is-open");
    var noteEl = li.querySelector(".verse-note");
    noteField.value = noteEl ? noteEl.textContent.trim() : "";
    COLORS.forEach(function (c) {
      var sw = pop.querySelector(".swatch." + c);
      sw.classList.toggle("sel", li.classList.contains("hl-" + c));
    });
    var rect = li.getBoundingClientRect();
    pop.style.top = (window.scrollY + rect.bottom + 8) + "px";
    pop.style.left = Math.max(12, Math.min(window.scrollX + rect.left, window.scrollX + window.innerWidth - 280)) + "px";
    pop.classList.add("show");
  }
  function closePop() {
    pop.classList.remove("show");
    if (current) current.classList.remove("is-open");
    current = null;
  }

  versesEl.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".mark-btn");
    if (!btn) return;
    openPop(btn.closest(".verse"));
  });
  document.getElementById("closePop").addEventListener("click", closePop);
  document.addEventListener("click", function (ev) {
    if (current && !pop.contains(ev.target) && !ev.target.closest(".mark-btn")) closePop();
  });

  pop.querySelectorAll(".swatch").forEach(function (sw) {
    sw.addEventListener("click", function () {
      if (!current) return;
      var cor = sw.dataset.cor || null;
      var li = current;
      window.postJSON("/api/estudo/grifo", {
        abbrev: ABBREV, capitulo: CHAPTER, versiculo: Number(li.dataset.verse), cor: cor
      }).then(function () {
        COLORS.forEach(function (c) { li.classList.remove("hl-" + c); });
        pop.querySelectorAll(".swatch").forEach(function (s) { s.classList.remove("sel"); });
        if (cor) { li.classList.add("hl-" + cor); sw.classList.add("sel"); }
        window.showToast(cor ? "Versículo grifado" : "Grifo removido", "");
      }).catch(function () { window.showToast("Erro ao grifar", ""); });
    });
  });

  document.getElementById("saveNote").addEventListener("click", function () {
    if (!current) return;
    var li = current;
    var texto = noteField.value;
    window.postJSON("/api/estudo/nota", {
      abbrev: ABBREV, capitulo: CHAPTER, versiculo: Number(li.dataset.verse), texto: texto, tags: ""
    }).then(function () {
      li.querySelector(".verse-note").textContent = texto.trim();
      window.showToast(texto.trim() ? "Anotação salva" : "Anotação removida", "");
      closePop();
    }).catch(function () { window.showToast("Erro ao salvar nota", ""); });
  });

  // ---------- TTS versículo a versículo ----------
  var ttsBtn = document.getElementById("ttsBtn");
  var ttsPause = document.getElementById("ttsPause");
  var voice = null;
  function loadVoices() {
    var voices = window.speechSynthesis ? speechSynthesis.getVoices() : [];
    voice = voices.filter(function (v) { return v.lang === "pt-BR"; })[0] ||
            voices.filter(function (v) { return v.lang.indexOf("pt") === 0; })[0] || voices[0];
  }
  if (window.speechSynthesis) { speechSynthesis.onvoiceschanged = loadVoices; loadVoices(); }

  function clearTts() { verseItems.forEach(function (li) { li.classList.remove("tts-active"); }); }
  function speakFrom(i) {
    if (i >= verseItems.length) { clearTts(); ttsBtn.textContent = " Ouvir"; return; }
    var li = verseItems[i];
    var text = li.querySelector(".verse__text").innerText.trim();
    clearTts();
    li.classList.add("tts-active");
    li.scrollIntoView({ behavior: "smooth", block: "center" });
    var u = new SpeechSynthesisUtterance(text);
    u.lang = "pt-BR"; if (voice) u.voice = voice; u.rate = 0.95; u.pitch = 1.05;
    u.onend = function () { if (ttsBtn.textContent.indexOf("Tocando") >= 0) speakFrom(i + 1); };
    speechSynthesis.speak(u);
  }
  if (ttsBtn) ttsBtn.addEventListener("click", function () {
    if (!window.speechSynthesis) { window.showToast("Áudio não suportado", ""); return; }
    if (speechSynthesis.speaking || speechSynthesis.pending) { speechSynthesis.cancel(); clearTts(); ttsBtn.textContent = " Ouvir"; return; }
    ttsBtn.textContent = " Tocando"; speakFrom(0);
  });
  if (ttsPause) ttsPause.addEventListener("click", function () {
    if (!window.speechSynthesis) return;
    if (speechSynthesis.speaking && !speechSynthesis.paused) speechSynthesis.pause();
    else if (speechSynthesis.paused) speechSynthesis.resume();
  });

  // ---------- Barra de rolagem + auto-marcar ----------
  var bar = document.getElementById("scrollProgress");
  var marked = false, scrolled = false;
  function autoMark() {
    if (marked) return;
    marked = true;
    try { localStorage.setItem("kja_read_" + ABBREV + "_" + CHAPTER, "1"); } catch (e) {}
    if (PLANO) {
      window.postJSON("/api/planos/" + PLANO + "/progresso", { livro: BOOK, capitulo: CHAPTER, concluido: true })
        .then(function (d) {
          window.showToast("Capítulo marcado como lido", "✓");
          (d.new_achievements || []).forEach(function (a) { window.showToast("Conquista: " + a.nome, a.icone || ""); });
        }).catch(function () {});
    } else {
      window.showToast("Leitura concluída", "✓");
    }
  }
  function onScroll() {
    var doc = document.documentElement;
    var h = doc.scrollHeight - doc.clientHeight;
    var pct = h > 0 ? Math.min(100, (window.scrollY / h) * 100) : 0;
    if (bar) bar.style.width = pct + "%";
    if (pct >= 92) autoMark();
  }
  window.addEventListener("scroll", function () { scrolled = true; onScroll(); }, { passive: true });
  onScroll();
  setTimeout(function () {
    var doc = document.documentElement;
    if (doc.scrollHeight - doc.clientHeight < 40 && !scrolled) autoMark();
  }, 20000);

  // ---------- Pomodoro ----------
  var pomBtn = document.getElementById("pomodoro");
  var pomLabel = document.getElementById("pomodoroLabel");
  var remaining = 25 * 60, timer = null;
  function fmt(s) { return String((s / 60) | 0).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); }
  function render() { pomLabel.textContent = "Foco " + fmt(remaining); }
  function beep() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination); o.frequency.value = 660; g.gain.value = 0.12;
      o.start(); o.stop(ctx.currentTime + 0.6);
    } catch (e) {}
  }
  pomBtn.addEventListener("click", function () {
    if (timer) { clearInterval(timer); timer = null; pomBtn.classList.remove("running"); remaining = 25 * 60; render(); return; }
    pomBtn.classList.add("running");
    timer = setInterval(function () {
      remaining--; render();
      if (remaining <= 0) { clearInterval(timer); timer = null; pomBtn.classList.remove("running"); remaining = 25 * 60; render(); beep(); window.showToast("Sessão de foco concluída!", ""); }
    }, 1000);
  });
  render();
})();
