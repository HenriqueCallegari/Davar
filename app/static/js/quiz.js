/* Quiz de versículos. */
(function () {
  "use strict";
  var BEST_KEY = "quiz_best_streak";
  var els = {
    verse: document.getElementById("verseText"), ref: document.getElementById("verseRef"),
    options: document.getElementById("options"), next: document.getElementById("nextBtn"),
    feedback: document.getElementById("quizFeedback"), qIndex: document.getElementById("qIndex"),
    score: document.getElementById("qScore"), streak: document.getElementById("qStreak"),
    best: document.getElementById("qBest"), card: document.querySelector(".quiz-card"),
    end: document.getElementById("quizEnd"), endTitle: document.getElementById("endTitle"),
    endText: document.getElementById("endText"), restart: document.getElementById("restartBtn")
  };
  var perguntas = [], atual = 0, score = 0, streak = 0, answered = false;
  var best = Number(localStorage.getItem(BEST_KEY) || 0);
  els.best.textContent = best;

  function carregar() {
    els.verse.textContent = "Carregando…"; els.options.innerHTML = "";
    fetch("/api/quiz?q=10").then(function (r) { return r.json(); }).then(function (data) {
      perguntas = data.perguntas || [];
      atual = 0; score = 0; streak = 0;
      els.score.textContent = "0"; els.streak.textContent = "0";
      els.end.hidden = true; els.card.hidden = false; mostrar();
    }).catch(function () { els.verse.textContent = "Não foi possível carregar."; });
  }
  function mostrar() {
    answered = false;
    var p = perguntas[atual];
    els.qIndex.textContent = (atual + 1) + "/" + perguntas.length;
    els.verse.textContent = "“" + p.texto + "”";
    els.ref.textContent = ""; els.ref.classList.remove("show");
    els.feedback.textContent = ""; els.feedback.classList.remove("is-saved");
    els.next.disabled = true; els.options.innerHTML = "";
    p.opcoes.forEach(function (nome) {
      var b = document.createElement("button");
      b.className = "quiz-option"; b.type = "button"; b.textContent = nome;
      b.addEventListener("click", function () { responder(b, nome, p); });
      els.options.appendChild(b);
    });
  }
  function responder(btn, escolha, p) {
    if (answered) return; answered = true;
    var acertou = escolha === p.correta;
    Array.prototype.forEach.call(els.options.children, function (b) {
      b.disabled = true;
      if (b.textContent === p.correta) b.classList.add("correct");
      else if (b === btn) b.classList.add("wrong");
    });
    if (acertou) { score++; streak++; els.feedback.textContent = "Acertou! 🎉"; els.feedback.classList.add("is-saved"); }
    else { streak = 0; els.feedback.textContent = "Era " + p.correta + "."; }
    if (streak > best) { best = streak; try { localStorage.setItem(BEST_KEY, best); } catch (e) {} }
    els.score.textContent = score; els.streak.textContent = streak; els.best.textContent = best;
    els.ref.textContent = p.referencia; els.ref.classList.add("show"); els.next.disabled = false;
  }
  els.next.addEventListener("click", function () {
    atual++; if (atual >= perguntas.length) finalizar(); else mostrar();
  });
  function finalizar() {
    els.card.hidden = true; els.end.hidden = false;
    var pct = Math.round((score / perguntas.length) * 100);
    els.endTitle.textContent = score + "/" + perguntas.length + " acertos (" + pct + "%)";
    els.endText.textContent = pct === 100 ? "Perfeito! 👑" : pct >= 70 ? "Muito bom! 🙌" :
      pct >= 40 ? "Bom começo — a leitura diária ajuda. 📖" : "Não desanime! Cada leitura conta. 🌱";
  }
  els.restart.addEventListener("click", carregar);
  carregar();
})();
