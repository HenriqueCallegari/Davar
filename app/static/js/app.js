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

  // ----- Confete (comemorações: fim de jogo, dia concluído) -----
  window.confetti = function () {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var canvas = document.createElement("canvas");
    canvas.setAttribute("aria-hidden", "true");
    canvas.style.cssText = "position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:200";
    document.body.appendChild(canvas);
    var ctx = canvas.getContext("2d");
    var w = canvas.width = window.innerWidth, h = canvas.height = window.innerHeight;
    var colors = ["#e7b53f", "#5b8fd8", "#6faa77", "#cf6b5c", "#a781cf", "#d8b878"];
    var pieces = [];
    for (var i = 0; i < 150; i++) {
      pieces.push({
        x: w / 2 + (Math.random() - .5) * w * .3, y: h * .35,
        vx: (Math.random() - .5) * 11, vy: -Math.random() * 11 - 3,
        size: 5 + Math.random() * 6, rot: Math.random() * 6.28, vr: (Math.random() - .5) * .35,
        color: colors[i % colors.length]
      });
    }
    var start = performance.now();
    (function frame(now) {
      var t = now - start;
      ctx.clearRect(0, 0, w, h);
      pieces.forEach(function (p) {
        p.vy += .22; p.x += p.vx; p.y += p.vy; p.vx *= .992; p.rot += p.vr;
        ctx.save();
        ctx.globalAlpha = Math.max(0, 1 - t / 2600);
        ctx.translate(p.x, p.y); ctx.rotate(p.rot);
        ctx.fillStyle = p.color; ctx.fillRect(-p.size / 2, -p.size / 3, p.size, p.size * .6);
        ctx.restore();
      });
      if (t < 2600) requestAnimationFrame(frame); else canvas.remove();
    })(start);
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
