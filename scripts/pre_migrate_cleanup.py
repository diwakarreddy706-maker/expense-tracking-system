"""
Pre-migration cleanup script for resilient cloud deployments.
Detects if a previous migration run aborted midway in DDL execution
leaving orphaned columns/tables before Django recorded the migration as applied.
"""
import os
import sys
from pathlib import Path

# Ensure project root (/app or local root) is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_tracking_core.settings.production')
django.setup()

from django.db import connection


def run_cleanup():
    print("Checking database migration state for interrupted DDL...")
    if connection.vendor != 'mysql':
        print(f"Vendor is {connection.vendor}, skipping MySQL DDL cleanup.")
        return

    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES LIKE 'django_migrations'")
        if not cursor.fetchone():
            print("Fresh database, no cleanup needed.")
            return

        # Check if employees 0003 is already recorded as applied
        cursor.execute(
            "SELECT id FROM django_migrations WHERE app = 'employees' AND name = '0003_employeepayment_units_logged_and_more'"
        )
        if not cursor.fetchone():
            print("employees.0003 not recorded as applied. Cleaning up any partially created artifacts...")
            try:
                cursor.execute("ALTER TABLE `employee_payments` DROP FOREIGN KEY `employee_payments_compensation_id_3d0b2103_fk_employee_`")
                print("Cleaned up orphaned foreign key.")
            except Exception:
                pass

            try:
                cursor.execute("SHOW COLUMNS FROM `employee_payments` LIKE 'compensation_id'")
                if cursor.fetchone():
                    cursor.execute("ALTER TABLE `employee_payments` DROP COLUMN `compensation_id`")
                    print("Cleaned up orphaned compensation_id column.")
            except Exception:
                pass

            try:
                cursor.execute("SHOW COLUMNS FROM `employee_payments` LIKE 'units_logged'")
                if cursor.fetchone():
                    cursor.execute("ALTER TABLE `employee_payments` DROP COLUMN `units_logged`")
                    print("Cleaned up orphaned units_logged column.")
            except Exception:
                pass

            try:
                cursor.execute("DROP TABLE IF EXISTS `employee_compensations`")
                print("Cleaned up orphaned employee_compensations table.")
            except Exception:
                pass

        # Check machines 0003 in case it was partially applied
        cursor.execute(
            "SELECT id FROM django_migrations WHERE app = 'machines' AND name = '0003_machinebooking_machineworkentry_booking'"
        )
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE `machine_work_entries` DROP FOREIGN KEY `machine_work_entries_booking_id_8d24ebf4_fk_machine_b`")
            except Exception:
                pass
            try:
                cursor.execute("SHOW COLUMNS FROM `machine_work_entries` LIKE 'booking_id'")
                if cursor.fetchone():
                    cursor.execute("ALTER TABLE `machine_work_entries` DROP COLUMN `booking_id`")
                    print("Cleaned up orphaned booking_id column.")
            except Exception:
                pass
            try:
                cursor.execute("DROP TABLE IF EXISTS `machine_bookings`")
                print("Cleaned up orphaned machine_bookings table.")
            except Exception:
                pass

    print("Pre-migration check completed cleanly.")


if __name__ == '__main__':
    try:
        run_cleanup()
    except Exception as e:
        print(f"Pre-migration cleanup warning: {e}")
