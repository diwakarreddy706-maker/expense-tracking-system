# Progressive Web App (PWA) & Mobile Installation Architecture

**Project:** Sri Basaveshwara — Enterprise Agricultural Machinery & Financial ERP  
**Business:** SRI BASAVESHWARA HARVESTING & CO.  
**Phase:** Phase 25 — PWA & Install-to-Phone Experience  

---

## 1. Executive Summary

Sri Basaveshwara is fully equipped as a high-performance **Progressive Web App (PWA)** tailored for smartphone and tablet operation by machine operators, harvester drivers, accountants, and business owners in the field.

Users can install Sri Basaveshwara directly to their Android, iOS, or Desktop home screen, launching it as a fullscreen standalone application without browser URL bars taking up screen estate.

---

## 2. Web App Manifest Specification

- **File Path:** [`static/manifest.webmanifest`](file:///c:/Users/diwak/Desktop/ETS/static/manifest.webmanifest)
- **Application Name:** `Sri Basaveshwara Harvesting & Co. — Sri Basaveshwara & Co.`
- **Short Name:** `Sri Basaveshwara`
- **Display Mode:** `standalone` (fullscreen application shell)
- **Orientation:** `portrait-primary`
- **Theme Color:** `#10B981` (Emerald Green)
- **Background Color:** `#0B0F17` (Deep Dark Slate)
- **Start URL:** `/` (Routes to dashboard when authenticated, or login when unauthenticated)
- **Scope:** `/`
- **Categories:** `["finance", "business", "productivity", "agriculture"]`

### Operational Quick Shortcuts
The manifest provides native OS long-press / 1-tap shortcuts directly to active Django routes:
1. **Record Expense (`+ Expense`):** `/expenses/add/`
2. **Log Fuel Refill (`+ Fuel`):** `/fuel/add/`
3. **New Work Log (`+ Work`):** `/machines/work/add/`
4. **Farmer Ledger (`Ledger`):** `/machines/farmers/ledger/`

---

## 3. PWA Icon Assets

All icons are valid PNG image assets with standard dimensions and maskable support:
- `static/icons/icon-192.png`: 192 × 192 (Any / Maskable adaptive icon)
- `static/icons/icon-512.png`: 512 × 512 (Any / Maskable splash icon)
- `static/icons/favicon-32x32.png`: 32 × 32 browser tab icon
- `static/icons/favicon-16x16.png`: 16 × 16 bookmark icon
- `static/icons/logo.png`: 1024 × 1024 high-resolution brand emblem

---

## 4. Service Worker & Caching Strategy

- **File Path:** [`static/js/service-worker.js`](file:///c:/Users/diwak/Desktop/ETS/static/js/service-worker.js)
- **Active Cache Name:** `sbh-pwa-v3.2`

### Resource Classification & Safety Contracts:

| Resource Category | Strategy | Storage | Financial Safety Contract |
| :--- | :--- | :--- | :--- |
| **Category A (Static Shell Assets)**<br>CSS, JS, Fonts, Icons, Manifest | **Stale-While-Revalidate / Cache-First** | CacheStorage (`sbh-pwa-v3.2`) | Fast loading for offline shell UI |
| **Category C (Financial Data & Ledgers)**<br>Balances, Udhar Katha, Work Logs, Daily Closing, APIs | **Network-First / Network-Only** | **NEVER Cached** | Zero risk of stale or misleading financial records |
| **Mutations (POST, PUT, DELETE, PATCH)**<br>Expense, Fuel, Payment, Work, Wages | **STRICT Network-Only** | **NEVER Cached or Replayed** | Prevents double-submission and transaction desync |

---

## 5. Critical Financial Safety Rules

> [!IMPORTANT]
> **OFFLINE = APPLICATION SHELL + NETWORK AWARENESS**  
> **NOT: OFFLINE FINANCIAL TRANSACTIONS**

1. **No Offline Financial Queuing:** Sri Basaveshwara does not silently queue financial mutations when offline.
2. **No False Promises:** The offline shell clearly explains: *"Financial transactions and ledger records require an active internet connection."*
3. **Form Data Preservation:** If an operator loses connection while filling out a work log or fuel receipt:
   - Form inputs are **not cleared**.
   - No automatic submission happens when network reconnects.
   - The user must explicitly press **Save** once connectivity is restored.

---

## 6. Installation Experience by Platform

### Android & Chromium Browsers (Chrome, Edge, Brave, Samsung Internet)
- Captures `beforeinstallprompt`.
- Displays a bottom sheet banner: *"Install Sri Basaveshwara App — Fast 1-tap field access & fullscreen mode"*.
- Snoozes for 7 days if the user taps *"Not now"*.
- When the user taps *"Install"*, the native install dialog triggers immediately.

### iOS & iPadOS Safari
- Detects iOS non-standalone browsers.
- Displays a 2-step instructional card:
  1. Tap the **Share** button (`⎋`) in Safari's bottom toolbar.
  2. Scroll down and tap **Add to Home Screen** (`➕`).

### Standalone Detection
- Uses `window.matchMedia('(display-mode: standalone)').matches` and `navigator.standalone`.
- When already running as an installed PWA, all install banners and instructions are automatically hidden.

---

## 7. Real-Time Network Status Indicator

- Listens to `window.online` and `window.offline` events.
- **Offline Mode:** Displays a top warning banner: `⚡ Offline — financial actions unavailable`.
- **Online Reconnection:** Displays a brief confirmation: `✓ Connection restored` and auto-dismisses after 3.5 seconds.
- Uses accessible ARIA live regions (`role="status"`, `aria-live="polite"`).

---

## 8. Service Worker Update Strategy

- When a new service worker version is deployed on Render, `initServiceWorkerUpdates()` detects the new worker in the background.
- A non-intrusive bottom notification displays: `New version available — [Update]`.
- Clicking Update sends `skipWaiting` to activate the new version and reload without interrupting unsaved form inputs.

---

## 9. Limitations & Future Work

- **Phase 25 Scope:** Focuses on PWA Shell, Home Screen Installation, and Network Awareness.
- **Future Possibilities:**
  - Idempotent cryptographically-signed offline transaction queue (if requested).
  - Background receipt image compression before upload.
