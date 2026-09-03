# EXPENSE TRACKING & MANAGEMENT SYSTEM
## Web Routes & RESTful API Specification

---

## 1. Routing Overview & Standards
The system employs a hybrid routing architecture:
- **Server-Side Rendered (SSR) Views:** Django Class-Based Views (CBVs) returning rendered HTML templates for full-page navigation.
- **RESTful JSON API Endpoints:** Clean endpoints returning structured JSON for Chart.js analytics, asynchronous modals, form submissions, and data-grid filtering.
- **CSRF & Authentication:** All mutations require standard Django `X-CSRFToken` verification and session cookies.

---

## 2. Standard API Response Structure

### Success Response Format
```json
{
  "success": true,
  "message": "Operation completed successfully.",
  "data": {
    "id": 42,
    "code": "EXP-20260815-0042",
    "amount": "12500.00",
    "created_at": "2026-08-15T14:30:00Z"
  }
}
```

### Error Response Format
```json
{
  "success": false,
  "error_code": "INSUFFICIENT_FUNDS",
  "message": "Account 'Main Cash Box' does not have sufficient balance for this debit.",
  "field_errors": {
    "amount": ["Amount exceeds available account balance of ₹4,250.00."]
  }
}
```

---

## 3. Comprehensive Route & API Catalog

### A. Authentication & User Management
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/login/` | GET, POST | Public | Anonymous | SSR | User login view |
| `/logout/` | POST | Yes | Authenticated | Action | Terminate session with CSRF verification |
| `/profile/` | GET, POST | Yes | Authenticated | SSR | User profile view & password update |
| `/settings/users/` | GET, POST | Yes | `OWNER` | SSR | User administration & role assignment |

---

### B. Executive Dashboard & Real-Time Analytics
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/` or `/dashboard/` | GET | Yes | All Roles | SSR | Executive dashboard landing |
| `/api/dashboard/summary/` | GET | Yes | All Roles | JSON API | Summary KPI cards and today's financial metrics |
| `/api/dashboard/charts/` | GET | Yes | All Roles | JSON API | 12-month expense trends & category doughnut data |

#### API Spec: `GET /api/dashboard/summary/`
- **Response Payload:**
```json
{
  "success": true,
  "data": {
    "total_available_balance": "145250.00",
    "today_financial_summary": {
      "opening_balance": "125430.00",
      "today_inflow": "25000.00",
      "today_expense": "4870.00",
      "today_transfers": "0.00",
      "expected_closing": "145560.00",
      "closing_status": "PENDING"
    },
    "monthly_expense": "75600.00",
    "yearly_expense": "428750.00",
    "operational_breakdown": {
      "fuel_lubricants": "32400.00",
      "machine_maintenance": "18200.00",
      "employee_wages": "19500.00",
      "general_overhead": "5500.00"
    },
    "to_receive": "84000.00",
    "to_pay": "31500.00"
  }
}
```

---

### C. General & Quick Expense Management
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/expenses/` | GET | Yes | All Roles | SSR | Filterable expense datagrid |
| `/expenses/add/` | GET, POST | Yes | `OWNER`, `ACCOUNTANT`, `MANAGER` | SSR / Form | Create detailed general expense |
| `/expenses/<int:id>/` | GET | Yes | All Roles | SSR | Expense details & receipt lightbox |
| `/expenses/<int:id>/edit/` | GET, POST | Yes | `OWNER`, `ACCOUNTANT` | SSR / Form | Edit existing expense |
| `/expenses/<int:id>/delete/`| POST | Yes | `OWNER` | Action | Soft-delete expense record |
| `/api/expenses/` | POST | Yes | `OWNER`, `ACCOUNTANT`, `MANAGER` | JSON API | Asynchronous expense creation |
| `/api/expenses/quick/` | POST | Yes | `OWNER`, `ACCOUNTANT`, `MANAGER` | JSON API | Mobile Quick Expense (under 20s) |
| `/api/expenses/<int:id>/reverse/` | POST | Yes | `OWNER`, `ACCOUNTANT` | JSON API | Auditable transaction reversal |

#### API Spec: `POST /api/expenses/quick/`
- **Request Body:**
```json
{
  "amount": "1200.00",
  "category_id": 3,
  "account_id": 1,
  "payment_method": "CASH",
  "machine_id": 2,
  "employee_id": null,
  "description": "Emergency fan belt replacement in field"
}
```
- **Execution & Balance Effects:** Executed inside atomic transaction (`@transaction.atomic`). Debits `account_id` in `account_transactions` with `direction='DEBIT'`, `transaction_type='EXPENSE'`. Generates `audit_logs` record.

---

### D. Dedicated Fuel & Lubricants Module
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/fuel/` | GET | Yes | All Roles | SSR | Fuel & lubricant logbook |
| `/fuel/add/` | GET, POST | Yes | `OWNER`, `ACCOUNTANT`, `MANAGER` | SSR / Form | Record fuel intake entry |
| `/fuel/<int:id>/` | GET | Yes | All Roles | SSR | Refueling entry details & receipt |
| `/api/fuel/` | POST | Yes | `OWNER`, `ACCOUNTANT`, `MANAGER` | JSON API | Asynchronous fuel logging |
| `/api/fuel/summary/` | GET | Yes | All Roles | JSON API | Aggregated fuel volume, avg price, machine sums |

#### API Spec: `POST /api/fuel/`
- **Request Body:**
```json
{
  "entry_date": "2026-08-15",
  "machine_id": 1,
  "fuel_type": "DIESEL",
  "quantity": "50.00",
  "unit_price": "88.50",
  "supplier_id": 2,
  "account_id": 1,
  "operator_id": 3,
  "meter_reading": "1450.00",
  "notes": "Refueled before harvesting block B"
}
```
- **Server Execution:** Computes `total_amount = 50.00 * 88.50` = `₹4,425.00`. In a single atomic transaction:
  1. Inserts into `fuel_entries`.
  2. Inserts 1-to-1 linked record into `expenses` (`category='CAT-FUEL'`).
  3. Inserts ledger debit into `account_transactions`.
  4. Generates audit record.

---

### E. Machine Registry & Operating Cost (TCO)
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/machines/` | GET | Yes | All Roles | SSR | Machine registry & operational status |
| `/machines/add/` | GET, POST | Yes | `OWNER`, `ACCOUNTANT` | SSR / Form | Register new agricultural machine |
| `/machines/<int:id>/` | GET | Yes | All Roles | SSR | Machine 360 profile (Operating cost breakdown) |
| `/machines/<int:id>/edit/` | GET, POST | Yes | `OWNER`, `ACCOUNTANT` | SSR / Form | Update machine details / status |
| `/api/machines/<int:id>/costs/`| GET | Yes | All Roles | JSON API | Operating cost breakdown (Fuel vs Parts vs Labor) |

---

### F. Employee Management, Wages & Advances
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/employees/` | GET | Yes | `OWNER`, `ACCOUNTANT`, `MANAGER` | SSR | Staff roster with balance ledger |
| `/employees/add/` | GET, POST | Yes | `OWNER`, `ACCOUNTANT` | SSR / Form | Register staff (non-sensitive V1 fields) |
| `/employees/<int:id>/` | GET | Yes | `OWNER`, `ACCOUNTANT`, `MANAGER` | SSR | Employee profile & passbook |
| `/api/employees/<int:id>/payout/`| POST | Yes | `OWNER`, `ACCOUNTANT` | JSON API | Disburse advance or salary settlement |

#### API Spec: `POST /api/employees/<int:id>/payout/`
- **Request Body:**
```json
{
  "payment_date": "2026-08-15",
  "payment_type": "ADVANCE_PAYOUT",
  "amount": "3000.00",
  "account_id": 1,
  "notes": "Mid-month festival advance"
}
```
- **Execution:** Inserts into `employee_payments`. If type is `ADVANCE_PAYOUT` or `SALARY_SETTLEMENT`, debits `account_id` in `account_transactions` and creates linked `Expense` entry. Reduces employee outstanding balance.

---

### G. Central Ledger, Accounts & Inter-Account Transfers
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/accounts/` | GET | Yes | `OWNER`, `ACCOUNTANT` | SSR | Accounts list & balance cards |
| `/accounts/add/` | GET, POST | Yes | `OWNER` | SSR / Form | Create business account with opening balance |
| `/accounts/<int:id>/statement/` | GET | Yes | `OWNER`, `ACCOUNTANT` | SSR | Account passbook statement |
| `/api/accounts/<int:id>/ledger/`| GET | Yes | `OWNER`, `ACCOUNTANT` | JSON API | Query `account_transactions` records |
| `/api/accounts/transfer/` | POST | Yes | `OWNER`, `ACCOUNTANT` | JSON API | Execute atomic inter-account transfer (Rule 2) |

#### API Spec: `POST /api/accounts/transfer/`
- **Request Body:**
```json
{
  "transfer_date": "2026-08-15",
  "from_account_id": 2,
  "to_account_id": 1,
  "amount": "25000.00",
  "reference_no": "ATM-WDL-9941",
  "notes": "Bank withdrawal for field cash box"
}
```
- **Execution & Balance Effects:** Inside atomic transaction:
  1. Creates `account_transfers` record.
  2. Creates `TRANSFER_OUT` debit in `account_transactions` for Source Account.
  3. Creates `TRANSFER_IN` credit in `account_transactions` for Destination Account.
  4. **Strictly excluded from P&L revenue/expense totals.**

---

### H. Customers, Receivables & Payment History
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/customers/` | GET, POST | Yes | `OWNER`, `ACCOUNTANT` | SSR | Customer master management |
| `/receivables/` | GET | Yes | `OWNER`, `ACCOUNTANT` | SSR | Customer receivable bills & aging |
| `/api/receivables/` | POST | Yes | `OWNER`, `ACCOUNTANT` | JSON API | Log new customer receivable bill |
| `/api/receivables/<int:id>/payments/`| POST | Yes | `OWNER`, `ACCOUNTANT` | JSON API | Record customer payment (No duplicate revenue) |

#### API Spec: `POST /api/receivables/<int:id>/payments/`
- **Request Body:**
```json
{
  "payment_date": "2026-08-15",
  "amount": "15000.00",
  "account_id": 2,
  "payment_method": "UPI",
  "reference_no": "UPI-TXN-884102",
  "notes": "Partial settlement for harvest contract"
}
```
- **Execution:** Validates `amount <= remaining_balance`. Inserts into `customer_payments`. Updates `receivables.received_amount`. Creates `RECEIVABLE_PAYMENT` credit in `account_transactions` for Account 2. **Does NOT create duplicate income.**

---

### I. Suppliers, Payables & Payment History
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/suppliers/` | GET, POST | Yes | `OWNER`, `ACCOUNTANT` | SSR | Supplier master management |
| `/payables/` | GET | Yes | `OWNER`, `ACCOUNTANT` | SSR | Supplier bills & vendor balance |
| `/api/payables/` | POST | Yes | `OWNER`, `ACCOUNTANT` | JSON API | Log new vendor payable bill |
| `/api/payables/<int:id>/payments/` | POST | Yes | `OWNER`, `ACCOUNTANT` | JSON API | Record supplier payment (No duplicate expense) |

#### API Spec: `POST /api/payables/<int:id>/payments/`
- **Request Body:**
```json
{
  "payment_date": "2026-08-15",
  "amount": "12000.00",
  "account_id": 2,
  "payment_method": "BANK_TRANSFER",
  "reference_no": "NEFT-550291",
  "notes": "Payment for spare parts invoice"
}
```
- **Execution:** Validates `amount <= remaining_balance`. Inserts into `supplier_payments`. Updates `payables.paid_amount`. Creates `PAYABLE_PAYMENT` debit in `account_transactions` for Account 2. **Does NOT create duplicate expense.**

---

### J. Scoped Daily Financial Closing
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/daily-closing/` | GET | Yes | `OWNER`, `ACCOUNTANT`, `MANAGER` | SSR | Daily closing reconciliation screen |
| `/daily-closing/history/` | GET | Yes | `OWNER`, `ACCOUNTANT` | SSR | Historical daily closing log |
| `/api/daily-closing/calculate/`| GET | Yes | `OWNER`, `ACCOUNTANT`, `MANAGER` | JSON API | Calculate expected balance by scope |
| `/api/daily-closing/submit/` | POST | Yes | `OWNER`, `ACCOUNTANT`, `MANAGER` | JSON API | Commit and freeze daily closing |

#### API Spec: `POST /api/daily-closing/submit/`
- **Request Body:**
```json
{
  "closing_date": "2026-08-15",
  "scope": "CASH_ACCOUNT",
  "account_id": 1,
  "actual_closing": "135600.00",
  "notes": "Physical cash count in main shop register"
}
```
- **Server Execution:** Computes expected balance via `closing_service.py`. Computes `discrepancy = actual_closing - expected_closing`. Enforces mandatory notes if discrepancy != 0. Freezes closing record (`is_locked=True`). Logs audit event.

---

### K. Financial Reports & Export Engines
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/reports/` | GET | Yes | `OWNER`, `ACCOUNTANT` | SSR | Report generation portal |
| `/reports/export/csv/` | GET | Yes | `OWNER`, `ACCOUNTANT` | Download | Streaming CSV export |
| `/reports/export/excel/`| GET | Yes | `OWNER`, `ACCOUNTANT` | Download | Styled Excel (`.xlsx`) report |
| `/reports/export/pdf/` | GET | Yes | `OWNER`, `ACCOUNTANT` | Download | Formatted PDF statement |

---

### L. Audit Logs & Compliance Trail
| Route URL | Method | Auth | Role / Permission | View Type | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/audit-logs/` | GET | Yes | `OWNER` Only | SSR | Searchable audit trail |
| `/api/audit-logs/` | GET | Yes | `OWNER` Only | JSON API | Filtered audit log query |
