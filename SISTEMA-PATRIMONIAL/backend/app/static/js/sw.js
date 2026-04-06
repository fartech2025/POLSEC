/**
 * POLSEC — Service Worker
 * Estratégia: cache-first (assets), network-first com fallback (páginas HTML)
 * Versão: 1.0
 */

const CACHE_NAME = 'polsec-v1.0';

// Assets estáticos pré-cacheados no install
const PRECACHE = [
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/js/offline.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css',
];

// ── Install: pré-cacheia assets críticos ──────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: remove caches antigos ──────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Ignora POST/PUT (tratados pelo offline.js via interceptação de form)
  if (request.method !== 'GET') return;

  // Ignora chrome-extension e outros esquemas não-http
  if (!url.protocol.startsWith('http')) return;

  const isSameOrigin = url.hostname === self.location.hostname;
  const isCDN = url.hostname.includes('jsdelivr.net') ||
                url.hostname.includes('fonts.googleapis.com') ||
                url.hostname.includes('fonts.gstatic.com');
  const isStatic = url.pathname.startsWith('/static/');

  // Assets locais e CDN → cache-first
  if (isStatic || isCDN) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(c => c.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // Páginas HTML do próprio domínio → network-first com cache fallback
  if (isSameOrigin && request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Cacheia apenas respostas de sucesso (não redirects de login)
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(c => c.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // JSON / API → network-first com cache fallback
  if (isSameOrigin) {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(c => c.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
  }
});
