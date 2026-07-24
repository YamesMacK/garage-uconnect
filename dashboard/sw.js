/* sw.js — minimal service worker for PWA installability.
   Strategy:
   - data.json / location.json — network first, cached under a CANONICAL key
     (the page fetches with a ?t= cache-buster, so caching the raw request
     URL would never match again and would grow the cache without bound).
   - navigations / index.html — network first so dashboard updates reach
     installed PWAs without a manual CACHE bump; cache fallback offline.
   - everything else same-origin (icons, images, manifest) — cache first. */

const CACHE = 'garage-v20260724-cinematic-v12';
const SHELL = [
  './',
  './index.html',
  './cinematic.css?v=20260724c',
  './manifest.json',
  './img/hero-cinematic-white-v2.png',
  './img/truck-top-laramie-v1.png',
  './icon-192.png',
  './img/oil-can-ios.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k.startsWith('garage-') && k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  // Cross-origin (fonts, maps, GitHub API) — let the browser handle it.
  if (url.origin !== self.location.origin) return;

  // Live data — network first under a canonical key. Fall back to the
  // cached last-good copy on network failure AND on HTTP errors (a Pages
  // deploy propagation miss can 404 exactly when the cache matters most).
  const dataMatch = url.pathname.match(/\/(data|location)\.json$/);
  if (dataMatch) {
    const key = `./${dataMatch[1]}.json`;
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(key, copy));
            return res;
          }
          return caches.match(key).then((hit) => hit || res);
        })
        .catch(() => caches.match(key))
    );
    return;
  }

  // App shell — network first so edits deploy without a CACHE bump.
  if (e.request.mode === 'navigate' || url.pathname.endsWith('/index.html')) {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put('./index.html', copy));
          }
          return res;
        })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }

  // Static assets — cache first, network fallback.
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request))
  );
});
