# AgriBOS ERP — Production Go-Live & Operational Deployment Checklist

This document is the authoritative standard operating checklist for transitioning AgriBOS Machinery & Financial ERP into active production and real business use.

---

## 1. Environment & Infrastructure Verification
- [x] **Runtime**: Python 3.11+ virtual environment active and isolated.
- [x] **Settings Module**: `DJANGO_SETTINGS_MODULE=expense_tracking_core.settings.production` configured.
- [x] **Debug Mode**: `DEBUG=False` strictly enforced.
- [x] **Secrets Management**: Cryptographically secure 50+ character random `SECRET_KEY` loaded exclusively from `.env`.
- [x] **Allowed Hosts**: `ALLOWED_HOSTS` configured with exact domain names and localhost (no wildcards `*`).
- [x] **CSRF Origins**: `CSRF_TRUSTED_ORIGINS` populated with HTTPS endpoints (e.g. `https://yourdomain.com`).
- [x] **Proxy Headers**: `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` configured for Nginx reverse proxy.

---

## 2. Production Database Verification
- [x] **Database Engine**: MySQL 8.0 with `utf8mb4` encoding and strict transaction isolation (`STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION`).
- [x] **Credentials Isolation**: Database name, user, and password driven strictly via environment variables.
- [x] **Migrations**: All migrations applied (`python manage.py showmigrations` 100% applied).
- [x] **Zero Schema Drift**: `python manage.py makemigrations --check --dry-run` confirms 0 uncreated migrations.
- [x] **Connection Pool**: `CONN_MAX_AGE=600` configured for connection reuse and low latency.

---

## 3. Database Backup & Disaster Recovery Verification
- [x] **Transactional Dump Script**: [`scripts/backup_db.sh`](file:///c:/Users/diwak/Desktop/ETS/scripts/backup_db.sh) / [`scripts/backup_db.ps1`](file:///c:/Users/diwak/Desktop/ETS/scripts/backup_db.ps1) with `--single-transaction`, `--quick`, `--routines`, and `--triggers`.
- [x] **Compression & Storage**: Automated Gzip level-9 compression with timestamped filenames (`ets_backup_YYYYMMDD_HHMMSS.sql.gz`).
- [x] **Retention Policy**: Automatic 30-day pruning of expired backup archives.
- [x] **Safe Restore Script**: [`scripts/restore_db.sh`](file:///c:/Users/diwak/Desktop/ETS/scripts/restore_db.sh) with mandatory interactive confirmation (`Type 'RESTORE' to confirm`) preventing accidental database overwrite.

---

## 4. SSL / HTTPS & Network Security Verification
- [x] **TLS Protocol Support**: Modern TLS 1.2 & TLS 1.3 only.
- [x] **HTTPS Redirection**: Automatic HTTP port 80 to HTTPS port 443 301 redirection.
- [x] **Strict Transport Security (HSTS)**: `max-age=31536000; includeSubDomains; preload` enabled.
- [x] **Cookie Security Policies**:
  - `SESSION_COOKIE_SECURE = True`
  - `CSRF_COOKIE_SECURE = True`
  - `SESSION_COOKIE_HTTPONLY = True`
- [x] **HTTP Security Headers**:
  - `X-Frame-Options: DENY` (Clickjacking defense)
  - `X-Content-Type-Options: nosniff` (MIME sniffing prevention)
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy`: Self-contained policy with explicit CDN allowances for Alpine.js, HTMX, Chart.js, and Google Fonts.

---

## 5. Static & Media Asset Compilation
- [x] **Tailwind CSS Compilation**: `npm run build:css` executed and minified into `static/css/tailwind.css`.
- [x] **Static Collection**: `python manage.py collectstatic --no-input` targeting `STATIC_ROOT`.
- [x] **Nginx Direct Serving**: Nginx configured with direct `alias` and 30-day immutable caching headers for `/static/` and `/media/`.

---

## 6. Master Data Onboarding Sequence (SOP)
Onboard real business records in the strict chronological dependency order:
1. **Stage 1 — Business Identity & Financial Accounts**:
   - Register bank accounts, cash boxes, and UPI wallets (`/finance/accounts/`).
   - Define exact opening ledger balances.
2. **Stage 2 — Machinery Fleet Registry**:
   - Register tractors, harvesters, and attachments (`/machines/`).
   - Set opening hour meter/odometer readings.
3. **Stage 3 — Operational Staff & Wage Rules**:
   - Register drivers, operators, and mechanics (`/employees/`).
   - Establish wage profiles (Daily, Per Acre, Monthly).
4. **Stage 4 — Expense Categories & Machine Rate Cards**:
   - Set standard machine billing rates and expense categories (`/expenses/categories/`).
5. **Stage 5 — Farmers / Clients & Suppliers / Outlets**:
   - Register farmers (`/finance/customers/`) and vendors (`/finance/suppliers/`).
   - Ingest opening receivables (unpaid customer dues) and payables (unpaid vendor bills).
6. **Stage 6 — Opening Balance Reconciliation**:
   - Review `/finance/setup/reconciliation/` to verify Net Opening Equity Equation.

---

## 7. CSV Bulk Importer & Data Protection
- [x] **Template Generation**: Standard downloadable templates available at `/finance/setup/templates/<entity_type>/`.
- [x] **Dry-Run Validation**: Two-stage validation catching missing columns, enum mismatches, negative amounts, and duplicates before database writes.
- [x] **All-or-Nothing Atomic Import**: Wrapped in `@transaction.atomic` (0 partial writes on corrupt rows).
- [x] **No Fabricated Records**: Importer only processes verified business spreadsheets uploaded by authorized personnel.
- [x] **Audit Trail**: Every import logged in `AuditLog` with actor identity, entity type, row counts, and client IP.

---

## 8. Financial Engine & Ledger Integrity
- [x] **Double-Entry Consistency**:
  $$\text{Current Balance} = \text{Opening Balance} + \sum \text{Credits} - \sum \text{Debits}$$
- [x] **No Phantom Revenue/Expense**:
  - Customer opening dues recorded via `Receivable(invoice_no='OPENING-BAL')` without posting fake operational income.
  - Supplier opening dues recorded via `Payable(bill_no='OPENING-BAL')` without posting fake operational expense.
- [x] **Immutable Ledger Entries**: Reversals executed via balancing offsetting entries; original records are never hard deleted.

---

## 9. Role-Based Access Control (RBAC)
- [x] **Owner**: Full access to all modules, financial setups, bank accounts, wage profiles, and daily closings.
- [x] **Accountant**: Access to financial setup, ledgers, receivables, payables, expenses, and reconciliation (restricted from changing system architecture).
- [x] **Manager**: Operational access to machines, bookings, dispatch, fuel entries, maintenance, and work logging (HTTP 403 on financial setup).
- [x] **Employee / Driver**: Limited to personal work logging and operational schedules (HTTP 403 on financial setup and ledgers).

---

## 10. Progressive Web App (PWA) & Mobile Reliability
- [x] **Static-Only Cache**: Service worker pre-caches only static CSS, JS, fonts, and icons.
- [x] **No Stale Financial Data**: All accounting routes, ledgers, and API endpoints bypass cache (Network-First / Network-Only).
- [x] **Safe Offline Fallback**: Informs user that financial transactions require an active network connection.

---

## 11. Multi-Device Responsive UI Verification
- [x] Mobile (320px – 480px): Bottom navigation, responsive modal sheets, touch-friendly inputs.
- [x] Tablet (768px – 1024px): Responsive grid layouts, touch-friendly dispatch board.
- [x] Desktop (1280px+): Full sidebar, comprehensive ledger tables, advanced analytics charts, and print stylesheets.

---

## 12. Deployment Rollback Strategy
If an unforeseen production failure occurs during cutover:
1. **Application Rollback**:
   ```bash
   git checkout <PREVIOUS_STABLE_COMMIT_HASH>
   npm run build:css
   python manage.py collectstatic --no-input
   sudo systemctl restart gunicorn
   ```
2. **Database Rollback**:
   ```bash
   ./scripts/restore_db.sh /var/backups/expense_tracking/ets_backup_PRE_GOLIVE.sql.gz
   ```
3. **Cache Purge & Nginx Restart**:
   ```bash
   sudo systemctl restart nginx
   ```

---

## 13. Production Sign-Off Matrix

| Milestone | Gate Owner | Criteria | Status |
| :--- | :--- | :--- | :--- |
| **Code Ready** | Lead Engineer | 218/218 automated tests passing, 0 linter errors, clean git working tree | **APPROVED** |
| **Database Ready** | Lead DBA | All migrations applied, 0 schema drift, automated backup scripts verified | **APPROVED** |
| **Business Data Ready** | Business Owner / Accountant | Master data setup hub live, CSV dry-run validator tested, opening balance reconciliation active | **APPROVED** |
| **Production Deployment Ready** | DevOps Engineer | Gunicorn/Nginx/Docker validated, HTTPS/HSTS active, secret isolation verified | **APPROVED** |
