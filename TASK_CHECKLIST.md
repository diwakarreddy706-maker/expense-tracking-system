# EXPENSE TRACKING & MANAGEMENT SYSTEM
## Master Implementation Roadmap & Task Checklist

---

## Strict Implementation Policy
> [!IMPORTANT]
> Tasks are strictly ordered by dependency. No application source code (Python, HTML, JS, CSS, SQL migrations) shall be written until Phase 0 documentation is completely reviewed and approved.

---

## Phase 0: Blueprint & Architecture Finalization (CURRENT PHASE)
- [x] Create comprehensive `PRD.md` (Product Requirements Document).
- [x] Create `ARCHITECTURE.md` (System Architecture & Technical Design).
- [x] Create `DATABASE_SCHEMA.md` (Database Models & Data Dictionary).
- [x] Create `API_ROUTES.md` (Web Routes & RESTful API Specifications).
- [x] Create `UI_UX_SPEC.md` (UI/UX Design System & Theme Specs).
- [x] Create `TASK_CHECKLIST.md` (Master Implementation Roadmap).
- [x] Complete global project name normalization (Removing all legacy references).
- [x] Integrate Central Financial Ledger (`account_transactions`) into data architecture.
- [x] Establish payment history tables (`customer_payments`, `supplier_payments`) and non-duplication rules.
- [x] Define Scoped Daily Financial Closing (`CASH_ACCOUNT`, `BANK_ACCOUNT`, `UPI_ACCOUNT`, `CONSOLIDATED`).
- [x] Map all 37 Functional Acceptance Criteria (`FAC-001` through `FAC-037`).
- [x] Perform final cross-document consistency audit across all 6 files.

---

## Phase 1: Project Foundation & Core Configuration
- [x] Initialize Python virtual environment (`venv`) and install dependencies (`Django`, `mysqlclient`, `python-dotenv`, `openpyxl`, `reportlab`, `pillow`).
- [x] Create Django project structure (`expense_tracking_project`) and modular settings (`expense_tracking_core/settings/` -> `base.py`, `development.py`, `production.py`).
- [x] Configure MySQL 8.x connection in `.env` and verify database connectivity.
- [x] Configure static files (`/static/`), media uploads (`/media/`), and template paths (`/templates/`).
- [x] Set application timezone to `Asia/Kolkata` and currency formatting to INR (`₹`).
- [x] Set up base HTML master template (`base.html`) with Bootstrap 5.3, Bootstrap Icons, and Chart.js 4.x.
- [x] Create core design system stylesheet (`custom.css`) implementing the dark modern palette and tabular numerical typography (`JetBrains Mono`).
- [x] Build reusable UI components: Top navigation, collapsible sidebar, flash toast container, and confirmation modals.

---

## Phase 2: Authentication & Role-Based Access Control (`apps.accounts`)
- [x] Implement custom user profile model extending `auth_user` with canonical `role` (`OWNER`, `ACCOUNTANT`, `MANAGER`, `EMPLOYEE`) and `phone_number`.
- [x] Seed standard user roles and permission groups.
- [x] Build login page view, session management, and logout handler with CSRF validation.
- [x] Create custom permission decorators (`@role_required`) to enforce server-side access control.
- [x] Build user management screen for `OWNER` to create staff accounts and assign roles.
- [x] Implement password change and profile management views.

---

## Phase 3: Master Data Management
- [x] Create `apps.expenses` models: `ExpenseCategory` (Parent and Subcategories with color hex and icons).
- [x] Seed default expense categories (Fuel & Lubricants, Machine Maintenance, Spare Parts, Wages, Shop Supplies, Electricity, Rent, Taxes, Transport).
- [x] Create `apps.machines` models: `MachineType` and `Machine` (with hour-meter tracking, registration, and status).
- [x] Create `apps.employees` model: `Employee` (with role, wage type, base rate, and non-sensitive V1 fields).
- [x] Create `apps.finance` models: `Account` (Cash box, Banks, UPI wallets with `opening_balance` and `opening_balance_date`).
- [x] Create `Customer` and `Supplier` master tables for client and vendor records.
- [x] Build responsive CRUD screens and modals for all master entities.

---

## Phase 4: Central Financial Ledger & Core Expense Engine
- [x] Create `account_transactions` model with direction (`DEBIT`/`CREDIT`), transaction types, and indexes.
- [x] Implement authoritative `FinancialCalculationService` in `apps.finance.services.balance_service` (`Opening + SUM(Credits) - SUM(Debits)`).
- [x] Create `Expense` model with `DECIMAL(15,2)` precision, foreign keys, and soft deletion (`is_deleted`).
- [x] Implement `ExpenseService.record_expense()` inside atomic database transactions (`@transaction.atomic`).
- [x] Enforce account balance validation upon expense creation (preventing overdrafts on cash accounts).
- [x] Implement Quick Expense mobile workflow (`/api/expenses/quick/`) for field entry in under 20 seconds.
- [x] Implement financial reversal service (`ReversalService.reverse_expense()`) creating compensating ledger entries.
- [x] Build secure receipt file upload pipeline with MIME type verification and 5MB cap.
- [x] Create expense list view with multi-parameter filters (Search, Date range, Category, Machine, Account, Payment method).

---

## Phase 5: Dedicated Fuel & Lubricants Module (`apps.fuel`)
- [x] Create `FuelEntry` model supporting diesel, petrol, engine oil, and hydraulic oil.
- [x] Implement automated server-side computation: `total_amount = quantity * unit_price`.
- [x] Enforce 1-to-1 atomic creation: Inserting a `FuelEntry` automatically creates a linked `Expense` and `account_transactions` debit.
- [x] Build fuel entry logging form with live auto-calculation of total amount on quantity/rate input.
- [x] Create fuel history datagrid with machine filters and date range selectors.
- [x] Build fuel analytics service calculating total volume, average diesel rate, and cost-per-hour per machine.

---

## Phase 6: Employee Payroll, Wages & Advance Ledger (`apps.employees`)
- [x] Create `EmployeePayment` model supporting `SALARY_ACCRUAL`, `ADVANCE_PAYOUT`, and `SALARY_SETTLEMENT`.
- [x] Implement real-time balance computation: `Outstanding = Accrued - Advances - Settlements`.
- [x] Build employee profile passbook view displaying complete chronological wage & advance history.
- [x] Implement advance disbursal modal with automatic cash/bank account deduction and expense logging.
- [x] Build monthly salary settlement tool with automated net balance clearing.

---

## Phase 7: Business Accounts, Balance Engine & Fund Transfers (`apps.finance`)
- [x] Initialize account opening balances as `OPENING_BALANCE` entries in `account_transactions`.
- [x] Build accounts dashboard displaying live cards with masked account numbers (`XXXX XXXX 4091`).
- [x] Create `AccountTransfer` model for inter-account fund movements.
- [x] Implement `TransferService.execute_transfer()` inside atomic transaction (Debit Source via `TRANSFER_OUT`, Credit Destination via `TRANSFER_IN`).
- [x] Enforce **Rule 2**: Strictly isolate transfers from business income/expense totals.
- [x] Create account passbook / statement view showing chronological debits, credits, and running balances.

---

## Phase 8: Receivables, Payables & Payment History
- [x] Create `Receivable` and `CustomerPayment` models (`customer_payments`).
- [x] Enforce customer payment accounting rule: Credits account and reduces receivable; does NOT create duplicate revenue.
- [x] Create `Payable` and `SupplierPayment` models (`supplier_payments`).
- [x] Enforce supplier payment accounting rule: Debits account and reduces payable; does NOT create duplicate expense.
- [x] Build receivable dashboard with payment status badges (`UNPAID`, `PARTIAL`, `PAID`) and aging indicators.
- [x] Build supplier payable dashboard with due dates and payment settlement modals.

---

## Phase 9: Scoped Daily Financial Closing Reconciliation (`apps.finance`)
- [x] Create `DailyClosing` model with `scope` (`CASH_ACCOUNT`, `BANK_ACCOUNT`, `UPI_ACCOUNT`, `CONSOLIDATED`).
- [x] Implement `ClosingService.calculate_daily_summary(date, scope, account_id)` to compute expected closing balances.
- [x] Build daily closing reconciliation interface with scope tabs and breakdown cards.
- [x] Implement physical count / balance verification input with live discrepancy calculation (`Actual - Expected`).
- [x] Enforce mandatory explanation notes when `discrepancy != 0.00`.
- [x] Lock and freeze daily closing record upon submission with user and timestamp audit.
- [x] Build historical daily closing logbook with discrepancy status tags.

---

## Phase 10: Budget Planning & Threshold Controls (`apps.budgets`)
- [x] Create `Budget` and `BudgetItem` models for monthly category allocations.
- [x] Implement budget variance service comparing allocated budget vs. actual expenses.
- [x] Build budget management interface to set monthly category spending limits.
- [x] Create visual progress bars with threshold color changes (Green < 80%, Amber 80-100%, Red > 100%).
- [x] Add over-budget warning alerts on expense entry when budget is exceeded.

---

## Phase 11: Executive Dashboard & Real-Time Analytics (`apps.dashboard`)
- [x] Build `Today's Financial Summary` card widget (Opening, Inflow, Expense, Transfers, Expected Closing, Closing Status).
- [x] Build executive KPI cards: `Available Balance`, `Monthly Expense`, `Yearly Expense`.
- [x] Build secondary operational cards: `Fuel & Lubricants`, `Machine Maintenance`, `Employee Wages`, `General Overhead`.
- [x] Build actionable widgets: `Today's Top Expenses`, `To Receive`, `To Pay`, `Today's Closing Status`.
- [x] Create JSON analytics endpoints (`/api/dashboard/summary/`, `/api/dashboard/charts/`).
- [x] Integrate Chart.js 12-month expense trend line/area chart with budget ceiling.
- [x] Integrate Chart.js category distribution doughnut chart.

---

## Phase 12: Comprehensive Financial Reports & Multi-Format Exporters (`apps.reports`)
- [x] Create unified reporting engine querying the shared calculation service.
- [x] Build report configuration portal with date range presets and multi-filter criteria.
- [x] Implement streaming CSV export for raw financial data ingestion.
- [x] Implement styled Excel (`.xlsx`) export using `openpyxl` with custom headers, cell borders, and formulas.
- [x] Implement PDF export using `ReportLab` / `WeasyPrint` with company header, KPI summary boxes, and tables.
- [x] Create print-optimized CSS stylesheet (`@media print`) for clean A4 browser printing.

---

## Phase 13: System Audit Logging & Security Hardening (`apps.audit`)
- [x] Create `AuditLog` model capturing `user`, `action` (`CREATE`, `UPDATE`, `SOFT_DELETE`, `RESTORE`, `LOGIN`, `LOGOUT`, `EXPORT`, `TRANSFER`, `PAYMENT`, `REVERSAL`, `DAILY_CLOSE`), `entity_type`, `entity_id`, `changes_json`, and `ip_address`.
- [x] Implement Django signal hooks and service interceptors to automatically log financial mutations.
- [x] Build searchable audit log viewer for `OWNER` role.
- [x] Verify CSRF protection across all forms and AJAX requests.
- [x] Enforce security HTTP headers (`X-Frame-Options`, `X-Content-Type-Options`, `Content-Security-Policy`).
- [x] Configure rotating file loggers (`expense_tracking.financial`, `expense_tracking.security`, `expense_tracking.errors`).

---

## Phase 14: Comprehensive Automated Testing & Financial Edge Cases
- [x] **Expense Edge Cases:** Zero amount, negative amount, insufficient account balance, credit expense, duplicate submit, soft deletion, reversal.
- [x] **Transfer Edge Cases:** Same source/destination, zero amount, negative amount, insufficient funds, duplicate transfer, P&L exclusion verification.
- [x] **Receivable Edge Cases:** Partial payment, full payment, overpayment attempt, duplicate payment, account credit verification, zero duplicate income.
- [x] **Payable Edge Cases:** Partial payment, full payment, overpayment attempt, duplicate payment, account debit verification, zero duplicate expense.
- [x] **Daily Closing Edge Cases:** Balanced (0 discrepancy), surplus, deficit, missing previous closing, duplicate closing attempt, locked record mutation attempt, scoped vs consolidated closing.
- [x] **Fuel & Lubricants Edge Cases:** Zero quantity, negative quantity, meter reading validation, duplicate entry, server-side unit price math, linked 1-to-1 expense creation.
- [x] **Employee Payroll Edge Cases:** Salary accrual (no cash debit), advance payout (cash debit), settlement payout, outstanding balance math.
- [x] **Decimal Precision Tests:** Verify `DECIMAL(15,2)` precision across 10,000+ compounding transactions with 0.00 float rounding error.
- [x] **Role & Security Tests:** Verify `EMPLOYEE` and `MANAGER` are strictly forbidden from settings, user management, and audit logs.
- [x] **Responsive & Print Tests:** Verify layout at 375px, 768px, 1200px, 1920px and print stylesheet on A4.

---

## Phase 15: Production Readiness & Deployment
- [ ] Configure `production.py` settings (`DEBUG=False`, `ALLOWED_HOSTS`, secure session cookies).
- [ ] Configure Nginx reverse proxy with SSL/TLS and static asset caching.
- [ ] Set up Gunicorn WSGI service unit.
- [ ] Implement automated daily MySQL database backup script with off-site sync.
- [ ] Validate final user acceptance against all 37 Functional Acceptance Criteria (`FAC-001` through `FAC-037`).
