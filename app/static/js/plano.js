/* Página do plano: marcar capítulos, salvar nota, navegar e conquistas. */
(function () {
  "use strict";
  var data = document.getElementById("planData");
  if (!data) return;
  var planId = data.dataset.planId;
  var day = data.dataset.day;
  var rows = Array.prototype.slice.call(document.querySelectorAll(".chapter-row[data-book]"));
  var saveStatus = document.getElementById("saveStatus");
  var progressBar = document.getElementById("progressBar");
  var progressPercent = document.getElementById("progressPercent");
  var completeMessage = document.getElementById("dayCompleteMessage");
  var note = document.getElementById("dayNote");
  var saveTimer;

  function setStatus(text, saved) {
    saveStatus.textContent = text;
    saveStatus.classList.toggle("is-saved", Boolean(saved));
  }
  function firstPendingRow() {
    return rows.find(function (r) { return !r.classList.contains("is-done"); }) || rows[0];
  }
  function openRow(row) { if (row && row.dataset.url) window.location.href = row.dataset.url; }

  var cont = document.getElementById("continueReading");
  if (cont) cont.addEventListener("click", function () { openRow(firstPendingRow()); });
  var next = document.getElementById("nextChapter");
  if (next) next.addEventListener("click", function () { openRow(firstPendingRow()); });

  rows.forEach(function (row) {
    var checkbox = row.querySelector("input[type='checkbox']");
    checkbox.addEventListener("change", function () {
      row.classList.toggle("is-done", checkbox.checked);
      setStatus("Salvando…", false);
      window.postJSON("/api/planos/" + planId + "/progresso", {
        livro: row.dataset.book, capitulo: Number(row.dataset.chapter), concluido: checkbox.checked
      }).then(function (d) {
        progressBar.style.width = d.progress.percent + "%";
        progressPercent.textContent = d.progress.percent + "%";
        completeMessage.classList.toggle("show", Boolean(d.day_completed));
        (d.new_achievements || []).forEach(function (a) { window.showToast("Conquista: " + a.nome, a.icone || ""); });
        setStatus("Salvo automaticamente", true);
      }).catch(function () {
        checkbox.checked = !checkbox.checked;
        row.classList.toggle("is-done", checkbox.checked);
        setStatus("Não foi possível salvar", false);
      });
    });
  });

  note.addEventListener("input", function () {
    clearTimeout(saveTimer);
    setStatus("Salvando anotação…", false);
    saveTimer = setTimeout(function () {
      window.postJSON("/api/planos/" + planId + "/dia/" + day + "/nota", { texto: note.value })
        .then(function () { setStatus("Anotação salva automaticamente", true); })
        .catch(function () { setStatus("Não foi possível salvar a anotação", false); });
    }, 550);
  });
})();
