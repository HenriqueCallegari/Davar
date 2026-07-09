/* App base: tema, toasts e helper de requisicao. */
(function () {
  "use strict";

  // ----- Tema -----
  var root = document.documentElement;
  var toggle = document.getElementById("themeToggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("kja_theme", next); } catch (e) {}
    });
  }

  // ----- Toasts -----
  var wrap = document.getElementById("toastWrap");
  window.showToast = function (message, icon) {
    if (!wrap) return;
    var toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML =
      '<span class="toast-icon">' + (icon || "✓") + "</span>" +
      '<span class="toast-body"><strong>' + message + "</strong></span>";
    wrap.appendChild(toast);
    requestAnimationFrame(function () { toast.classList.add("show"); });
    setTimeout(function () {
      toast.classList.remove("show");
      setTimeout(function () { toast.remove(); }, 400);
    }, 3800);
  };

  // ----- Helper de POST JSON -----
  window.postJSON = function (url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    }).then(function (r) {
      if (!r.ok) throw new Error("Falha na requisição");
      return r.json();
    });
  };

  // ----- PWA (instalável / base offline) -----
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }
})();
