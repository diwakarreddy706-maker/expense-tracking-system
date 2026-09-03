# Sri Basaveshwara & Co — AgriBOS ERP

A robust, enterprise-grade financial management, harvesting operations, and equipment fleet ERP platform built with Python, Django 5.x, MySQL 8.x, Tailwind CSS, Alpine.js, HTMX, and Bootstrap 5.3.

---

## 🌾 Overview
**AgriBOS ERP** provides end-to-end operational cost tracking and accounting for agricultural businesses, combine harvester fleet hiring hubs, and rural machinery transport services.

### Core Modules
- **⚡ General & Quick Expenses:** Real-time expense logging with field-ready mobile quick entry (< 20s).
- **⛽ Fuel & Lubricants:** Track diesel, petrol, engine oil, and hydraulic oil with 1-to-1 atomic ledger debit.
- **🚜 Combine Harvesters & Machinery:** Equipment registry, operating hours/acres billing, maintenance schedules, and rental owner commissions.
- **📖 Farmer Credit Ledger (Udhar Katha):** Real-time farmer credit balances, statement generation, WhatsApp sharing, and multi-mode payment collection.
- **👥 Employee Wages & Advances:** Comprehensive driver & crew wage accruals, advance tracking, and payout settlements.
- **💼 Central Financial Ledger:** Authoritative multi-account balance reconciliation with double-entry safety.
- **🔒 Scoped Daily Financial Closing:** Cash, bank, and consolidated end-of-day closing snapshots with lock enforcement.
- **📊 Business Setup & Master Data Hub:** CSV batch import and opening balance reconciliation.
- **📱 PWA & Field-First Mobile Web:** Home screen shortcuts, native camera receipt capture, and Global Command Palette (`Ctrl+K`).

---

## 📚 Project Documentation

All system architecture, product specifications, and operational manuals are organized in [`docs/`](file:///c:/Users/diwak/Desktop/ETS/docs):

| Document | Description |
| :--- | :--- |
| [PRD.md](file:///c:/Users/diwak/Desktop/ETS/docs/PRD.md) | Product Requirements & Business Domain Specifications |
| [ARCHITECTURE.md](file:///c:/Users/diwak/Desktop/ETS/docs/ARCHITECTURE.md) | System Architecture, Data Flow & Security Models |
| [DATABASE_SCHEMA.md](file:///c:/Users/diwak/Desktop/ETS/docs/DATABASE_SCHEMA.md) | MySQL Database Schema, Foreign Keys & Table Definitions |
| [API_ROUTES.md](file:///c:/Users/diwak/Desktop/ETS/docs/API_ROUTES.md) | Complete Web Routes & Internal API Specifications |
| [DEPLOYMENT.md](file:///c:/Users/diwak/Desktop/ETS/docs/DEPLOYMENT.md) | Production Deployment Guide (Docker, Cloud, VPS, Systemd) |
| [ONBOARDING_GUIDE.md](file:///c:/Users/diwak/Desktop/ETS/docs/ONBOARDING_GUIDE.md) | First-Time Business Setup & CSV Master Data Onboarding |
| [PRODUCTION_GO_LIVE_CHECKLIST.md](file:///c:/Users/diwak/Desktop/ETS/docs/PRODUCTION_GO_LIVE_CHECKLIST.md) | Production Hardening & Pre-Flight Verification Checklist |
| [TASK_CHECKLIST.md](file:///c:/Users/diwak/Desktop/ETS/docs/TASK_CHECKLIST.md) | Implementation Roadmap & Milestone Completion History |
| [UI_UX_SPEC.md](file:///c:/Users/diwak/Desktop/ETS/docs/UI_UX_SPEC.md) | Design System, Mobile Viewport Specs & Dark Theme Colors |

---

## 🛠️ Technology Stack
- **Backend:** Python 3.11+ / Django 5.x
- **Database:** MySQL 8.0+ / Cloud MySQL / PostgreSQL / SQLite (Fallback)
- **Frontend:** Django Templates, Tailwind CSS, Alpine.js, HTMX, Bootstrap 5.3
- **Reporting:** ReportLab (PDF), openpyxl (Excel), Python CSV
- **Static Assets & WSGI:** WhiteNoise & Gunicorn

---

## 🚀 Getting Started

### 1. Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate   # Windows PowerShell / CMD
# source venv/bin/activate  # Linux / macOS

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
Copy `.env.example` to `.env` and set your database connection details:
```bash
cp .env.example .env
```

### 3. Run Migrations & System Checks
```bash
python manage.py migrate
python manage.py check
python manage.py test
```

### 4. Start Development Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` to access the dashboard and `http://127.0.0.1:8000/health/` for the health check.
