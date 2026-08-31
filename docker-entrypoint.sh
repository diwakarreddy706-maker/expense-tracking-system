#!/bin/sh
set -e

echo "============================================================"
echo " Starting AgriBOS ERP Container on Render Cloud"
echo "============================================================"

echo "==> 1. Running Pre-Migrate State Verification..."
python scripts/pre_migrate_cleanup.py || echo "Pre-migrate warning ignored"

echo "==> 2. Running Database Migrations..."
python manage.py migrate --noinput || echo "Migrate warning ignored"

echo "==> 3. Collecting Static Assets..."
python manage.py collectstatic --noinput || echo "Collectstatic warning ignored"

echo "==> 4. Initializing Default Master Records & Admin..."
python scripts/init_admin.py || echo "Init-admin warning ignored"

echo "============================================================"
echo " Launching Gunicorn WSGI Server on port ${PORT:-8000}..."
echo "============================================================"
exec gunicorn --config deploy/gunicorn/gunicorn.conf.py expense_tracking_core.wsgi:application
