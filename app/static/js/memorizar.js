/* Cartões de memorização: revisão com repetição espaçada (caixas de Leitner). */
(function () {
  "use strict";
  var root = document.getElementById("memoRoot");
  if (!root) return;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function emptyState(title, text, link) {
    var box = el("div", "card quiz-end");
    box.appendChild(el("h2", null, title));
    box.appendChild(el("p", null, text));
    if (link) {
      var a = el("a", "btn btn--primary", link.label);
      a.href = link.href;
      box.appendChild(a);
    }
    return box;
  }
  // "Na verdade..." -> "N_ v_____ ..." (dica: primeira letra de cada palavra)
  function hintOf(text) {
    return text.split(/\s+/).map(function (w) {
      var m = w.match(/^([^A-Za-zÀ-ÿ]*)([A-Za-zÀ-ÿ])(.*)$/);
      if (!m) return w;
      var rest = m[3].replace(/[A-Za-zÀ-ÿ]/g, "_");
      return m[1] + m[2] + rest;
    }).join(" ");
  }

  fetch("/api/estudo/memorizar/fila", { credentials: "same-origin", headers: { "Accept": "application/json" } })
    .then(function (r) {
      if (r.status === 401) { window.location.href = "/login?next=/estudo/memorizar"; throw new Error("sessao"); }
      if (!r.ok) throw new Error("falha");
      return r.json();
    })
    .then(function (data) {
      if (!data.total) {
        root.replaceChildren(emptyState(
          "Seus cartões aparecerão aqui",
          "Durante a leitura, toque em “Memorizar” embaixo de um versículo para criar um cartão.",
          { label: "Ir para a Bíblia", href: "/livros" }));
      } else if (!data.cartas.length) {
        root.replaceChildren(emptyState(
          "Tudo revisado por hoje",
          "Seus próximos cartões chegam nos próximos dias. Que tal ler um capítulo agora?",
          { label: "Ler a Bíblia", href: "/livros" }));
      } else {
        run(data.cartas);
      }
    })
    .catch(function (err) {
      if (err && err.message === "sessao") return;
      root.replaceChildren(emptyState("Não foi possível carregar", "Tente de novo em instantes."));
    });

  function run(cartas) {
    var queue = cartas.slice(), total = cartas.length, done = 0, remembered = 0, revealed = false;
    var progress = el("div", "timer-track");
    var fill = el("span", "timer-fill");
    progress.appendChild(fill);
    var count = el("p", "memo-count");
    var card = el("article", "card memo-card");
    var ref = el("h2", "memo-ref");
    var hint = el("p", "memo-hint");
    var verse = el("blockquote", "memo-verse");
    verse.hidden = true;
    var tools = el("div", "quiz-actions");
    var hintBtn = el("button", "btn btn--ghost", "Dica");
    hintBtn.type = "button";
    var showBtn = el("button", "btn btn--primary", "Mostrar versículo");
    showBtn.type = "button";
    tools.appendChild(hintBtn); tools.appendChild(showBtn);
    var rate = el("div", "memo-rate");
    rate.hidden = true;
    [["esqueci", "Esqueci", "memo-btn--bad"], ["quase", "Quase", "memo-btn--mid"], ["lembrei", "Lembrei", "memo-btn--good"]]
      .forEach(function (r) {
        var b = el("button", "memo-rate__btn " + r[2], r[1]);
        b.type = "button";
        b.addEventListener("click", function () { review(r[0]); });
        rate.appendChild(b);
      });
    card.appendChild(ref); card.appendChild(hint); card.appendChild(verse); card.appendChild(tools); card.appendChild(rate);
    root.replaceChildren(count, progress, card);

    function show() {
      var c = queue[0];
      revealed = false;
      count.textContent = "Cartão " + Math.min(done + 1, total) + " de " + total + (queue.length > total - done ? " · revisando os que escaparam" : "");
      fill.style.width = (done / total * 100) + "%";
      ref.textContent = c.referencia;
      hint.textContent = ""; hint.hidden = true;
      verse.textContent = "“" + c.texto + "”"; verse.hidden = true;
      tools.hidden = false; rate.hidden = true;
      hintBtn.disabled = false;
    }
    hintBtn.addEventListener("click", function () {
      hint.textContent = hintOf(queue[0].texto);
      hint.hidden = false; hintBtn.disabled = true;
    });
    showBtn.addEventListener("click", function () {
      revealed = true;
      verse.hidden = false; hint.hidden = true; tools.hidden = true; rate.hidden = false;
    });

    function review(result) {
      var c = queue.shift();
      window.postJSON("/api/estudo/memorizar/revisar", {
        abbrev: c.abbrev, capitulo: c.capitulo, versiculo: c.versiculo, resultado: result
      }).catch(function () { window.showToast("Não foi possível salvar esta revisão", "!"); });
      if (result === "esqueci") {
        queue.push(c);  // volta ao fim da fila desta sessão
      } else {
        done++;
        if (result === "lembrei") remembered++;
      }
      if (!queue.length) finish(); else show();
    }
    function finish() {
      fill.style.width = "100%";
      if (remembered >= Math.ceil(total / 2) && window.confetti) window.confetti();
      var box = emptyState(
        "Revisão concluída",
        remembered + " de " + total + " lembrados de primeira. Os cartões voltam no tempo certo — sem pressa.",
        { label: "Voltar ao estudo", href: "/estudo" });
      root.replaceChildren(box);
    }
    show();
  }
})();
