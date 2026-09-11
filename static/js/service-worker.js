/**
 * Sri Basaveshwara Service Worker (PWA Shell & Network-Resilient Architecture)
 * Version: sbh-pwa-v3.2
 * Business: Sri Basaveshwara Harvesting & Co.
 * 
 * ============================================================================
 * CRITICAL FINANCIAL DATA SAFETY & SECURITY CONTRACT:
 * ============================================================================
 * 1. Category A (Static Shell Assets): Cache-First / Stale-While-Revalidate
 *    Pre-caches ONLY public UI assets (CSS, JS, Fonts, Icons, Manifest).
 * 
 * 2. Category C (Financial Data, Ledgers, Balances, APIs, Forms): Network-First / Network-Only
 *    Bypasses CacheStorage completely for financial data.
 *    NO financial balances, transactions, ledger lines, or user credentials are EVER cached.
 * 
 * 3. Mutation Requests (POST, PUT, DELETE, PATCH): Network-Only
 *    All financial submissions and forms pass directly to the server.
 *    Never cached, never silently queued, never replayed.
 * 
 * 4. Offline Shell:
 *    When network drops, navigation requests render a safe offline shell explaining that
 *    financial transactions require active network connectivity.
 * ============================================================================
 */

const CACHE_NAME = 'sbh-pwa-v3.2';

// Core static shell assets for ~fast offline shell display
const STATIC_SHELL_ASSETS = [
  '/static/css/tailwind.css',
  '/static/css/custom.css',
  '/static/css/print.css',
  '/static/vendor/alpine.min.js',
  '/static/vendor/htmx.min.js',
  '/static/js/app.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/favicon-32x32.png',
  '/static/icons/favicon-16x16.png',
  '/static/icons/logo.png',
  '/static/manifest.webmanifest'
];

// Install: Pre-cache static UI shell assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_SHELL_ASSETS).catch((err) => {
        console.warn('[Sri Basaveshwara SW] Non-critical static asset precache warning:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate: Delete any older obsolete caches
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

// Message listener: Controlled skipWaiting support for seamless version upgrades
self.addEventListener('message', (event) => {
  if (event.data && event.data.action === 'skipWaiting') {
    self.skipWaiting();
  }
});

// Fetch: Strategy dispatcher
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // 1. All Non-GET requests (POST, PUT, DELETE, PATCH): STRICT NETWORK ONLY
  // Absolutely no offline caching, no queuing, and no replay of mutations.
  if (request.method !== 'GET') {
    return;
  }

  // 2. Static Asset Requests (/static/): Stale-While-Revalidate / Cache-First
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          // Serve cached static asset immediately and refresh cache in background
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

  // 3. Dynamic / Authenticated Financial Routes & Views: Network-First
  // Guarantees real-time accuracy for ledgers, balances, machine logs, and daily closings.
  event.respondWith(
    fetch(request).catch(() => {
      // If request is a page navigation (HTML document) and offline, serve the safe shell
      if (request.mode === 'navigate' || (request.headers.get('accept') && request.headers.get('accept').includes('text/html'))) {
        return new Response(
          `<!DOCTYPE html>
          <html lang="en" class="dark">
          <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
            <title>Offline | Sri Basaveshwara & Co.</title>
            <link rel="stylesheet" href="/static/css/tailwind.css">
            <link rel="stylesheet" href="/static/css/custom.css">
          </head>
          <body class="bg-[#0B0F17] text-gray-100 min-h-screen flex items-center justify-center p-6 text-center antialiased">
            <div class="max-w-md w-full bg-[#131A26] border border-[#28354A] rounded-2xl p-8 shadow-2xl">
              <div class="w-16 h-16 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 mx-auto mb-5">
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="currentColor" viewBox="0 0 16 16">
                  <path d="M10.706 3.294A12.545 12.545 0 0 0 8 3C5.259 3 2.723 3.882.663 5.379a.485.485 0 0 0-.048.736.518.518 0 0 0 .668.05A11.448 11.448 0 0 1 8 4c.63 0 1.249.05 1.852.148l.854-.854zM8 6c-1.905 0-3.68.56-5.194 1.534a.507.507 0 0 0-.06.755.5.5 0 0 0 .68.06A9.453 9.453 0 0 1 8 7c.48 0 .949.038 1.405.111l.888-.888A10.518 10.518 0 0 0 8 6zm0 3c-.947 0-1.84.23-2.637.643a.5.5 0 0 0-.074.78.496.496 0 0 0 .69.06A7.472 7.472 0 0 1 8 10c.32 0 .633.024.939.07l.86-.86A8.528 8.528 0 0 0 8 9zm0 3a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"/>
                </svg>
              </div>
              <h1 class="text-xl font-bold text-white mb-2">You are currently offline</h1>
              <p class="text-xs text-gray-400 mb-6 leading-relaxed">
                Sri Basaveshwara Harvesting & Co. financial transactions and ledger records require an active internet connection to prevent double entries and protect financial accuracy.
              </p>
              <div class="flex flex-col gap-3">
                <button onclick="window.location.reload()" class="w-full py-3 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm transition-colors shadow-lg active:scale-98">
                  Retry Connection
                </button>
                <button onclick="window.history.back()" class="w-full py-2.5 px-4 rounded-xl bg-[#1A2333] hover:bg-[#222E42] text-gray-300 font-medium text-xs transition-colors border border-[#28354A]">
                  Go Back
                </button>
              </div>
            </div>
          </body>
          </html>`,
          { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
        );
      }
      return Promise.reject(new Error('Network offline'));
    })
  );
});
