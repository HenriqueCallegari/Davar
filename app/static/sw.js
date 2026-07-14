/* Service worker — app shell.
   CSS/JS: network-first (sempre pega a versão nova; cai no cache offline).
   Ícones e demais estáticos: cache-first. Áudio: nunca cacheado (respostas 206). */
const CACHE = "davar-v6";
const ASSETS = [
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/js/player.js",
  "/static/icons/favicon.svg"
];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(ASSETS); }));
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }));
  self.clients.claim();
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var path = new URL(req.url).pathname;

  if (path.indexOf("/static/audio/") === 0) return;  // áudio direto da rede

  var isCode = /\/static\/(css|js)\//.test(path);
  if (isCode) {
    // network-first: garante CSS/JS sempre atualizados
    e.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
        return res;
      }).catch(function () { return caches.match(req); })
    );
    return;
  }

  if (path.indexOf("/static/") === 0) {
    // cache-first para ícones e afins
    e.respondWith(
      caches.match(req).then(function (hit) {
        return hit || fetch(req).then(function (res) {
          if (res.status === 200) { var copy = res.clone(); caches.open(CACHE).then(function (c) { c.put(req, copy); }); }
          return res;
        });
      })
    );
  }
});
