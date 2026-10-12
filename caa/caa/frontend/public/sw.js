// Minimal service worker: makes the app installable and shows a friendly page if you are offline.
// It never caches API calls or logged-in data.
const CACHE = "caa-shell-v1";
const OFFLINE = "/offline.html";
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll([OFFLINE, "/icon-192.png"])));
  self.skipWaiting();
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;   // only page loads; everything else goes straight to the network
  e.respondWith(fetch(e.request).catch(() => caches.match(OFFLINE)));
});
