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
      var star = btn.querySelector(".fav-star");
      if (star) star.textContent = res.favorito ? "★" : "☆";
    }).catch(function () { window.showToast("Erro ao favoritar", ""); });
  });

  // ---------- Selecionar vários versículos (grifo em lote) ----------
  var selectModeBtn = document.getElementById("selectModeBtn");
  var selectBar = document.getElementById("selectBar");
  var selectCount = document.getElementById("selectCount");
  var selecting = false;
  var selected = [];

  function updateSelectBar() {
    selectCount.textContent = selected.length;
    selectBar.hidden = selected.length === 0;
  }

  function toggleSelectMode(force) {
    selecting = typeof force === "boolean" ? force : !selecting;
    versesEl.classList.toggle("select-mode", selecting);
    selectModeBtn.setAttribute("aria-pressed", String(selecting));
    selectModeBtn.classList.toggle("is-active", selecting);
    if (!selecting) {
      selected.forEach(function (li) { li.classList.remove("is-selected"); });
      selected = [];
      updateSelectBar();
      closePop();
    }
  }

  function toggleVerseSelection(li) {
    var idx = selected.indexOf(li);
    if (idx >= 0) {
      selected.splice(idx, 1);
      li.classList.remove("is-selected");
    } else {
      selected.push(li);
      li.classList.add("is-selected");
    }
    updateSelectBar();
  }

  selectModeBtn.addEventListener("click", function () { toggleSelectMode(); });

  versesEl.addEventListener("click", function (ev) {
    if (!selecting) return;
    if (ev.target.closest(".verse-act")) return; // botoes individuais desativados durante selecao
    var li = ev.target.closest(".verse");
    if (!li) return;
    ev.preventDefault();
    toggleVerseSelection(li);
  });

  document.getElementById("selectClear").addEventListener("click", function () {
    selected.forEach(function (li) { li.classList.remove("is-selected"); });
    selected = [];
    updateSelectBar();
  });

  document.getElementById("selectDone").addEventListener("click", function () { toggleSelectMode(false); });

  selectBar.querySelectorAll(".swatch").forEach(function (sw) {
    sw.addEventListener("click", function () {
      if (!selected.length) return;
      var cor = sw.dataset.cor || null;
      var alvo = selected.slice();
      var numeros = alvo.map(function (li) { return Number(li.dataset.verse); });
      window.postJSON("/api/estudo/grifo-lote", {
        abbrev: ABBREV, capitulo: CHAPTER, versiculos: numeros, cor: cor
      }).then(function () {
        alvo.forEach(function (li) {
          COLORS.forEach(function (c) { li.classList.remove("hl-" + c); });
          if (cor) li.classList.add("hl-" + cor);
          li.classList.remove("is-selected");
        });
        selected = [];
        updateSelectBar();
        window.showToast(cor ? numeros.length + " versículos grifados" : "Grifos removidos", "");
      }).catch(function () { window.showToast("Erro ao grifar em lote", ""); });
    });
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

  // ---------- Estudar o Capítulo ----------
  var studyBtn = document.getElementById("studyTabBtn");
  var studyOverlay = document.getElementById("studyOverlay");
  var studyCloseBtn = document.getElementById("studyCloseBtn");
  var studyConfirm = document.getElementById("studyConfirm");
  var studyLoading = document.getElementById("studyLoading");
  var studyContentEl = document.getElementById("studyContent");
  var studyEmptyEl = document.getElementById("studyEmpty");
  var studyEmptyText = document.getElementById("studyEmptyText");
  var studyCancelBtn = document.getElementById("studyCancelBtn");
  var studyConfirmBtn = document.getElementById("studyConfirmBtn");
  var studyConfirmClose = document.getElementById("studyConfirmClose");
  var studyRetryBtn = document.getElementById("studyRetryBtn");
  var studyCache = null;
  var studyController = null;
  var studyTimer = null;

  function abortStudy() {
    if (studyTimer) { clearTimeout(studyTimer); studyTimer = null; }
    if (studyController) { studyController.abort(); studyController = null; }
  }

  // Abrir: NUNCA carrega automaticamente — mostra a confirmação primeiro
  // (ou o conteúdo, se já tiver sido carregado nesta visita).
  function openStudy() {
    studyOverlay.hidden = false;
    document.body.classList.add("study-open");
    if (studyCache && studyCache.disponivel) { renderStudy(studyCache); return; }
    setStudyState("confirm");
  }
  function closeStudy() {
    abortStudy();
    studyOverlay.hidden = true;
    document.body.classList.remove("study-open");
  }
  function setStudyState(state) {
    if (studyConfirm) studyConfirm.hidden = state !== "confirm";
    studyLoading.hidden = state !== "loading";
    studyContentEl.hidden = state !== "content";
    studyEmptyEl.hidden = state !== "empty";
  }
  function renderStudy(data) {
    if (!data || !data.disponivel) {
      studyEmptyText.textContent = (data && data.motivo) || "Não foi possível carregar o estudo deste capítulo.";
      if (studyRetryBtn) studyRetryBtn.hidden = false;
      setStudyState("empty");
      return;
    }
    document.getElementById("studyResumo").innerHTML = paragraphsHtml(data.resumo);
    document.getElementById("studyContexto").innerHTML = paragraphsHtml(data.contexto);
    fillList(document.getElementById("studyMensagens"), data.mensagens);
    fillList(document.getElementById("studyPerguntas"), data.perguntas);
    setStudyState("content");
  }
  function paragraphsHtml(text) {
    if (!text) return "";
    return String(text).split(/\n+/).filter(Boolean).map(function (p) {
      return "<p>" + escapeHtml(p) + "</p>";
    }).join("");
  }
  function fillList(el, items) {
    el.innerHTML = "";
    (items || []).forEach(function (item) {
      var li = document.createElement("li");
      li.textContent = item;
      el.appendChild(li);
    });
  }
  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }
  function showStudyError(msg) {
    abortStudy();
    studyEmptyText.textContent = msg;
    if (studyRetryBtn) studyRetryBtn.hidden = false;
    setStudyState("empty");
  }
  function loadStudy() {
    abortStudy();
    setStudyState("loading");
    studyController = new AbortController();
    // Timeout de segurança: nunca fica carregando para sempre.
    studyTimer = setTimeout(function () {
      if (studyController) studyController.abort();
      showStudyError("O carregamento demorou mais que o esperado. Verifique sua conexão e tente novamente.");
    }, 15000);

    fetch("/api/estudo-capitulo/" + ABBREV + "/" + CHAPTER, {
      signal: studyController.signal,
      headers: { "Accept": "application/json" },
      credentials: "same-origin"
    })
      .then(function (r) {
        // Sessão expirada: a API redireciona para o login (HTML), não JSON.
        if (r.redirected || (r.headers.get("Content-Type") || "").indexOf("application/json") === -1) {
          throw new Error("sessao");
        }
        return r.json();
      })
      .then(function (data) {
        if (studyTimer) { clearTimeout(studyTimer); studyTimer = null; }
        studyController = null;
        studyCache = data;
        renderStudy(data);
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") return; // cancelado/timeout já tratado
        if (studyTimer) { clearTimeout(studyTimer); studyTimer = null; }
        studyController = null;
        if (err && err.message === "sessao") {
          showStudyError("Sua sessão expirou. Recarregue a página e faça login novamente.");
        } else {
          showStudyError("Não foi possível carregar o estudo agora. Tente novamente.");
        }
      });
  }

  var studyEndBtn = document.getElementById("studyEndBtn");
  if (studyBtn) studyBtn.addEventListener("click", openStudy);
  if (studyEndBtn) studyEndBtn.addEventListener("click", openStudy);
  if (studyCloseBtn) studyCloseBtn.addEventListener("click", closeStudy);
  if (studyConfirmClose) studyConfirmClose.addEventListener("click", closeStudy);
  if (studyConfirmBtn) studyConfirmBtn.addEventListener("click", loadStudy);
  if (studyCancelBtn) studyCancelBtn.addEventListener("click", function () { abortStudy(); setStudyState("confirm"); });
  if (studyRetryBtn) studyRetryBtn.addEventListener("click", loadStudy);
  if (studyOverlay) studyOverlay.addEventListener("click", function (ev) {
    if (ev.target === studyOverlay) closeStudy();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && !studyOverlay.hidden) closeStudy();
  });

  // ---------- Reflexão do capítulo: "O que Deus falou comigo" ----------
  var reflexao = document.getElementById("chapterReflection");
  var reflexaoStatus = document.getElementById("reflexaoStatus");
  if (reflexao) {
    var reflexaoTimer = null;
    var setReflexaoStatus = function (text, saved) {
      if (!reflexaoStatus) return;
      reflexaoStatus.textContent = text;
      reflexaoStatus.classList.toggle("is-saved", Boolean(saved));
    };
    reflexao.addEventListener("input", function () {
      clearTimeout(reflexaoTimer);
      setReflexaoStatus("Salvando…", false);
      reflexaoTimer = setTimeout(function () {
        window.postJSON("/api/estudo/reflexao", {
          abbrev: reflexao.dataset.abbrev,
          capitulo: Number(reflexao.dataset.chapter),
          texto: reflexao.value
        }).then(function () {
          setReflexaoStatus("Salvo automaticamente", true);
        }).catch(function () {
          setReflexaoStatus("Não foi possível salvar", false);
        });
      }, 600);
    });
  }
})();
