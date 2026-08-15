# Expense Tracking & Management System

A robust, enterprise-grade financial management and operational cost tracking platform built with Python, Django 5.x, MySQL 8.x, Bootstrap 5.3, and Chart.js.

## Overview
**Expense Tracking & Management System** provides end-to-end operational cost tracking for agricultural businesses, heavy equipment hiring hubs, and rural transport services.

### Core Modules
- **General & Quick Expenses:** Real-time expense logging with field-ready mobile quick entry (< 20s).
- **Fuel & Lubricants:** Track diesel, petrol, engine oil, and hydraulic oil with 1-to-1 atomic ledger integration.
- **Agricultural Machinery (TCO):** Equipment registry and operating cost per hour / per kilometer.
- **Employee Wages & Advances:** Comprehensive workforce wage accruals and advance passbooks.
- **Central Financial Ledger:** Authoritative multi-account balance reconciliation (`account_transactions`).
- **Scoped Daily Financial Closing:** Cash, bank, and consolidated end-of-day closing snapshots.
- **Customer Receivables & Supplier Payables:** Inflow/outflow tracking with complete payment histories.
- **Budgeting & Visual Analytics:** Monthly category thresholds with 80%/100% warning alerts and Chart.js dashboards.
- **Compliance Reports & Audit:** Multi-format exports (PDF, Excel, CSV, Print) with immutable change logs.

## Technology Stack
- **Backend:** Python 3.11+ / Django 5.x
- **Database:** MySQL 8.0+ (InnoDB, UTF8MB4, Strict SQL Mode)
- **Frontend:** Django Templates, HTML5, CSS3, Bootstrap 5.3, Vanilla JavaScript
- **Visualizations:** Chart.js 4.x
- **Reporting:** openpyxl (Excel), ReportLab (PDF), Python CSV

## Getting Started

### 1. Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `.env` and configure your database credentials:
```bash
cp .env.example .env
```

### 3. Run System Checks & Tests
```bash
python manage.py check
python manage.py test tests
```

### 4. Start Development Server
```bash
python manage.py runserver
```
Navigate to `http://127.0.0.1:8000/` to access the dashboard and `http://127.0.0.1:8000/health/` for health check.
