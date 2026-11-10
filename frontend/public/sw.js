// ISL NOVA service worker: offline app shell + cached recognition assets.
// - App shell (index.html, /assets/*, icons): cache-first, refreshed in the background.
// - MediaPipe bundle/WASM/models (cdn.jsdelivr.net, storage.googleapis.com): cache-first after
//   the first online visit, so the camera pipeline loads offline.
// - API calls: always network (never cached: they carry personal data and live model state).
const SHELL = 'isl-nova-shell-v2';
const VISION = 'isl-nova-vision-v1';
const SHELL_URLS = ['/', '/favicon.svg', '/manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => ![SHELL, VISION].includes(k)).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const isVision = (u) => u.hostname === 'cdn.jsdelivr.net' || u.hostname === 'storage.googleapis.com';

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === self.location.origin && url.pathname.startsWith('/api/')) return; // network only
  if (isVision(url)) {
    e.respondWith(caches.open(VISION).then(async (c) => (await c.match(req)) || fetch(req).then((r) => {
      if (r.ok) c.put(req, r.clone());
      return r;
    })));
    return;
  }
  if (url.origin !== self.location.origin) return;
  if (req.mode === 'navigate') {
    // SPA routes: network first, fall back to the cached shell when offline
    e.respondWith(fetch(req).then((r) => {
      caches.open(SHELL).then((c) => c.put('/', r.clone()));
      return r;
    }).catch(() => caches.match('/')));
    return;
  }
  e.respondWith(caches.open(SHELL).then(async (c) => {
    const hit = await c.match(req);
    const net = fetch(req).then((r) => { if (r.ok) c.put(req, r.clone()); return r; }).catch(() => hit);
    return hit || net;
  }));
});
