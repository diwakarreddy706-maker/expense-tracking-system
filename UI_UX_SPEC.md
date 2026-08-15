# EXPENSE TRACKING & MANAGEMENT SYSTEM
## UI/UX Design System & Frontend Specification

---

## 1. Design Philosophy & Visual Identity
**Expense Tracking & Management System** is designed with a sleek, high-contrast, dark-themed financial interface optimized for agricultural enterprise management. The visual hierarchy combines deep charcoal slate surfaces (`#0D1117`), elevated card panels (`#161B22`), crisp emerald accents (`#10B981`), and monospace tabular numerals (`JetBrains Mono`) for instantaneous, jitter-free financial readability across mobile field devices and desktop monitors.

---

## 2. Color Palette & CSS Design Tokens

```css
:root {
  /* Canvas & Structural Backgrounds */
  --theme-bg-base:        #0D1117;   /* Deep canvas background */
  --theme-surface-card:   #161B22;   /* Elevated card & modal surface */
  --theme-surface-hover:  #21262D;   /* Interactive hover state */
  --theme-border:         #30363D;   /* Subtle structural border */

  /* Functional & Status Accents */
  --theme-primary:        #10B981;   /* Emerald Green - Positive flow, Primary CTA */
  --theme-primary-glow:   rgba(16, 185, 129, 0.15);
  --theme-warning:        #F59E0B;   /* Harvest Amber - Fuel, Pending, Over-budget 80% */
  --theme-danger:         #EF4444;   /* Crimson Red - Expenses, Deficits, Alerts */
  --theme-info:           #3B82F6;   /* Electric Blue - Machines, Transfers */
  --theme-purple:         #8B5CF6;   /* Royal Violet - Employee Wages & Advances */

  /* Typography Colors */
  --theme-text-main:      #F0F6FC;   /* High-contrast crisp white */
  --theme-text-muted:     #8B949E;   /* Secondary labels & captions */
  --theme-text-dim:       #484F58;   /* Disabled states & placeholders */
}
```

---

## 3. Typography & Numerical Formatting
- **Interface Font:** `'Inter', -apple-system, BlinkMacSystemFont, sans-serif` (Optimal UI legibility).
- **Financial & Monetary Numerals:** `'JetBrains Mono', 'Roboto Mono', monospace` with `font-variant-numeric: tabular-nums` (Guarantees strict vertical digit alignment across tables and cards).
- **Masked Account Formatting:** Bank account numbers are rendered in masked format across general UI screens: `XXXX XXXX 4091`.

---

## 4. Master Layout Architecture

```
+-----------------------------------------------------------------------------+
| System Logo    |  Global Search (Ctrl+K)   | [+ Quick Expense] | Profile ▾  | (Top Navbar)
+----------------+------------------------------------------------------------+
| [≡] Dashboard  |                                                            |
| [$] Expenses   |  BREADCRUMB / PAGE TITLE                                   |
| [⛽] Fuel & Lube|  ========================================================  |
| [🚜] Machines   |  ROW 1: TODAY'S FINANCIAL SUMMARY & AVAILABLE BALANCE      |
| [👥] Employees  |  ========================================================  |
| [🏦] Accounts   |  ROW 2: OPERATIONAL EXPENSE BREAKDOWN (Fuel|Maint|Wage|Gen)|
| [🎯] Budgets    |  ========================================================  |
| [📥] Receivables|  ROW 3: ANALYTICS (12-Mo Trend Line | Category Doughnut)  |
| [📤] Payables   |  ========================================================  |
| [📋] Reports    |  ROW 4: TODAY'S TOP EXPENSES | TO RECEIVE | TO PAY | CLOSING|
| [🔒] Closing    |                                                            |
| [⚙] Settings   |                                                            |
+----------------+------------------------------------------------------------+
  (Sidebar)                                (Main Dynamic Content Canvas)
```

---

## 5. Detailed Dashboard Layout & Screen Components

### Row 1: Today's Financial Summary & Available Balance (Grid Layout)
1. **Today's Financial Summary Card (Wide 8-Col Widget):**
   - Compact ledger summary: `Opening (₹1,25,430.00)` + `Inflow (₹25,000.00)` - `Expense (₹4,870.00)` = `Expected Closing (₹1,45,560.00)`.
   - Live Status Badge: `PENDING`, `BALANCED`, `SURPLUS`, `DEFICIT`.
2. **Total Available Liquid Balance (4-Col Card):**
   - Prominent large figure: `₹1,45,250.00` in emerald green (`#10B981`).
   - Breakdown chips: Cash Box (`₹12,400`), Bank A/c 4091 (`₹98,600`), UPI (`₹34,250`).

### Row 2: Operational Expense Breakdown Cards (4-Column Grid)
1. **Fuel & Lubricants:** `₹32,400.00` (365 L Diesel, 20 L Hydraulic Oil) - Amber Accent.
2. **Machine Maintenance & Parts:** `₹18,200.00` (5 Equipment Serviced) - Blue Accent.
3. **Employee Wages & Advances:** `₹19,500.00` (8 Active Operators) - Purple Accent.
4. **General & Shop Overhead:** `₹5,500.00` (Electricity, Rent, Taxes) - Grey Accent.

### Row 3: Visual Analytics Canvas (8-Col + 4-Col Grid)
- **Left (8-Col): 12-Month Expense Trend (Chart.js Line/Bar):**
  - Smooth curved area chart comparing Monthly Actual Expense against monthly budget ceiling.
  - Interactive tooltip displaying exact rupee figures and percentage change vs previous month.
- **Right (4-Col): Category Spending Distribution (Chart.js Doughnut):**
  - High-contrast doughnut chart displaying proportions for Fuel (42%), Maintenance (24%), Wages (26%), General (8%).
  - Center cutout displaying Total Monthly Spend.

### Row 4: Actionable Financial Widgets (4-Column Grid)
- **Column 1: Today's Top Expenses:** Ranked list of the 5 largest expenses logged today with category badges.
- **Column 2: To Receive (Receivables):** Summary of pending farmer bills (`₹84,000.00`) with overdue alert indicators.
- **Column 3: To Pay (Payables):** Summary of due supplier bills (`₹31,500.00`) with due dates.
- **Column 4: Today's Closing Status:** Quick action panel with button **[Proceed to Daily Closing]**.

---

## 6. Quick Expense Entry Workflow (Mobile Optimized)

- **Target:** Data logging in under 20 seconds on mobile devices.
- **Trigger:** Accessible via global header **[+ Quick Expense]** button or mobile bottom floating action button (FAB).
- **Minimal Field Set:**
  1. `Amount` (Auto-focused, large numeric input with `₹` prefix).
  2. `Category` (Visual icon grid: Fuel, Repairs, Wages, Supplies, Other).
  3. `Account` (Dropdown defaulting to `Main Cash Box`).
  4. `Payment Method` (Pill selector: Cash, UPI, Bank, Credit).
  5. `Machine` (Optional quick dropdown).
  6. `Employee` (Optional quick dropdown).
  7. `Description` (Optional one-line text).
- **Submission:** Live client-side decimal validation, instant AJAX submit, and non-blocking toast notification.

---

## 7. Scoped Daily Financial Closing Interface

- **Scope Selector Tabs:** `[Consolidated Business]` | `[Cash Box]` | `[Bank Accounts]` | `[UPI Wallets]`.
- **Dynamic Calculation Box:**
  - `Opening Balance` (Auto-carried from previous verified closing).
  - `+ Inflows` (Customer payments & receipts).
  - `- Outflows` (Expenses, supplier payouts, advance disbursals).
  - `+/- Transfers In/Out` (For individual account scopes).
  - `= Expected Closing Balance` (Highlighted in Blue).
- **Physical Verification Input:**
  - Label: **"Actual Cash Counted"** (for Cash scope) / **"Actual Account Balance Verified"** (for Bank/UPI).
  - Input field formatted with tabular numbers.
- **Live Discrepancy Indicator:**
  - Green `BALANCED (₹0.00)` if exact match.
  - Amber `SURPLUS (+₹...)` if physical exceeds expected.
  - Red `DEFICIT (-₹...)` if physical is less than expected.
- **Mandatory Notes:** Textarea is strictly required if Discrepancy != 0.
- **Lock Confirmation:** Modal warning that submitted closings freeze financial records for that business date.

---

## 8. Financial Reversal & Destruction Confirmation Modals

- **Rule 7 & 8 Protection:** Silent deletion of financial records is strictly forbidden.
- **Reversal Modal Dialog:**
  - Displays original transaction code, amount, and impacted account.
  - Requires user to enter mandatory **Reason for Reversal**.
  - Clearly explains that a compensating `REVERSAL` transaction will be posted to the ledger.
  - Emerald button **[Confirm Reversal]** / Ghost button **[Cancel]**.

---

## 9. Comprehensive UX States

| State | Visual Treatment & Behavior |
| :--- | :--- |
| **Loading State** | Shimmering skeleton placeholders matching table rows, KPI cards, and chart canvas geometry. |
| **Empty State** | Clean SVG illustration, friendly descriptive text (*"No transactions found for this date filter"*), and prominent **[+ Log Expense]** CTA. |
| **Error State** | Non-blocking crimson toast alert on top-right; inline red input borders with explicit validation helper text. |
| **Success State** | Quick emerald toast alert (*"Expense EXP-20260815-0042 recorded and ₹1,200 debited from Cash Box"*). |
| **Warning State** | Amber pill banner when category budget exceeds 80% or when daily closing discrepancy is non-zero. |

---

## 10. Responsive Breakpoint Rules

- **Desktop (>= 1200px):** Full sidebar (240px width), 4-column KPI cards, side-by-side charts, full data tables.
- **Tablet (768px - 1199px):** Collapsible sidebar rail (64px), 2-column KPI cards, vertically stacked charts.
- **Mobile (< 768px):** Off-canvas slide drawer, 1-column cards, horizontal scroll on tables with sticky first column, bottom floating action button (FAB) for Quick Expense.
- **Print View (`@media print`):** Stripped dark backgrounds to clean white, black high-contrast text, hidden sidebars/buttons, formatted for standard A4 margins.
