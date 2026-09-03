# EXPENSE TRACKING & MANAGEMENT SYSTEM
## Product Requirements Document (PRD)

---

## 1. Executive Summary
**Expense Tracking & Management System** (`expense_tracking`) is a full-stack, enterprise-grade financial management and operational cost tracking platform built for agricultural enterprises, machinery custom-hiring centers, farm logistics, and agro-service businesses.

Agricultural enterprises operate under heavy operational complexity: capital-intensive mobile machinery (tractors, combine harvesters, tillers), high-volume fuel consumption, seasonal workforce, spare-part suppliers, multi-account cash and digital liquidity (Cash box, multiple Bank accounts, UPI wallets), receivables from farmers, and supplier payables.

This system centralizes operational expense management, fuel & lubricant accounting, machine-level operating costs, workforce wage and advance ledgers, multi-account ledger reconciliation, and strict daily financial closing into one authoritative, auditable financial system.

---

## 2. Product Vision
To provide agricultural business owners, managers, and accountants with an authoritative, real-time, zero-leakage financial operating system that eliminates unaccounted cash loss, tracks machine operational costs, audits fuel consumption, enforces wage/advance discipline, and guarantees daily balance reconciliation.

---

## 3. Problem Statement
Agricultural businesses face acute financial tracking issues:
1. **Unattributed Machine Operating Costs:** High-value machinery incurs variable fuel, maintenance, spare parts, and driver wages. Without machine-specific cost attribution, owners cannot calculate true operational cost per hour or per kilometer.
2. **Fuel & Lubricant Pilferage:** Fuel and lubricants are bought across rural pumps and bulk tanks with varying rates and meters. Without linkable log meters and supplier tracking, fuel loss goes undetected.
3. **Cash & Multi-Account Discrepancies:** Transactions occur across physical cash boxes, UPI handles, and multiple bank accounts. Internal transfers often distort revenue or get double-counted as expenses.
4. **Daily Closing Imbalances:** Daily field cash inflows and operational disbursements lead to variance between system expected cash and physical cash in hand.
5. **Labor Advances & Supplier Credit Chaos:** Daily wage workers and field operators frequently take advances against seasonal wages, while vendors supply parts on credit. Without an integrated ledger, tracking outstanding payables and advances results in costly errors.

---

## 4. Product Goals
- Provide 100% financial traceability for every rupee spent, received, or transferred.
- Track Total Cost of Ownership (TCO) and operational cost per hour/KM for every registered machine.
- Enforce strict daily closing protocols to reconcile physical cash and bank balances against ledger records.
- Standardize wage accruals, advance payouts, and settlement tracking for all operators and staff.
- Maintain a single central financial transaction ledger (`account_transactions`) as the single source of truth for all account balances.
- Deliver executive-level analytics and compliance-ready reports (PDF/Excel/CSV/Print).

---

## 5. Product Objectives & Success Metrics
- **Zero Ledger Discrepancy:** 100% of balance movements backed by an immutable ledger entry.
- **Accurate Machine Costing:** 100% of fuel and repair transactions tagged to specific machines.
- **Rapid Field Logging:** Quick Expense logging completed in under 20 seconds on mobile devices.
- **Rigorous Daily Closing:** Reconcile daily financial activity within 5 minutes at end of business day.
- **Data Integrity:** Strict fixed-point decimal arithmetic (`DECIMAL(15,2)`) across all computations with zero floating-point rounding errors.

---

## 6. Target Users & Business Context
Designed for agricultural contracting businesses, farm equipment hiring centers, farm workshops, and rural transport hubs operating in India (Karnataka and nationwide), utilizing INR (₹) currency and Indian Standard Time (`Asia/Kolkata`, UTC+5:30).

---

## 7. User Personas

### Persona 1: Suresh Gowda (Business Owner)
- **Profile:** 48 years old, owns 4 tractors, 2 harvesters, 1 workshop shed, and 12 seasonal operators.
- **Needs:** Executive dashboard on mobile/tablet, daily closing variance alerts, machine operating cost comparisons, monthly expenditure trends, and budget over-run alerts.
- **Pain Point:** Cannot identify which machine is consuming excess maintenance vs. fuel.

### Persona 2: Ramesh Kumar (Head Accountant / Cashier)
- **Profile:** 34 years old, manages daily cash boxes, bank accounts, UPI transfers, supplier payables, and employee payroll.
- **Needs:** Rapid transaction entry, bill/receipt attachment, account balance reconciliation, automated daily closing, receivable aging reports, and export to Excel/PDF.
- **Pain Point:** Manual diary ledgers take hours every evening with recurring cash reconciliation errors.

### Persona 3: Manjunath (Field Operations Manager)
- **Profile:** 31 years old, oversees machinery in the field, diesel refills, operator shifts, and minor emergency repairs.
- **Needs:** Mobile-friendly quick expense entry, fuel & lubricant logging, machine status updates, and operator assignments.
- **Pain Point:** Forgets hour-meter readings and loses paper fuel slips.

---

## 8. User Roles & Canonical Permissions Matrix

The system enforces 4 canonical roles (`OWNER`, `ACCOUNTANT`, `MANAGER`, `EMPLOYEE`):

| Module / Action | OWNER | ACCOUNTANT | MANAGER | EMPLOYEE |
| :--- | :---: | :---: | :---: | :---: |
| **System Settings & User Management** | Full (CRUD) | None | None | None |
| **Master Data (Categories, Machines, Accounts)** | Full (CRUD) | Full (CRUD) | Read Only | None |
| **Customer & Supplier Master** | Full (CRUD) | Full (CRUD) | Read Only | None |
| **General Expenses** | Full (CRUD) | Full (CRUD) | Create / Read | None / Self View |
| **Quick Expense (Mobile Field Entry)** | Full (CRUD) | Full (CRUD) | Create / Read | None |
| **Fuel & Lubricants** | Full (CRUD) | Full (CRUD) | Create / Read | Create Log (Self) |
| **Machine Registry & Maintenance** | Full (CRUD) | Full (CRUD) | Read / Update Status | Read Only |
| **Employee Wages & Advances** | Full (CRUD) | Full (CRUD) | Read Only | None / Self View |
| **Account & Fund Transfers** | Full (CRUD) | Full (CRUD) | Read Only | None |
| **Receivables & Customer Payments** | Full (CRUD) | Full (CRUD) | Read Only | None |
| **Payables & Supplier Payments** | Full (CRUD) | Full (CRUD) | Read Only | None |
| **Daily Closing Submission** | Full (CRUD) | Create / Read | Create / Read | None |
| **Daily Closing Reversal / Admin Unlock**| Full (CRUD) | None | None | None |
| **Financial Budgets** | Full (CRUD) | Full (CRUD) | Read Only | None |
| **Reports & Export (PDF/Excel/CSV)** | Full (CRUD) | Full (CRUD) | Read Only | None |
| **Audit Logs** | Full (Read Only) | None | None | None |

---

## 9. Canonical Master Values & System Enums

All system modules strictly adhere to these canonical enums:

1. **User Roles:** `OWNER`, `ACCOUNTANT`, `MANAGER`, `EMPLOYEE`
2. **Payment Methods:** `CASH`, `BANK_TRANSFER`, `UPI`, `CHEQUE`, `CREDIT`
3. **Business Segments:** `GENERAL`, `FARM_OPERATIONS`, `MACHINERY_RENTAL`, `WORKSHOP_REPAIRS`, `SHOP_RETAIL`, `GENERAL_ADMIN`
4. **Machine Status:** `ACTIVE`, `UNDER_MAINTENANCE`, `IDLE`, `DECOMMISSIONED`
5. **Machine Types:** `TRACTOR`, `COMBINE_HARVESTER`, `MINI_TRACTOR`, `TILLER`, `BALER`, `SPRAYER`, `TRAILER`, `OTHER`
6. **Fuel & Lubricant Types:** `DIESEL`, `PETROL`, `ENGINE_OIL`, `HYDRAULIC_OIL`
7. **Employee Roles:** `TRACTOR_DRIVER`, `HARVESTER_OPERATOR`, `WORKSHOP_MECHANIC`, `SHOP_STAFF`, `ACCOUNTANT`, `MANAGER`, `DAILY_LABOR`
8. **Wage Types:** `MONTHLY_SALARY`, `DAILY_WAGE`, `PER_ACRE_COMMISSION`
9. **Employee Payment Types:** `SALARY_ACCRUAL`, `ADVANCE_PAYOUT`, `SALARY_SETTLEMENT`, `BONUS`
10. **Receivable & Payable Status:** `UNPAID`, `PARTIAL`, `PAID`
11. **Daily Closing Scope:** `CASH_ACCOUNT`, `BANK_ACCOUNT`, `UPI_ACCOUNT`, `CONSOLIDATED`
12. **Daily Closing Status:** `BALANCED`, `SURPLUS`, `DEFICIT`
13. **Audit Actions:** `CREATE`, `UPDATE`, `SOFT_DELETE`, `RESTORE`, `LOGIN`, `LOGOUT`, `EXPORT`, `TRANSFER`, `PAYMENT`, `REVERSAL`, `DAILY_CLOSE`
14. **Transaction Ledger Types:** `OPENING_BALANCE`, `INCOME`, `EXPENSE`, `RECEIVABLE_PAYMENT`, `PAYABLE_PAYMENT`, `EMPLOYEE_PAYMENT`, `TRANSFER_IN`, `TRANSFER_OUT`, `ADJUSTMENT`, `REVERSAL`

---

## 10. Core Modules & Functional Requirements

### Module A: Executive Dashboard & Analytics
- **Summary Widgets:**
  - `Today's Financial Summary`: Opening Balance, Today's Inflow, Today's Expense, Today's Transfers, Expected Closing, Actual Closing, Variance.
  - `Available Balance`: Total liquid funds across all active accounts with masked account numbers (`XXXX XXXX 4091`).
  - `Monthly & Yearly Expenses`: Current month vs previous month trends and fiscal year totals.
  - `Operational Sub-Totals`: Fuel & Lubricants, Machine Maintenance & Parts, Employee Wages & Advances, General Overhead.
  - `Today's Top Expenses`: Ranked list of top expenditures logged today.
  - `To Receive`: Aggregated pending customer receivables with overdue alerts.
  - `To Pay`: Aggregated pending supplier bills with due date alerts.
  - `Today's Closing Status`: Clear visual badge (`PENDING`, `BALANCED`, `SURPLUS`, `DEFICIT`).
- **Interactive Visualizations (Chart.js):**
  - **Expense Trend:** 12-month area chart comparing monthly actual expenses against baseline budget limits.
  - **Category Breakdown:** High-contrast doughnut chart showing percentage distribution.
  - **Machine Operating Cost:** Horizontal bar chart comparing operational costs across all machines.

### Module B: General Expense Management & Quick Expense
- **Quick Expense (Mobile Field Entry):**
  - Minimalist workflow optimized for field/mobile data entry in under 20 seconds.
  - Minimum inputs: `Amount`, `Category`, `Account`, `Payment Method` (defaults to CASH), optional `Machine`, optional `Employee`, optional `Description`.
- **Detailed Expense Entry:**
  - Fields: `Expense Code` (`EXP-YYYYMMDD-XXXX`), `Date`, `Amount` (`DECIMAL(15,2)`), `Category` & `Subcategory`, `Payment Method`, `Account`, `Business Segment`, `Machine` (optional), `Employee` (optional), `Supplier` (optional), `Reference/Invoice No`, `Description`, `Receipt Attachment` (PDF/JPG/PNG max 5MB).
  - Validation: Positive amount (> 0.00). Account required unless payment method is `CREDIT`. If payment is Cash/Bank/UPI, account must have sufficient balance.
- **Credit Expense Rule:** If payment method is `CREDIT`, no immediate account deduction occurs; an associated `Payable` record is created for the selected Supplier.

### Module C: Dedicated Fuel & Lubricants Module
- **Tracking Capabilities:** Refueling logs for diesel, petrol, engine oil, and hydraulic oil.
- **Fields:** `Entry Code` (`FUL-YYYYMMDD-XXXX`), `Date`, `Machine ID` (or `BULK_STORAGE`), `Fuel Type`, `Quantity/Litres` (`DECIMAL(10,2)`), `Price per Unit/Litre` (`DECIMAL(10,2)`), `Total Amount` (Calculated on server: `Quantity * Unit Price`), `Supplier/Pump`, `Account`, `Operator/Driver`, `Meter Reading` (Hour-meter / Odometer), `Receipt`.
- **1-to-1 Atomic Linkage:** Each fuel entry atomically creates exactly one linked `Expense` record in the 'Fuel & Lubricants' category and one `account_transactions` ledger entry.

### Module D: Agricultural Machine Management
- **Master Registry:** `Machine Code` (`MCH-TRAC-01`), `Name & Model`, `Machine Type`, `Registration/Chassis No`, `Status`, `Default Operator`, `Current Meter Reading`, `Meter Unit` (`HOURS`, `KM`), `Purchase Date`, `Purchase Price`.
- **V1 Costing Scope:** Aggregates machine total operating costs, fuel & lubricant costs, maintenance & spare-parts costs, operator wage allocations, cost per operating hour, cost per KM, and expenditure trends.
- **V2 Scope Note:** True machine revenue, machine net profit, and ROI calculations are explicitly deferred to Version 2.0 (when field job invoicing is implemented).

### Module E: Employee Management, Wages & Advances
- **Master Registry:** `Employee Code` (`EMP-001`), `Full Name`, `Phone`, `Role`, `Employment Type`, `Base Rate/Salary` (`DECIMAL(15,2)`), `Joining Date`, `Status`, `Emergency Contact`. (Sensitive government ID numbers like Aadhaar/PAN are excluded from mandatory V1 requirements).
- **Payment Types & Ledger Rules:**
  - `SALARY_ACCRUAL`: Recognizes wage/salary expense; increases employee accrued payable; does NOT debit cash/bank.
  - `ADVANCE_PAYOUT`: Disburses cash/UPI advance to employee; reduces employee outstanding balance; debits selected business account.
  - `SALARY_SETTLEMENT`: Pays out net wage balance; reduces employee outstanding balance; debits selected business account.
- **Employee Outstanding Formula:**
  $$\text{Outstanding Balance} = \text{Total Accrued} - \text{Advances Payouts} - \text{Settlement Payments}$$

### Module F: Central Financial Ledger & Business Accounts
- **Account Master:** `Account Name`, `Account Type` (`CASH`, `BANK_SAVINGS`, `BANK_CURRENT`, `UPI_WALLET`, `PETTY_CASH`), `Account Number / UPI ID` (masked in UI), `Bank Name`, `IFSC`, `Opening Balance`, `Opening Balance Date`, `Current Balance` (derived cache), `Status`.
- **Central Financial Ledger (`account_transactions`):**
  - Authoritative record of every monetary movement.
  - Fields: `account_id`, `transaction_date`, `transaction_type`, `direction` (`DEBIT`, `CREDIT`), `amount`, `reference_type`, `reference_id`, `description`, `created_by_id`, `created_at`.
  - Authoritative Balance Formula:
    $$\text{Account Balance} = \text{Opening Balance} + \sum \text{Credits} - \sum \text{Debits}$$
- **Internal Account Transfers (Rule 2):**
  - Transfer funds from Source Account to Destination Account.
  - Creates two linked ledger records: `TRANSFER_OUT` on Source Account and `TRANSFER_IN` on Destination Account.
  - Strictly excluded from business income and expense totals.

### Module G: Receivables & Customer Payment History
- **Customer Master:** `Customer Code`, `Name`, `Phone`, `Location/Address`, `Notes`, `Status`.
- **Receivable Bills:** `Invoice No`, `Bill Date`, `Due Date`, `Total Amount`, `Received Amount`, `Status` (`UNPAID`, `PARTIAL`, `PAID`).
- **Customer Payments (`customer_payments`):**
  - Records payments against receivables: `receivable_id`, `account_id`, `payment_date`, `amount`, `payment_method`, `reference_no`, `notes`.
  - **Accounting Rule:** Customer invoice records the revenue/inflow expectation. Customer payment decreases receivable balance and credits selected account; it does **NOT** create duplicate revenue.
  - Prevents overpayment (`Payment Amount <= Remaining Receivable Balance`).

### Module H: Payables & Supplier Payment History
- **Supplier Master:** `Supplier Code`, `Name`, `Supplier Type` (`FUEL_PUMP`, `SPARE_PARTS`, `WORKSHOP`, `FERTILIZER`, `OTHER`), `Phone`, `Address`, `Payment Terms`, `Status`.
- **Payable Bills:** `Bill No`, `Bill Date`, `Due Date`, `Total Amount`, `Paid Amount`, `Status` (`UNPAID`, `PARTIAL`, `PAID`).
- **Supplier Payments (`supplier_payments`):**
  - Records payments against payables: `payable_id`, `account_id`, `payment_date`, `amount`, `payment_method`, `reference_no`, `notes`.
  - **Accounting Rule:** Supplier bill records the expense and payable liability. Supplier payment decreases payable balance and debits selected account; it does **NOT** create a duplicate expense entry.
  - Prevents overpayment (`Payment Amount <= Remaining Payable Balance`).

### Module I: Daily Financial Closing
- **Closing Scope:** `CASH_ACCOUNT`, `BANK_ACCOUNT`, `UPI_ACCOUNT`, `CONSOLIDATED`.
- **Formulas by Scope:**
  - *Single Account Closing:*
    $$\text{Expected Closing} = \text{Opening} + \text{Inflows} + \text{Transfer In} - \text{Outflows} - \text{Transfer Out}$$
  - *Consolidated Closing:*
    $$\text{Expected Closing} = \text{Opening} + \text{External Inflows} - \text{External Outflows}$$
    *(Internal transfers net to zero in consolidated scope)*
- **Reconciliation & Variance:**
  - User enters `Actual Cash Counted` (for Cash accounts) or `Actual Account Balance Verified` (for Bank/UPI accounts).
  - $\text{Discrepancy} = \text{Actual Balance} - \text{Expected Balance}$.
  - Status: `BALANCED` ($\text{Discrepancy} = 0$), `SURPLUS` ($> 0$), `DEFICIT` ($< 0$).
  - Mandatory explanation notes required when $\text{Discrepancy} \ne 0$.
  - Finalized closing records are frozen/immutable for non-admin users.

### Module J: Financial Reversals & Correction Mechanism
- To maintain audit integrity, posted financial transactions cannot be silently modified or deleted.
- **Correction Pattern:**
  $$\text{Original Transaction} \longrightarrow \text{REVERSAL Transaction} \longrightarrow \text{Corrected New Transaction}$$
- Reversals generate a `REVERSAL` transaction in `account_transactions` and an audit entry with reason.

### Module K: Budget Planning & Control
- Monthly limits per Category and Machine.
- Utilization alerts: Green (< 80%), Warning Amber (80% - 100%), Critical Red (> 100%).

### Module L: Financial Reports & Export Engines
- Standard Reports: Daily Closing Summary, Monthly Expense Statement, Yearly Financial Overview, Machine Operating Cost (TCO), Fuel & Lubricant Consumption, Employee Wage & Advance Ledger, Category Breakdown, Account Passbook, Receivable Aging, Payable Aging, Budget Variance.
- Multi-Format Export: PDF, Excel (`.xlsx`), CSV, and `@media print` A4 layout.

### Module M: Audit Trail & Compliance
- Captures `user`, `action` (`CREATE`, `UPDATE`, `SOFT_DELETE`, `RESTORE`, `LOGIN`, `LOGOUT`, `EXPORT`, `TRANSFER`, `PAYMENT`, `REVERSAL`, `DAILY_CLOSE`), `entity_type`, `entity_id`, before/after JSON diff, IP address, and timestamp.

---

## 11. The 15 Critical Business Rules

1. **RULE 1 (Fixed-Point Precision):** Money must never use floating-point arithmetic. All monetary fields use `DECIMAL(15,2)` in MySQL and Python `decimal.Decimal`.
2. **RULE 2 (Transfer Exclusion):** Internal fund transfers adjust account balances via `TRANSFER_OUT` and `TRANSFER_IN` ledger entries but must NEVER be classified as revenue or expenses.
3. **RULE 3 (Mandatory Categorization):** Every expense must belong to an active category.
4. **RULE 4 (Fuel-Machine Association):** Every fuel & lubricant entry must link to a specific Machine, or explicitly to `BULK_STORAGE`.
5. **RULE 5 (Machine Maintenance Attribution):** All maintenance and spare parts must link to the corresponding Machine ID for accurate operating cost calculation.
6. **RULE 6 (Employee Traceability):** All wage payouts and advances must be linked directly to an active Employee profile.
7. **RULE 7 (Soft-Deletion Safety):** Financial records are soft-deleted (`is_deleted=True`). Core financial foreign keys use `ON DELETE RESTRICT` / `PROTECT`.
8. **RULE 8 (Mandatory Financial Audit Trail):** All balance modifications, reversals, and closings generate unalterable audit log records.
9. **RULE 9 (Immutability of Closed Periods):** Finalized daily closings are locked against retroactive modifications.
10. **RULE 10 (Single Authoritative Calculation Service):** All financial computations reside in a dedicated service layer (`apps.finance.services.balance_service`) and must never be duplicated across views or templates.
11. **RULE 11 (Daily Closing Snapshot):** Daily closing persists an immutable snapshot of expected balance, verified balance, and discrepancy.
12. **RULE 12 (Engine Uniformity):** Financial reports and dashboard KPI cards must query the exact same business logic service methods.
13. **RULE 13 (Timezone & Localization):** Standardized to Indian Rupee (`₹` / INR) and `Asia/Kolkata` (UTC+5:30) timezone.
14. **RULE 14 (Receivable & Payable Non-Duplication):** Customer payments settle receivables without creating duplicate revenue. Supplier payments settle payables without creating duplicate expenses.
15. **RULE 15 (Server-Side Permission Enforcement):** User authorization is verified server-side on every view and service invocation.

---

## 12. Complete 37 Functional Acceptance Criteria (FAC-001 to FAC-037)

- **FAC-001:** System shall authenticate users with role-based session access (`OWNER`, `ACCOUNTANT`, `MANAGER`, `EMPLOYEE`).
- **FAC-002:** System shall restrict settings, user administration, and audit logs exclusively to `OWNER`.
- **FAC-003:** System shall record general expenses with mandatory `amount`, `category`, `payment_method`, and `account` (unless credit).
- **FAC-004:** Quick Expense interface shall log a valid expense in under 20 seconds with minimal fields on mobile viewports.
- **FAC-005:** System shall prevent cash/bank account overdrafts upon expense submission if balance is insufficient.
- **FAC-006:** Credit expense shall create a linked `Payable` obligation without immediate cash/bank debit.
- **FAC-007:** Fuel & Lubricants module shall record quantity, unit price, fuel type, supplier, and meter reading.
- **FAC-008:** Server shall compute `total_amount = quantity * unit_price` for fuel entries and disallow client overrides.
- **FAC-009:** Fuel entry creation shall atomically create exactly one linked `Expense` record and one `account_transactions` debit.
- **FAC-010:** System shall register agricultural machines with machine type, code, meter unit, and operational status.
- **FAC-011:** System shall calculate total machine operating cost as the sum of fuel, maintenance, parts, and allocated wages.
- **FAC-012:** System shall compute machine cost per operating hour and cost per kilometer based on meter logs.
- **FAC-013:** System shall manage employee master records without requiring sensitive government ID numbers in V1.
- **FAC-014:** `SALARY_ACCRUAL` shall increase employee accrued balance without debiting business cash/bank accounts.
- **FAC-015:** `ADVANCE_PAYOUT` shall debit selected business account and reduce employee outstanding balance.
- **FAC-016:** `SALARY_SETTLEMENT` shall clear net wage balance and record account debit.
- **FAC-017:** System shall compute employee outstanding balance as `Total Accrued - Advances - Settlements`.
- **FAC-018:** System shall maintain business accounts (Cash, Bank, UPI) with `opening_balance` and `opening_balance_date`.
- **FAC-019:** Account opening balance shall be initialized as an `OPENING_BALANCE` entry in `account_transactions`.
- **FAC-020:** Central `account_transactions` table shall serve as the authoritative ledger for all account balances.
- **FAC-021:** `accounts.current_balance` shall be maintained as a cached derived value reconciling with `account_transactions`.
- **FAC-022:** Inter-account transfers shall execute atomically, debiting source and crediting destination without affecting P&L.
- **FAC-023:** System shall mask account numbers in general UI views (e.g. `XXXX XXXX 4091`).
- **FAC-024:** Customer receivables shall record billed customer dues with invoice number and due date.
- **FAC-025:** Customer payments (`customer_payments`) shall credit account and decrease receivable without duplicate revenue.
- **FAC-026:** System shall reject customer payments that exceed the remaining receivable balance.
- **FAC-027:** Supplier payables shall record vendor obligations and due dates.
- **FAC-028:** Supplier payments (`supplier_payments`) shall debit account and decrease payable without creating duplicate expense.
- **FAC-029:** System shall reject supplier payments that exceed the remaining payable balance.
- **FAC-030:** Daily closing shall support scopes `CASH_ACCOUNT`, `BANK_ACCOUNT`, `UPI_ACCOUNT`, and `CONSOLIDATED`.
- **FAC-031:** Daily closing shall compute `Expected Closing = Opening + Inflows - Outflows +/- Transfers` based on scope.
- **FAC-032:** Daily closing shall compute `Discrepancy = Actual - Expected` and enforce explanation notes if discrepancy != 0.
- **FAC-033:** Finalized daily closing records shall be locked against unauthorized editing.
- **FAC-034:** Correction of posted financial records shall require a `REVERSAL` transaction preserving audit history.
- **FAC-035:** Monthly budgets shall track category spending and display visual alerts at 80% and 100% thresholds.
- **FAC-036:** Reporting engine shall export statements in PDF, Excel (`.xlsx`), CSV, and printable HTML formats.
- **FAC-037:** Audit logging system shall record user, timestamp, IP, action, entity, and JSON diff for all financial mutations.
