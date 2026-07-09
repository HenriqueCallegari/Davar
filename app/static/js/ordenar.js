/* Jogo: ordene os livros. */
(function () {
  "use strict";
  var LIVROS = [];
  try { LIVROS = JSON.parse(document.getElementById("livrosData").textContent); } catch (e) {}
  var RUN = 6;
  var target = document.getElementById("target");
  var pool = document.getElementById("pool");
  var feedback = document.getElementById("orderFeedback");
  var nextBtn = document.getElementById("nextRound");
  var roundEl = document.getElementById("roundNum");
  var hitsEl = document.getElementById("hits");
  var missEl = document.getElementById("miss");
  var round = 1, hits = 0, miss = 0, sequence = [], expected = 0;

  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  function novaRodada() {
    var maxStart = Math.max(0, LIVROS.length - RUN);
    var start = Math.floor(Math.random() * (maxStart + 1));
    sequence = LIVROS.slice(start, start + RUN);
    expected = 0; nextBtn.hidden = true;
    feedback.textContent = "Clique no primeiro livro da sequência."; feedback.classList.remove("is-saved");
    roundEl.textContent = round;
    target.innerHTML = "";
    sequence.forEach(function () { var s = document.createElement("div"); s.className = "order-slot"; target.appendChild(s); });
    pool.innerHTML = "";
    shuffle(sequence).forEach(function (nome) {
      var c = document.createElement("button"); c.className = "order-chip"; c.type = "button"; c.textContent = nome;
      c.addEventListener("click", function () { escolher(c, nome); });
      pool.appendChild(c);
    });
  }
  function escolher(chip, nome) {
    if (chip.disabled) return;
    if (nome === sequence[expected]) {
      chip.disabled = true; chip.classList.add("done");
      var slot = target.children[expected]; slot.textContent = nome; slot.classList.add("filled");
      expected++; hits++; hitsEl.textContent = hits;
      if (expected === sequence.length) { feedback.textContent = "Sequência completa! 🎉"; feedback.classList.add("is-saved"); nextBtn.hidden = false; round++; }
      else feedback.textContent = "Isso! Próximo…";
    } else {
      miss++; missEl.textContent = miss; chip.classList.add("shake");
      feedback.textContent = "Ainda não — tente outro.";
      setTimeout(function () { chip.classList.remove("shake"); }, 400);
    }
  }
  nextBtn.addEventListener("click", novaRodada);
  novaRodada();
})();
