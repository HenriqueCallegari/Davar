/* Service worker mínimo — app shell (cache-first para estáticos).
   Base para modo offline completo (ver ROADMAP). */
const CACHE = "kja-v1";
const ASSETS = [
  "/static/css/app.css",
  "/static/js/app.js",
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
  e.respondWith(
    caches.match(req).then(function (hit) {
      return hit || fetch(req).then(function (res) {
        try {
          if (res.ok && new URL(req.url).pathname.indexOf("/static/") === 0) {
            var copy = res.clone();
            caches.open(CACHE).then(function (c) { c.put(req, copy); });
          }
        } catch (err) {}
        return res;
      }).catch(function () { return hit; });
    })
  );
});
