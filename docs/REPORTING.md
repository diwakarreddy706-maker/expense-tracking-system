# Enterprise PDF Export & Financial Reporting (Phase 23)

## 1. Overview
The **Enterprise PDF Export & Financial Reporting** module provides authoritative, read-only, high-fidelity A4 PDF export capabilities for Sri Basaveshwara Harvesting & Co. Built on ReportLab Platypus, it translates complex operational field work, fuel expenses, and central accounting ledgers into publication-grade documents suitable for farmer handovers, office credit audits, and formal financial reconciliation.

---

## 2. Core Architecture

### 2.1 PDF Platypus Engine (`apps/reports/services/pdf_service.py`)
- **A4 Portrait & Landscape Formatting**:
  - Portrait: Usable width = `523.27pt` (Margins: `36pt` / 0.5 in).
  - Landscape: Usable width = `769.0pt` (Margins: `36pt` / 0.5 in).
- **Two-Pass `NumberedCanvas`**:
  - Dynamically calculates total pages across page breaks and writes running header (`SRI BASAVESHWARA & CO. | FINANCIAL AUDIT`) and footer (`Page X of Y • Generated on DD-MM-YYYY • STRICTLY CONFIDENTIAL`).
- **Design Tokens & Typography**:
  - Forest Emerald (`#065F46`), Primary Dark (`#1E293B`), Crimson Rose (`#BE123C`), Warm Amber (`#D97706`), Neutral Gray (`#F8FAFC`).
  - Strict wrapping inside Paragraph flowables to prevent table text truncation.
- **Indian Rupee Formatting (`format_inr`)**:
  - Authoritative Indian numbering grouping (e.g., `₹12,45,670.00`).
- **Corporate Letterhead & Signature Blocks**:
  - Dynamic company metadata, customizable signatory lines (e.g., *Farmer Signature*, *Chief Accountant*, *Managing Partner*).

---

## 3. Reports & Statements Catalog

| Report Name | Document Type | Page Size | Service Class | Primary Endpoint |
|---|---|---|---|---|
| **Farmer Account Statement / Passbook** | Full Ledger History | A4 Portrait | `FarmerStatementPDFService` | `/machines/farmers/ledger/<id>/export-pdf/` |
| **Payment / Advance Receipt** | Payment Voucher | A4 Portrait | `PaymentReceiptPDFService` | `/finance/customer-payments/<id>/receipt-pdf/` |
| **Work Entry / Commercial Invoice** | Field Work Bill | A4 Portrait | `WorkInvoicePDFService` | `/machines/work/<id>/pdf/` |
| **Machinery Operational P&L** | Fleet P&L Audit | A4 Landscape | `MachineryPnLPDFService` | `/reports/machinery-pnl/pdf/` |
| **Comprehensive Expense Analysis** | Expense Breakdown | A4 Portrait | `ExpenseReportPDFService` | `/reports/expenses/pdf/` |
| **Farmer Receivables & Aging Report** | Aging & Udhar Audit | A4 Landscape | `ReceivablesAgingPDFService` | `/reports/receivables-aging/pdf/` |

---

## 4. Authoritative Financial & Accounting Rules

1. **Read-Only Invariance**:
   - PDF generation is strictly non-mutating. Generating or downloading reports never alters balances, never writes ledger entries, and never modifies receivable statuses.
2. **Cost Attribution (No Double Counting)**:
   - Direct machine fuel, maintenance, and wage costs are queried once from `Expense` with matching `machine` attribution.
3. **Running Balance Logic**:
   - Starting Opening Balance $\to$ Debit Work Entries $\to$ Credit On-Site Advances $\to$ Credit Direct Office Payments $\to$ Final Outstanding Udhar Due.
4. **Receivables Aging Buckets**:
   - Outstanding balances categorized into: `0–30 Days (Current)`, `31–60 Days`, `61–90 Days`, `91–180 Days`, `181+ Days (Critical)`.

---

## 5. Security & Governance

- **Role-Based Access Control (RBAC)**:
  - Owner & Accountant: Unrestricted access to all fleet P&L, expense analytics, central ledgers, and customer statements.
  - Manager: Access to operational P&L, customer passbooks, and field work invoices.
  - Field Drivers & Operators: Restricted from accessing financial summaries, fleet P&L, and receivables aging.
- **Independent Audit Logging (`ReportAuditLog`)**:
  - Every PDF export creates a record in `report_audit_logs` capturing user ID, timestamp, report type, period filters, and generated filename without touching financial ledger tables.

---

## 6. Automated Testing Suite

All reporting services and security constraints are verified via `tests/test_pdf_reports.py`:
- HTTP 200 and `application/pdf` validation.
- Binary header validation (`%PDF-`).
- Multi-page pagination and table header repetition.
- Empty dataset handling (`NO_RECORDS` fallback).
- RBAC denial for unauthorized roles (HTTP 403).
- Read-only data invariance verification.
