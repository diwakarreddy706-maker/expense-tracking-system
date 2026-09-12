
**Sri Basaveshwara ERP - Mobile Optimization Specification V2**

# Sri Basaveshwara ERP — Comprehensive Mobile UX & UI Audit (V2)

This authoritative specification details structural, ergonomic, offline-readiness, and layout adjustments required across all modules of the Sri Basaveshwara Harvesting Machines ERP. The goal is to eliminate desktop-first bottlenecks, streamline field usage on mobile viewports (< 420px), and establish touch-first, offline-ready standards across every agricultural operational workflow.

## 1. Global Application Shell & Layout System

|   |
| - |

**Component Location**

|   |
| - |

**Current Issue / Desktop Overflow**

|   |
| - |

**Exact Change Required**

|   |
| - |

**Top Navigation Bar (Header)**

|   |
| - |

Houses 5 separate actions (Menu, Language toggle, Theme switch, Search bar, Profile pill) alongside the brand logo, resulting in cramped tap targets and header height bloat.

|   |
| - |

Condense to 3 primary items: Brand Logo + Hamburger Menu on the left, and Profile Avatar on the right. Relocate Language, Theme, and Global Search into the mobile slide-out drawer navigation.

|   |
| - |

**Bottom Navigation Bar**

|   |
| - |

Duplicates top-row shortcuts (+Fuel, +Work) while the primary Floating Action Button (FAB) uses poor green-on-teal contrast with no safe-area padding.

|   |
| - |

Redesign as a 5-tab persistent bottom bar: Home, Operations/Work, Center FAB (+ Speed Dial for all creations), Ledger, and Menu. Apply iOS/Android safe area bottom inset padding. Boost FAB contrast to meet WCAG AA (4.5:1).

|   |
| - |

**Subheadings & Metadata Banners**

|   |
| - |

Long titles such as "Financial Overview & Operational Cost Hierarchy • Authoritative Central Ledger" consume critical above-the-fold space.

|   |
| - |

Hide non-critical enterprise subtitles on mobile viewports. Integrate the date chip directly underneath the title as compact metadata rather than a separate floating badge.

|   |
| - |

**Modal Dialogs & Data Entry Forms**

|   |
| - |

Standard desktop popups trigger horizontal cut-offs and keyboard overlay issues.

|   |
| - |

Convert all modal popups to mobile bottom sheets that slide up from the bottom, dock cleanly, and scroll independently of the virtual keyboard.

## 2. Core Operations & Registries

|   |
| - |

**Module / Screen**

|   |
| - |

**Screen Elements Affected**

|   |
| - |

**Required Mobile Transformation**

|   |
| - |

**Executive Dashboard**

|   |
| - |

Today's Financial Summary, Daily Closing alert, and quick action cards.

|   |
| - |

Remove the top duplicate row of action buttons (+Expense, +Work, +Fuel, Ledger). Convert the 5-item horizontal ledger balance equation into a compact swipeable summary card or a 2x2 metric grid. Convert the Daily Closing banner into a slim top status ribbon.

|   |
| - |

**Expenses Hub & Categories**

|   |
| - |

Expense log tabular listing, multi-select category filters, search input.

|   |
| - |

Replace horizontal multi-column expense table with touch cards displaying expense category and date on top, amount in high-contrast red/green, and payment mode badge at the bottom. Replace desktop multi-select dropdowns with a single horizontal scrolling pill bar (Diesel, Maintenance, Spare Parts, UPI, Cash).

|   |
| - |

**Fuel & Lubricants**

|   |
| - |

Fuel top-up forms, pump vendor selection, machine meter reading log.

|   |
| - |

Transform meter input fields to trigger numeric keyboards with decimal support. Add immediate camera capture integration for fuel slip and pump meter photos. Present diesel consumption history as unit-level cards showing Liters, Cost, and Machine ID.

## 3. Machinery, Fleet & Field Operations

|   |
| - |

**Module / Screen**

|   |
| - |

**Screen Elements Affected**

|   |
| - |

**Required Mobile Transformation**

|   |
| - |

**Machines Registry & Rented Fleet**

|   |
| - |

Machinery asset roster, ownership specs, operating metrics.

|   |
| - |

Replace tabular fleet view with compact machine profile cards displaying machine registration, harvester model, current status indicator (Ready, In Job, In Workshop), and one-tap quick action buttons (Log Work, Assign Driver, Fuel Up).

|   |
| - |

**Vehicle Compliance**

|   |
| - |

Insurance expiry dates, fitness certificates, road tax tables.

|   |
| - |

Group records by expiration urgency into three mobile accordion tabs: Expired / Due in 7 Days (Red), Due in 30 Days (Yellow), and Compliant (Green). Include direct document upload from camera roll.

|   |
| - |

**Bookings & Jobs**

|   |
| - |

Farmer service booking schedule, advance payments, field locations.

|   |
| - |

Display jobs as chronological itinerary cards sorted by date and proximity. Place direct call links and WhatsApp location sharing buttons on each card for machine operators in the field.

|   |
| - |

**Dispatch Board**

|   |
| - |

Desktop Kanban columns and multi-machine calendar grid.

|   |
| - |

Convert the horizontal multi-lane board into a vertical timeline grouped by machine tag. Use quick swipe actions to change dispatch status (Dispatched, On Field, Idle).

|   |
| - |

**Work Logs & Billing**

|   |
| - |

Hour meter start/end, acreage calculation, customer signature.

|   |
| - |

Design as a streamlined 3-step field logging workflow: Step 1 (Acreage/Hour inputs with automated billing calculator), Step 2 (Optional fuel deduction / payment advance), Step 3 (On-screen digital customer sign-off).

|   |
| - |

**Workshop Maintenance**

|   |
| - |

Spare parts replacement log, repair costs, mechanic notes.

|   |
| - |

Present maintenance tickets as collapsible accordion items with quick status badges and direct photo attachment capabilities for damaged parts.

## 4. Finance, Ledgers & Settlements

|   |
| - |

**Module / Screen**

|   |
| - |

**Screen Elements Affected**

|   |
| - |

**Required Mobile Transformation**

|   |
| - |

**Farmer Credit Ledger (Udhar)**

|   |
| - |

Farmer balance ledger, running debit/credit columns, search filter.

|   |
| - |

Introduce a sticky top search bar with instant autocomplete by farmer name and village. Each row must feature a one-tap WhatsApp payment reminder button with pre-filled billing details and balance due.

|   |
| - |

**Staff & Wages**

|   |
| - |

Driver salary records, trip commissions, daily bata, advance payouts.

|   |
| - |

Segment employee accounts into individual cards showing Outstanding Wages, Total Paid, and Pending Advances. Provide quick-entry modal for logging daily driver bata and fuel allowances.

|   |
| - |

**Business Accounts, Receivables & Payables**

|   |
| - |

Bank account cards, aging buckets (0-15d, 16-30d, 30d+), vendor bills.

|   |
| - |

Replace horizontal aging tables with a mobile segmented control (All, 0-15d, 16-30d, 30d+). Display vendor balances with quick action buttons for settling via UPI or logging cheque details.

|   |
| - |

**Daily Closing**

|   |
| - |

Physical cash reconciliation, bank closing balances, discrepancy tally.

|   |
| - |

Break reconciliation down into a stepped wizard: Step 1 (Physical Cash Count with denomination counters), Step 2 (Bank Balances Verification), Step 3 (Unreconciled Expense Review & Lock Daily Register).

|   |
| - |

**Budgets & Analytics**

|   |
| - |

Category budget progress bars, multi-axis analytical graphs.

|   |
| - |

Replace desktop charts with touch-optimized vertical bar summaries and horizontal progress meters. Set fixed minimum chart heights with quick time-period toggles (Today, 7D, 30D, Year).

## 5. Administration & Master Setup

|   |
| - |

**Module / Screen**

|   |
| - |

**Screen Elements Affected**

|   |
| - |

**Required Mobile Transformation**

|   |
| - |

**User Management & Permissions**

|   |
| - |

Multi-column role permission grid, account status toggles.

|   |
| - |

Avoid wide matrix tables. Use expandable accordion sections per user profile with standard iOS/Android style toggle switches for permissions (View, Edit, Delete, Approve).

|   |
| - |

**Master Data Setup**

|   |
| - |

Harvester rates per acre, crop types, pump vendors, village lists.

|   |
| - |

Organize setup lists using search-enabled list views with floating add buttons and inline quick-edit bottom drawers.

## 6. Field Reliability, Offline Readiness & Direct-Sunlight Ergonomics

|   |
| - |

**Field UX Domain**

|   |
| - |

**Real-World Field Risk**

|   |
| - |

**Required Implementation Specification**

|   |
| - |

**Offline & Spotty 4G Connectivity**

|   |
| - |

Harvesters work in remote rural areas. Network dropouts cause lost work logs, failed fuel entries, or freezing screens.

|   |
| - |

Implement Service Worker caching and local device storage (IndexedDB/LocalForage). Queue pending work logs, fuel entries, and customer signatures offline with a persistent banner: "Working Offline • X logs queued". Auto-sync seamlessly with retry-backoff once connectivity resumes.

|   |
| - |

**Direct Sunlight Ergonomics**

|   |
| - |

Operators cannot read soft-gray secondary text (#6b7280) under bright midday sunlight.

|   |
| - |

Enforce an ultra-high-contrast outdoor theme. Set primary values, rupee figures, and status chips to pure black (#111827) and dark slate (#334155). Increase font weight to 600+ for all machine identifiers, dates, and amounts.

|   |
| - |

**Virtual Keyboard Obscurity**

|   |
| - |

Opening the virtual numeric keyboard pushes form action buttons (Save, Submit, Next) below the visible fold.

|   |
| - |

Anchor primary form action buttons to a sticky footer bar docked directly above the virtual keyboard (utilizing VisualViewport API). Add auto-centering scroll mechanics on input focus events.

|   |
| - |

**Camera Slip & Receipt Compression**

|   |
| - |

Direct phone camera uploads produce 6-12 MB RAW images, timing out on 2G/3G networks and filling server storage.

|   |
| - |

Integrate client-side canvas image compression. Automatically downscale captured diesel bills and meter photos to max 1280px resolution and < 350 KB JPEG format before the upload request triggers.

|   |
| - |

**Destructive Action Prevention**

|   |
| - |

Bumpy tractor cabins and dirty fingers cause accidental taps on delete, dispatch cancel, or closing finalization buttons.

|   |
| - |

Replace immediate single-tap deletions with a two-step slide-to-confirm interaction or explicit bottom-sheet confirmation modal with 2-second hold-to-confirm for daily register locks.

## 7. Key Technical Implementation Checklist

- **Viewport Meta Tag:** Ensure viewport-fit=cover is declared to support modern notched devices.
- **Minimum Touch Targets:** Enforce a minimum dimensions of 48 × 48 CSS pixels across all clickable icons, navigation tabs, and form buttons.
- **Input Types:** Assign explicit numeric (inputmode="decimal" or inputmode="numeric") keyboards for currency, meter readings, and phone numbers.
- **Fixed Navigation Insets:** Anchor bottom navigation using CSS environment variables (env(safe-area-inset-bottom)) to prevent overlaps with system gesture bars.
- **Haptic Touch Feedback:** Add subtle vibration feedback (navigator.vibrate(10)) on primary action completions (Save, Start Job, Confirm Payment) where supported.