/**
 * AgriBOS Service Worker (Safe Non-Stale Caching Strategy)
 * 
 * Safety Contract:
 * - Pre-caches ONLY immutable public static assets (CSS, JS, Icons, Fonts).
 * - Bypasses cache completely (Network-Only / Network-First) for all authenticated
 *   financial routes, APIs, forms, and dynamic accounting views to prevent stale data.
 */

const CACHE_NAME = 'agribos-static-v3.0';
const STATIC_ASSETS = [
  '/static/css/tailwind.css',
  '/static/css/custom.css',
  '/static/css/print.css',
  '/static/vendor/alpine.min.js',
  '/static/vendor/htmx.min.js',
  '/static/js/app.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/logo.png',
  '/static/manifest.webmanifest'
];

// Install: Pre-cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[AgriBOS ServiceWorker] Non-critical static asset caching notice:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate: Clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Strategy dispatch
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // 1. Non-GET requests (POST, PUT, DELETE): Always bypass to network
  if (request.method !== 'GET') {
    return;
  }

  // 2. Static Asset Requests (/static/): Cache-First strategy
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          // Return cached static asset while updating in background
          fetch(request).then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              caches.open(CACHE_NAME).then((cache) => cache.put(request, networkResponse));
            }
          }).catch(() => {});
          return cachedResponse;
        }
        return fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // 3. Dynamic / Authenticated Financial Routes & HTML: Network-First (NO CACHING of financial data)
  // Ensures all balances, daily closings, receipts, and ledger lines are always fresh.
  event.respondWith(
    fetch(request).catch(() => {
      // Offline fallback when network is completely unavailable
      return new Response(
        `<!DOCTYPE html>
        <html lang="en" class="dark">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Offline | AgriBOS ERP</title>
          <link rel="stylesheet" href="/static/css/tailwind.css">
        </head>
        <body class="bg-[#0B0F17] text-white min-h-screen flex items-center justify-center p-6 text-center">
          <div class="max-w-md bg-[#131A26] border border-[#28354A] rounded-2xl p-8 shadow-2xl">
            <div class="w-16 h-16 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 mx-auto mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="currentColor" viewBox="0 0 16 16">
                <path d="M10.706 3.294A12.545 12.545 0 0 0 8 3C5.259 3 2.723 3.882.663 5.379a.485.485 0 0 0-.048.736.518.518 0 0 0 .668.05A11.448 11.448 0 0 1 8 4c.63 0 1.249.05 1.852.148l.854-.854zM8 6c-1.905 0-3.68.56-5.194 1.534a.507.507 0 0 0-.06.755.5.5 0 0 0 .68.06A9.453 9.453 0 0 1 8 7c.48 0 .949.038 1.405.111l.888-.888A10.518 10.518 0 0 0 8 6zm0 3c-.947 0-1.84.23-2.637.643a.5.5 0 0 0-.074.78.496.496 0 0 0 .69.06A7.472 7.472 0 0 1 8 10c.32 0 .633.024.939.07l.86-.86A8.528 8.528 0 0 0 8 9zm0 3a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"/>
              </svg>
            </div>
            <h1 class="text-xl font-bold mb-2">You are offline</h1>
            <p class="text-xs text-gray-400 mb-6 leading-relaxed">
              AgriBOS financial ledger records and operational workflows require an active network connection to prevent data inconsistencies.
            </p>
            <button onclick="window.location.reload()" class="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-colors shadow-md">
              Retry Connection
            </button>
          </div>
        </body>
        </html>`,
        { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
      );
    })
  );
});
