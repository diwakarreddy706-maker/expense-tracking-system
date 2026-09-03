# EXPENSE TRACKING & MANAGEMENT SYSTEM
## System Architecture & Technical Design Document

---

## 1. System Overview
**Expense Tracking & Management System** (`expense_tracking`) is structured as a modular, high-integrity financial application utilizing a layered Model-View-Template (MVT) design with a dedicated **Service/Business Logic Layer** and a **Central Financial Transaction Ledger** (`account_transactions`). 

The architecture enforces single-source-of-truth calculations, ACID-compliant database transactions, fixed-precision arithmetic, and strict role-based access control (RBAC).

---

## 2. Architecture Style & High-Level Paradigm

```
+-----------------------------------------------------------------------+
|                           CLIENT TIER                                 |
|  Responsive Browser UI (Bootstrap 5.3, Vanilla JS, Chart.js 4.x)      |
+-----------------------------------▲-----------------------------------+
                                    │ HTTPS (SSR Templates + JSON API)
+-----------------------------------▼-----------------------------------+
|                        PRESENTATION LAYER                             |
|  Django URL Routers -> Class-Based & Functional Views -> Templates   |
+-----------------------------------▲-----------------------------------+
                                    │ Invokes
+-----------------------------------▼-----------------------------------+
|                   SERVICE & BUSINESS LOGIC LAYER                      |
|  • Central Financial Calculation Service (Single Source of Truth)     |
|  • Authoritative Account Ledger & Reconciliation Service              |
|  • Machine Operating Cost (TCO) & Fuel Consumption Service           |
|  • Customer Receivable & Supplier Payable Settlement Service          |
|  • Scoped Daily Closing & Snapshot Reconciliation Service             |
|  • Financial Reversal & Correction Engine                             |
|  • Multi-Format Report & Export Engine (PDF / Excel / CSV)            |
|  • Audit & Compliance Interceptor                                     |
+-----------------------------------▲-----------------------------------+
                                    │ ORM Calls
+-----------------------------------▼-----------------------------------+
|                          DATA ACCESS LAYER                            |
|  Django ORM Models (DECIMAL(15,2), Custom Managers, Soft Deletes)    |
+-----------------------------------▲-----------------------------------+
                                    │ SQL Queries (Transactions / Row Locks)
+-----------------------------------▼-----------------------------------+
|                         DATABASE LAYER                                |
|  MySQL 8.0+ (InnoDB Engine, UTF8MB4, Row Locking, ACID Compliance)    |
+-----------------------------------------------------------------------+
```

---

## 3. Detailed Technology Stack

| Component | Selected Technology | Technical Justification |
| :--- | :--- | :--- |
| **Backend Language** | Python 3.11+ | High performance, native `decimal` fixed-point arithmetic, enterprise stability |
| **Web Framework** | Django 5.x | Security defaults (CSRF, XSS, SQLi protection), robust ORM, session management |
| **Database** | MySQL 8.0+ (InnoDB) | Full ACID transaction guarantees, row-level locking (`SELECT FOR UPDATE`), foreign key integrity |
| **Frontend Framework**| Bootstrap 5.3 + Vanilla JS | Ultra-fast client rendering, zero Node.js build dependencies, responsive mobile & desktop UI |
| **Data Visualizations**| Chart.js 4.x | Lightweight, responsive HTML5 canvas charting with zero external dependencies |
| **Spreadsheet Engine** | `openpyxl` & Python `csv` | Native formatted Excel (.xlsx) and streaming CSV generation |
| **PDF Generation** | `ReportLab` / `WeasyPrint` | Production-ready, printable, pixel-accurate financial statements |
| **Authentication** | Django Auth + Session Cookies | Secure HTTP-only session cookies with PBKDF2 SHA256 password hashing |
| **Authorization** | Django RBAC (Groups & Perms) | Server-side role validation (`OWNER`, `ACCOUNTANT`, `MANAGER`, `EMPLOYEE`) |

---

## 4. Application Directory & Project Structure

```
expense_tracking_project/
├── manage.py
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── expense_tracking_core/     # Main Project Configuration
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py            # Common settings (apps, middleware, templates)
│   │   ├── development.py     # Dev settings (DEBUG=True, local DB)
│   │   └── production.py      # Prod settings (Security headers, MySQL prod)
│   ├── urls.py                # Root routing
│   ├── wsgi.py
│   └── asgi.py
├── static/                    # Global Static Assets
│   ├── css/
│   │   ├── bootstrap.min.css
│   │   ├── custom.css         # Dark theme & tabular numeric typography
│   │   └── print.css          # A4 Print-optimized stylesheet
│   ├── js/
│   │   ├── bootstrap.bundle.min.js
│   │   ├── chart.min.js
│   │   ├── dashboard_charts.js
│   │   └── app.js             # Modals, AJAX helpers, quick-expense logic
│   └── images/
│       └── logo.png
├── media/                     # Uploaded Receipts & Documents
│   ├── receipts/
│   └── machine_docs/
├── templates/                 # Global Templates & Layouts
│   ├── base.html              # Master layout (Sidebar, Navbar, Toasts)
│   ├── components/            # Reusable UI fragments (Modals, KPI cards)
│   └── errors/                # 400, 403, 404, 500 error templates
└── apps/                      # Modular Business Applications
    ├── accounts/              # User Authentication, Profiles & Roles
    ├── dashboard/             # Executive Overview & Summary Endpoints
    ├── expenses/              # Expense Categories, General & Quick Expense
    ├── machines/              # Machine Registry & Operating Cost (TCO)
    ├── fuel/                  # Fuel & Lubricants Logging (1-to-1 with Expense)
    ├── employees/             # Employee Profiles, Wages & Advance Ledger
    ├── finance/               # Central Ledger, Accounts, Transfers, Receivables, Payables, Daily Closing
    ├── budgets/               # Budget Limits & Threshold Warnings
    ├── reports/               # Financial Statements & Exporters (PDF/Excel/CSV)
    └── audit/                 # Audit Logging & Event Interceptors
```

---

## 5. Django Apps & Responsibilities

1. **`apps.accounts`:** User authentication, profiles, role management (`OWNER`, `ACCOUNTANT`, `MANAGER`, `EMPLOYEE`), and session security.
2. **`apps.dashboard`:** Executive summary view, today's financial summary widget, and Chart.js aggregation endpoints.
3. **`apps.expenses`:** Category master, general expense CRUD, mobile Quick Expense entry, receipt attachments, and credit expense handling.
4. **`apps.machines`:** Agricultural equipment master, meter tracking (hours/KM), maintenance history, and machine operating cost (TCO) analytics. (Machine revenue and profit are deferred to V2).
5. **`apps.fuel`:** Fuel & Lubricants intake logs (Diesel, Petrol, Engine Oil, Hydraulic Oil). Enforces 1-to-1 atomic creation of linked `Expense` and `account_transactions` records.
6. **`apps.employees`:** Staff registry, wage accruals (`SALARY_ACCRUAL`), advance disbursals (`ADVANCE_PAYOUT`), salary settlements (`SALARY_SETTLEMENT`), and running outstanding calculations.
7. **`apps.finance`:** 
   - Central Financial Ledger (`account_transactions`).
   - Business Accounts (Cash, Bank, UPI) and atomic inter-account transfers.
   - Customer Receivables & Payment History (`customer_payments`).
   - Supplier Payables & Payment History (`supplier_payments`).
   - Scoped Daily Financial Closing (`CASH_ACCOUNT`, `BANK_ACCOUNT`, `UPI_ACCOUNT`, `CONSOLIDATED`).
   - Financial Reversal and Correction service.
8. **`apps.budgets`:** Monthly category budget allocation and visual warning thresholds (80% / 100%).
9. **`apps.reports`:** Comprehensive reporting engine and multi-format exporters (PDF, Excel, CSV, Print).
10. **`apps.audit`:** Automatic signal interceptors capturing user mutations, IP addresses, and before/after JSON diffs.

---

## 6. Service & Business Logic Layer Architecture

In compliance with **Rule 10 (Single Authoritative Calculation Service)**, views must never perform direct business calculations. All financial math is encapsulated in dedicated service classes:

```
apps/
└── finance/
    └── services/
        ├── balance_service.py       # Computes Authoritative Account & Total Balances
        ├── ledger_service.py        # Writes to account_transactions with Row Locking
        ├── transfer_service.py      # Executes Atomic Inter-Account Transfers (Rule 2)
        ├── closing_service.py       # Computes Scoped Daily Closing & Discrepancies
        ├── receivable_service.py    # Records Invoices & Settle Customer Payments
        ├── payable_service.py       # Records Bills & Settle Supplier Payments
        └── reversal_service.py      # Executes Auditable Financial Reversals
└── expenses/
    └── services/
        └── expense_service.py       # Validates & Logs Expenses with Ledger Debits
└── machines/
    └── services/
        └── tco_service.py           # Computes Machine Operating Cost (Fuel + Parts + Wages)
```

### Central Financial Ledger Contract
```python
# Conceptual Service Contract
class FinancialCalculationService:
    @staticmethod
    def get_account_balance(account_id: int) -> Decimal:
        """
        Calculates authoritative balance from the central ledger:
        Opening Balance + SUM(CREDITS) - SUM(DEBITS)
        """
        ...

    @staticmethod
    def calculate_daily_summary(business_date: date, scope: str, account_id: int = None) -> dict:
        """
        Computes opening, external inflows, external outflows,
        transfers in/out, and expected closing for the selected scope.
        """
        ...
```

---

## 7. Central Financial Ledger & Account Balance Architecture

### Authoritative Ledger Principle
- The `account_transactions` table is the **single source of truth** for all cash, bank, and UPI movements.
- The `accounts.current_balance` field is a **derived cache value** maintained for performance, which must strictly reconcile with `account_transactions`.
- Opening balances are initialized via `OPENING_BALANCE` entries in `account_transactions` with `opening_balance_date`.

### Non-Duplication Accounting Rules
1. **Customer Receivables:** Invoice creation records expected inflow/revenue. When `customer_payments` is logged, the selected account is credited and receivable balance decreased; it **does NOT create duplicate revenue**.
2. **Supplier Payables:** Supplier bill creation records the expense and payable liability. When `supplier_payments` is logged, the selected account is debited and payable balance decreased; it **does NOT create a duplicate expense**.
3. **Inter-Account Transfers:** Transfers generate `TRANSFER_OUT` (debit source) and `TRANSFER_IN` (credit destination) ledger records. They adjust account balances but are **strictly excluded from revenue and expenses**.

---

## 8. Financial Reversal & Correction Architecture

To eliminate silent modifications of financial history, the system enforces a strict reversal pattern:
```
[Original Transaction] ──(Reversal Requested)──> [REVERSAL Ledger Entry] ──(Correction)──> [New Corrected Entry]
```
- A `REVERSAL` transaction entry is created in `account_transactions` offsetting the original debit/credit.
- The original record is flagged as reversed with audit links.
- The correction event is logged in `audit_logs` with action `REVERSAL` and user justification.

---

## 9. Scoped Daily Closing Architecture

Daily closing supports 4 explicit scopes to prevent mixing physical cash counts with digital bank balances:
1. `CASH_ACCOUNT`: Reconciles cash box opening, cash receipts, cash expenses, cash withdrawals/deposits against **Actual Physical Cash Counted**.
2. `BANK_ACCOUNT`: Reconciles bank opening, online receipts, bank payouts, net transfers against **Actual Bank Statement Balance Verified**.
3. `UPI_ACCOUNT`: Reconciles UPI merchant opening, UPI collections, UPI payouts against **Actual UPI Wallet Balance Verified**.
4. `CONSOLIDATED`: Reconciles total business liquid funds. All inter-account transfers net to zero.

---

## 10. Security & Data Protection Architecture

- **Account Masking:** Bank account and card numbers are displayed in masked format (`XXXX XXXX 4091`) in general UI views.
- **CSRF & Injection Defenses:** `CsrfViewMiddleware` active; 100% parameterization via Django ORM; auto-escaping in templates.
- **Soft-Delete Safety:** Core financial foreign keys use `ON DELETE RESTRICT` or `ON DELETE PROTECT` to prevent cascade deletions.
- **File Upload Security:** MIME-type validation via `python-magic`, 5MB size limit, and UUID file renaming.

---

## 11. Logging Architecture & Namespaces

The standard Python logging hierarchy uses dedicated namespaces:
- `expense_tracking.financial`: Logs all ledger debits/credits, transfers, daily closings, and reversals (`INFO` level).
- `expense_tracking.security`: Logs login/logout events, permission violations, and failed authentications (`WARNING` level).
- `expense_tracking.errors`: Logs unhandled exceptions with full stack traces (`ERROR` level).
