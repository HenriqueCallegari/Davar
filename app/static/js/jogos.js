/* Jogos gerados a partir do texto bíblico: completar, montar, relâmpago e pares.
   Cada jogo recebe os itens de /api/jogos/<slug> e monta a própria interface. */
(function () {
  "use strict";

  var root = document.getElementById("game");
  if (!root) return;
  var SLUG = root.dataset.game;
  var live = document.getElementById("gameLive");

  // ---------- utilidades ----------
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }
  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }
  function announce(text) { if (live) live.textContent = text; }
  function bestGet(key) { try { return Number(localStorage.getItem("davar_best_" + key) || 0); } catch (e) { return 0; } }
  function bestSet(key, value) { try { localStorage.setItem("davar_best_" + key, String(value)); } catch (e) {} }
  function party() { if (window.confetti) window.confetti(); }

  function chapterUrl(item) {
    return "/livro/" + item.abbrev + "/capitulo/" + item.capitulo + "#v" + item.versiculo;
  }
  function refLink(item) {
    var a = el("a", "game-ref-link", item.referencia + " — ler no capítulo →");
    a.href = chapterUrl(item);
    return a;
  }

  // Barra de placar: [{key, label, value}] -> { set(key, value) }
  function scorebar(items) {
    var wrap = el("div", "quiz-scorebar");
    var cells = {};
    items.forEach(function (it) {
      var cell = el("div", "card");
      cell.appendChild(el("span", null, it.label));
      var strong = el("strong", null, String(it.value));
      cell.appendChild(strong);
      wrap.appendChild(cell);
      cells[it.key] = strong;
    });
    return { node: wrap, set: function (key, value) { if (cells[key]) cells[key].textContent = String(value); } };
  }

  function endCard(title, text, onAgain) {
    var card = el("div", "card quiz-end");
    card.appendChild(el("h2", null, title));
    card.appendChild(el("p", null, text));
    var actions = el("div", "quiz-actions");
    actions.style.justifyContent = "center";
    var again = el("button", "btn btn--primary", "Jogar de novo");
    again.type = "button";
    again.addEventListener("click", onAgain);
    var back = el("a", "btn btn--ghost", "Outros jogos");
    back.href = "/jogos";
    actions.appendChild(again);
    actions.appendChild(back);
    card.appendChild(actions);
    return card;
  }

  function load(callback) {
    var params = new URLSearchParams();
    if (root.dataset.livro) params.set("livro", root.dataset.livro);
    if (root.dataset.capitulo) params.set("capitulo", root.dataset.capitulo);
    if (root.dataset.diario) params.set("diario", "1");
    root.replaceChildren(el("p", "muted", "Carregando…"));
    fetch("/api/jogos/" + SLUG + "?" + params.toString(), { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) {
        if (r.status === 401) { window.location.href = "/login?next=" + encodeURIComponent(location.pathname + location.search); throw new Error("sessao"); }
        if (!r.ok) throw new Error("falha");
        return r.json();
      })
      .then(function (data) {
        if (!data.itens || !data.itens.length) {
          root.replaceChildren(el("div", "empty-state", "Não há versículos suficientes aqui para este jogo. Tente com toda a Bíblia."));
          return;
        }
        callback(data.itens);
      })
      .catch(function (err) {
        if (err && err.message === "sessao") return;
        root.replaceChildren(el("div", "empty-state", "Não foi possível carregar o jogo. Tente de novo."));
      });
  }

  // ======================================================================
  // COMPLETE O VERSÍCULO
  // ======================================================================
  function playCompletar(itens) {
    var i = 0, acertos = 0, seq = 0, best = bestGet("completar_seq"), answered = false;
    var bar = scorebar([
      { key: "q", label: "Pergunta", value: "1/" + itens.length },
      { key: "ok", label: "Acertos", value: 0 },
      { key: "seq", label: "Sequência", value: 0 },
      { key: "best", label: "Recorde", value: best }
    ]);
    var card = el("article", "card quiz-card");
    var verse = el("p", "quiz-verse");
    var refLine = el("p", "quiz-reference");
    var options = el("div", "quiz-options");
    var actions = el("div", "quiz-actions");
    var next = el("button", "btn btn--primary", "Próxima →");
    next.type = "button"; next.disabled = true;
    var feedback = el("span", "save-status");
    actions.appendChild(next); actions.appendChild(feedback);
    card.appendChild(verse); card.appendChild(refLine); card.appendChild(options); card.appendChild(actions);
    root.replaceChildren(bar.node, card);

    function show() {
      answered = false;
      var q = itens[i];
      bar.set("q", (i + 1) + "/" + itens.length);
      verse.replaceChildren(
        document.createTextNode("“" + q.antes),
        el("span", "blank", "_____"),
        document.createTextNode(q.depois + "”")
      );
      refLine.replaceChildren(); refLine.classList.remove("show");
      feedback.textContent = ""; feedback.classList.remove("is-saved");
      next.disabled = true;
      options.replaceChildren();
      q.opcoes.forEach(function (word) {
        var b = el("button", "quiz-option", word);
        b.type = "button";
        b.addEventListener("click", function () { answer(b, word, q); });
        options.appendChild(b);
      });
    }
    function answer(btn, choice, q) {
      if (answered) return; answered = true;
      var right = choice === q.correta;
      Array.prototype.forEach.call(options.children, function (b) {
        b.disabled = true;
        if (b.textContent === q.correta) b.classList.add("correct");
        else if (b === btn) b.classList.add("wrong");
      });
      var blank = verse.querySelector(".blank");
      blank.textContent = q.correta;
      blank.classList.add("filled", right ? "right" : "wrong");
      if (right) { acertos++; seq++; feedback.textContent = "Isso mesmo!"; feedback.classList.add("is-saved"); }
      else { seq = 0; feedback.textContent = "A palavra era “" + q.correta + "”."; }
      if (seq > best) { best = seq; bestSet("completar_seq", best); }
      bar.set("ok", acertos); bar.set("seq", seq); bar.set("best", best);
      refLine.replaceChildren(refLink(q)); refLine.classList.add("show");
      next.disabled = false; next.focus();
      announce(right ? "Resposta certa" : "Resposta errada. A palavra era " + q.correta);
    }
    next.addEventListener("click", function () {
      i++;
      if (i >= itens.length) finish(); else show();
    });
    function finish() {
      var pct = Math.round((acertos / itens.length) * 100);
      if (pct >= 80) party();
      if (root.dataset.diario) {  // marca o desafio do dia como concluído neste aparelho
        try {
          var d = new Date();
          localStorage.setItem("davar_diario_" + d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate(), "1");
        } catch (e) {}
      }
      var msg = pct === 100 ? "Perfeito! A Palavra está no seu coração." :
        pct >= 70 ? "Muito bom! Você conhece bem o texto." :
        pct >= 40 ? "Bom caminho — reler esses versículos vai ajudar." : "Sem pressa: cada leitura planta uma semente.";
      root.replaceChildren(endCard(acertos + " de " + itens.length + " (" + pct + "%)", msg, function () { load(playCompletar); }));
    }
    show();
  }

  // ======================================================================
  // MONTE O VERSÍCULO
  // ======================================================================
  function playMontar(itens) {
    var i = 0, perfeitos = 0, erros = 0, dicas = 0;
    var bar = scorebar([
      { key: "q", label: "Versículo", value: "1/" + itens.length },
      { key: "ok", label: "Sem ajuda", value: 0 },
      { key: "err", label: "Tentativas erradas", value: 0 },
      { key: "hint", label: "Dicas", value: 0 }
    ]);
    var card = el("article", "card quiz-card");
    var answerLine = el("div", "build-answer");
    answerLine.setAttribute("aria-label", "Sua resposta");
    var pool = el("div", "build-pool");
    var refLine = el("p", "quiz-reference");
    var actions = el("div", "quiz-actions");
    var hintBtn = el("button", "btn btn--soft", "Dica");
    hintBtn.type = "button";
    var clearBtn = el("button", "btn btn--ghost", "Limpar");
    clearBtn.type = "button";
    var next = el("button", "btn btn--primary", "Próximo →");
    next.type = "button"; next.hidden = true;
    var feedback = el("span", "save-status");
    actions.appendChild(hintBtn); actions.appendChild(clearBtn); actions.appendChild(next); actions.appendChild(feedback);
    card.appendChild(answerLine); card.appendChild(pool); card.appendChild(refLine); card.appendChild(actions);
    root.replaceChildren(bar.node, card);

    var item, chips, placed, locked, usedHint, hadError;

    function show() {
      item = itens[i]; locked = false; usedHint = false; hadError = false; placed = [];
      bar.set("q", (i + 1) + "/" + itens.length);
      answerLine.replaceChildren(); answerLine.className = "build-answer";
      pool.replaceChildren(); refLine.replaceChildren(); refLine.classList.remove("show");
      feedback.textContent = ""; feedback.classList.remove("is-saved");
      next.hidden = true; hintBtn.disabled = false; clearBtn.disabled = false;
      var order = item.palavras.map(function (w, idx) { return { w: w, idx: idx }; });
      var mixed = shuffle(order);
      if (mixed.length > 2 && mixed.every(function (m, k) { return m.idx === k; })) mixed = mixed.reverse();
      chips = mixed.map(function (m) {
        var b = el("button", "build-chip", m.w);
        b.type = "button";
        b.addEventListener("click", function () { place(m); });
        pool.appendChild(b);
        return { data: m, btn: b, used: false };
      });
    }
    function chipFor(m) { return chips.filter(function (c) { return c.data === m; })[0]; }
    function place(m) {
      if (locked) return;
      var chip = chipFor(m);
      if (chip.used) return;
      chip.used = true; chip.btn.hidden = true;
      var b = el("button", "build-chip build-chip--placed", m.w);
      b.type = "button";
      b.addEventListener("click", function () { unplace(m, b); });
      answerLine.appendChild(b);
      placed.push({ data: m, btn: b });
      if (placed.length === item.palavras.length) verify();
    }
    function unplace(m, btn) {
      if (locked) return;
      btn.remove();
      placed = placed.filter(function (p) { return p.data !== m; });
      var chip = chipFor(m); chip.used = false; chip.btn.hidden = false;
      answerLine.classList.remove("is-wrong");
    }
    function verify() {
      var okAll = placed.every(function (p, k) { return p.data.w === item.palavras[k]; });
      if (okAll) {
        locked = true;
        answerLine.classList.add("is-right");
        placed.forEach(function (p) { p.btn.classList.add("right"); p.btn.disabled = true; });
        if (!usedHint && !hadError) { perfeitos++; bar.set("ok", perfeitos); }
        feedback.textContent = "Montou!"; feedback.classList.add("is-saved");
        refLine.replaceChildren(refLink(item)); refLine.classList.add("show");
        hintBtn.disabled = true; clearBtn.disabled = true;
        next.textContent = i + 1 >= itens.length ? "Ver resultado →" : "Próximo →";
        next.hidden = false; next.focus();
        announce("Versículo montado corretamente");
      } else {
        hadError = true; erros++; bar.set("err", erros);
        answerLine.classList.add("is-wrong");
        placed.forEach(function (p, k) { p.btn.classList.toggle("wrong", p.data.w !== item.palavras[k]); });
        feedback.textContent = "Ainda não — toque nas palavras vermelhas para trocar.";
        announce("A ordem ainda não está certa");
      }
    }
    clearBtn.addEventListener("click", function () {
      if (locked) return;
      placed.slice().forEach(function (p) { unplace(p.data, p.btn); });
      feedback.textContent = "";
    });
    hintBtn.addEventListener("click", function () {
      if (locked) return;
      // Corrige a posição certa mais cedo: devolve o que estiver errado e põe a próxima palavra.
      var k = 0;
      while (k < placed.length && placed[k].data.w === item.palavras[k]) k++;
      placed.slice(k).forEach(function (p) { unplace(p.data, p.btn); });
      var wanted = chips.filter(function (c) { return !c.used && c.data.w === item.palavras[k]; })[0];
      if (wanted) { usedHint = true; dicas++; bar.set("hint", dicas); place(wanted.data); }
    });
    next.addEventListener("click", function () {
      i++;
      if (i >= itens.length) finish(); else show();
    });
    function finish() {
      if (perfeitos >= Math.ceil(itens.length * 0.6)) party();
      var msg = perfeitos === itens.length ? "Todos sem ajuda — você conhece bem esses versículos!" :
        "Montar versículos é uma ótima forma de memorizar. Tente de novo!";
      root.replaceChildren(endCard(perfeitos + " de " + itens.length + " sem ajuda", msg, function () { load(playMontar); }));
    }
    show();
  }

  // ======================================================================
  // RELÂMPAGO (Antigo ou Novo Testamento)
  // ======================================================================
  function playRelampago(itens) {
    var DURATION = 45, PENALTY = 2;
    var best = bestGet("relampago");
    var intro = el("div", "card quiz-card game-intro");
    intro.appendChild(el("p", null, "Você tem " + DURATION + " segundos. Cada versículo é do Antigo ou do Novo Testamento? Acerte rápido — erros custam " + PENALTY + " segundos."));
    intro.appendChild(el("p", "muted", "No teclado: ← Antigo · → Novo. Seu recorde: " + best + "."));
    var start = el("button", "btn btn--primary", "Começar");
    start.type = "button";
    intro.appendChild(start);
    root.replaceChildren(intro);
    start.focus();

    start.addEventListener("click", function () {
      var i = 0, acertos = 0, erros = 0, seq = 0, left = DURATION, timer = null, busy = false;
      var bar = scorebar([
        { key: "time", label: "Tempo", value: DURATION },
        { key: "ok", label: "Acertos", value: 0 },
        { key: "seq", label: "Sequência", value: 0 },
        { key: "best", label: "Recorde", value: best }
      ]);
      var track = el("div", "timer-track");
      var fill = el("span", "timer-fill");
      track.appendChild(fill);
      var card = el("article", "card quiz-card flash-card");
      var verse = el("p", "quiz-verse");
      var choices = el("div", "relampago-choices");
      var AT = el("button", "relampago-btn relampago-btn--at", "Antigo Testamento");
      var NT = el("button", "relampago-btn relampago-btn--nt", "Novo Testamento");
      AT.type = "button"; NT.type = "button";
      choices.appendChild(AT); choices.appendChild(NT);
      card.appendChild(verse); card.appendChild(choices);
      root.replaceChildren(bar.node, track, card);

      function show() {
        var q = itens[i % itens.length];
        verse.textContent = "“" + q.texto + "”";
        busy = false;
      }
      function answer(testament) {
        if (busy || remaining() <= 0) return;
        busy = true;
        var q = itens[i % itens.length];
        var right = testament === q.correta;
        card.classList.remove("flash-right", "flash-wrong");
        void card.offsetWidth; // reinicia a animação
        card.classList.add(right ? "flash-right" : "flash-wrong");
        if (right) { acertos++; seq++; } else { erros++; seq = 0; }
        bar.set("ok", acertos); bar.set("seq", seq);
        i++;
        setTimeout(function () { if (remaining() > 0) show(); }, 260);
      }
      AT.addEventListener("click", function () { answer("Antigo Testamento"); });
      NT.addEventListener("click", function () { answer("Novo Testamento"); });
      function onKey(ev) {
        if (ev.key === "ArrowLeft") { ev.preventDefault(); answer("Antigo Testamento"); }
        else if (ev.key === "ArrowRight") { ev.preventDefault(); answer("Novo Testamento"); }
      }
      document.addEventListener("keydown", onKey);

      // Tempo restante = duração - tempo real decorrido - penalidades por erro.
      var startedAt = Date.now();
      function remaining() { return Math.max(0, DURATION - (Date.now() - startedAt) / 1000 - erros * PENALTY); }
      timer = setInterval(function () {
        left = remaining();
        bar.set("time", Math.ceil(left));
        fill.style.width = (left / DURATION * 100) + "%";
        if (left <= 0) finish();
      }, 100);

      function finish() {
        clearInterval(timer); document.removeEventListener("keydown", onKey);
        var total = acertos + erros;
        var pct = total ? Math.round((acertos / total) * 100) : 0;
        var record = acertos > best;
        if (record) { best = acertos; bestSet("relampago", best); }
        if (record || pct >= 90) party();
        var text = pct + "% de acerto" + (record ? " · novo recorde!" : " · recorde: " + best);
        root.replaceChildren(endCard(acertos + " versículos certos", text, function () { load(playRelampago); }));
      }
      show();
    });
  }

  // ======================================================================
  // PARES (memória)
  // ======================================================================
  function playPares(itens) {
    var moves = 0, found = 0, first = null, lock = false, started = null, tick = null;
    var bestKey = "pares_" + itens.length, best = bestGet(bestKey);
    var bar = scorebar([
      { key: "moves", label: "Jogadas", value: 0 },
      { key: "found", label: "Pares", value: "0/" + itens.length },
      { key: "time", label: "Tempo", value: "0s" },
      { key: "best", label: "Melhor", value: best ? best + " jog." : "—" }
    ]);
    var grid = el("div", "pairs-grid");
    var cards = [];
    itens.forEach(function (it) {
      cards.push({ id: it.id, kind: "texto", label: it.texto, item: it });
      cards.push({ id: it.id, kind: "ref", label: it.referencia, item: it });
    });
    shuffle(cards).forEach(function (c) {
      var btn = el("button", "pair-card");
      btn.type = "button";
      btn.setAttribute("aria-label", "Carta virada para baixo");
      var inner = el("span", "pair-card__inner");
      var back = el("span", "pair-card__face pair-card__face--back", "✦");
      var front = el("span", "pair-card__face pair-card__face--front pair-card__face--" + c.kind, c.kind === "texto" ? "“" + c.label + "”" : c.label);
      inner.appendChild(back); inner.appendChild(front);
      btn.appendChild(inner);
      c.btn = btn;
      btn.addEventListener("click", function () { flip(c); });
      grid.appendChild(btn);
    });
    root.replaceChildren(bar.node, grid);

    function flip(c) {
      if (lock || c.btn.classList.contains("is-flipped") || c.btn.classList.contains("is-matched")) return;
      if (!started) {
        started = Date.now();
        tick = setInterval(function () { bar.set("time", Math.floor((Date.now() - started) / 1000) + "s"); }, 500);
      }
      c.btn.classList.add("is-flipped");
      c.btn.removeAttribute("aria-label");
      if (!first) { first = c; return; }
      moves++; bar.set("moves", moves);
      if (first.id === c.id && first.kind !== c.kind) {
        [first, c].forEach(function (x) { x.btn.classList.add("is-matched"); });
        found++; bar.set("found", found + "/" + itens.length);
        announce("Par encontrado: " + c.item.referencia);
        first = null;
        if (found === itens.length) finish();
      } else {
        lock = true;
        var a = first; first = null;
        setTimeout(function () {
          a.btn.classList.remove("is-flipped"); c.btn.classList.remove("is-flipped");
          lock = false;
        }, 950);
      }
    }
    function finish() {
      clearInterval(tick);
      var secs = Math.floor((Date.now() - started) / 1000);
      var record = !best || moves < best;
      if (record) { best = moves; bestSet(bestKey, best); }
      party();
      var text = secs + " segundos" + (record ? " · novo recorde de jogadas!" : " · melhor: " + best + " jogadas");
      setTimeout(function () {
        root.replaceChildren(endCard("Todos os pares em " + moves + " jogadas", text, function () { load(playPares); }));
      }, 700);
    }
  }

  var ENGINES = { completar: playCompletar, montar: playMontar, relampago: playRelampago, pares: playPares };
  if (ENGINES[SLUG]) load(ENGINES[SLUG]);
})();
