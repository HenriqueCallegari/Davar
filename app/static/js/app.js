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
    // textContent (nunca innerHTML): a mensagem pode conter texto vindo do servidor.
    var iconEl = document.createElement("span");
    iconEl.className = "toast-icon";
    iconEl.textContent = icon || "✓";
    var body = document.createElement("span");
    body.className = "toast-body";
    var strong = document.createElement("strong");
    strong.textContent = message;
    body.appendChild(strong);
    toast.appendChild(iconEl);
    toast.appendChild(body);
    wrap.appendChild(toast);
    requestAnimationFrame(function () { toast.classList.add("show"); });
    setTimeout(function () {
      toast.classList.remove("show");
      setTimeout(function () { toast.remove(); }, 400);
    }, 3800);
  };

  // ----- Helpers de requisição JSON (token CSRF + sessão expirada) -----
  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  window.apiJSON = function (method, url, body) {
    return fetch(url, {
      method: method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": csrfToken()
      },
      body: JSON.stringify(body || {})
    }).then(function (r) {
      if (r.status === 401) {
        // Sessão expirada: leva ao login e volta para esta página depois.
        window.showToast("Sessão expirada. Entre novamente.", "!");
        setTimeout(function () {
          window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
        }, 1200);
        throw new Error("sessao");
      }
      if (!r.ok) throw new Error("Falha na requisição");
      return r.json();
    });
  };

  window.postJSON = function (url, body) { return window.apiJSON("POST", url, body); };

  // ----- Troca de versão bíblica -----
  document.querySelectorAll("[data-version-switch]").forEach(function (sel) {
    sel.addEventListener("change", function () {
      var next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = "/versao/" + sel.value + "?next=" + next;
    });
  });

  // ----- PWA (instalável / base offline) -----
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }
})();
