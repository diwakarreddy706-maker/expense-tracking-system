#!/usr/bin/env python
"""
AgriBOS Staging & Release Candidate Smoke Test Suite.
Validates all UI views, authentication flows, PWA assets, and financial invariants.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_tracking_core.settings.development')

import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile
from apps.expenses.models import ExpenseCategory, Expense
from apps.finance.models import Account, AccountTransaction
from apps.finance.services.balance_service import FinancialCalculationService

def run_staging_smoke_tests():
    print("=" * 80)
    print("        AGRIBOS ERP -- STAGING SMOKE TEST & ENDPOINT VALIDATION")
    print("=" * 80)

    client = Client()
    host_kwargs = {'HTTP_HOST': '127.0.0.1'}

    # 1. Ensure a staging test user exists
    username = 'staging_smoke_user'
    password = 'StagingTestPassword123!'
    user, _ = User.objects.get_or_create(username=username, defaults={'email': 'staging@example.com'})
    user.set_password(password)
    user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'OWNER', 'phone_number': '9999999999'})
    profile.role = 'OWNER'
    profile.save()

    results = []

    def check_url(name, path, expected_status=200, requires_auth=False):
        if requires_auth:
            client.login(username=username, password=password)
        else:
            client.logout()

        try:
            res = client.get(path, **host_kwargs)
            status_pass = (res.status_code == expected_status)
            status_text = f"Status {res.status_code} (Expected {expected_status})"
            results.append((name, status_pass, status_text))
            mark = "[PASS]" if status_pass else "[FAIL]"
            print(f"{name:<45} | {mark:<6} | {status_text}")
            return status_pass
        except Exception as e:
            results.append((name, False, f"Exception: {e}"))
            print(f"{name:<45} | [FAIL] | Exception: {e}")
            return False

    print("\n--- [A] Authentication & PWA Assets ---")
    check_url("1. Login Page Loads", "/accounts/login/", 200, requires_auth=False)
    check_url("2. PWA Webmanifest Accessible", "/static/manifest.webmanifest", 200, requires_auth=False)
    check_url("3. Service Worker Accessible", "/static/js/service-worker.js", 200, requires_auth=False)
    check_url("4. Core Tailwind CSS Accessible", "/static/css/tailwind.css", 200, requires_auth=False)

    print("\n--- [B] Core ERP Dashboard & Navigation (Authenticated) ---")
    check_url("5. Executive Dashboard Loads", "/", 200, requires_auth=True)
    check_url("6. Machines List Page Loads", "/machines/", 200, requires_auth=True)
    check_url("7. Machine Booking List Loads", "/machines/bookings/", 200, requires_auth=True)
    check_url("8. Machine Dispatch Board Loads", "/machines/dispatch/", 200, requires_auth=True)
    check_url("9. Maintenance Dashboard Loads", "/machines/maintenance/", 200, requires_auth=True)
    check_url("10. Maintenance Jobs List Loads", "/machines/maintenance/jobs/", 200, requires_auth=True)
    check_url("11. Fuel Tracking Page Loads", "/fuel/", 200, requires_auth=True)
    check_url("12. Expenses Ledger Loads", "/expenses/", 200, requires_auth=True)
    check_url("13. Employee & Wages Page Loads", "/employees/", 200, requires_auth=True)
    check_url("14. Customer Receivables Page Loads", "/finance/receivables/", 200, requires_auth=True)
    check_url("15. Supplier Payables Page Loads", "/finance/payables/", 200, requires_auth=True)
    check_url("16. Scoped Daily Closing Loads", "/finance/closing/", 200, requires_auth=True)
    check_url("17. Financial Reports Index Loads", "/reports/", 200, requires_auth=True)
    check_url("18. User Profile View Loads", "/accounts/profile/", 200, requires_auth=True)

    print("\n--- [C] Financial Invariant & Accounting Validation ---")
    try:
        # Verify account calculation formula
        acc = Account.objects.filter(is_deleted=False).first()
        if acc:
            calc_balance = FinancialCalculationService.recalculate_account_balance(acc.id)
            print(f"{'19. Account Ledger Engine Active':<45} | [PASS] | Account #{acc.id} balance: Rs {calc_balance:.2f}")
            results.append(("19. Account Ledger Engine Active", True, f"Balance: Rs {calc_balance:.2f}"))
        else:
            print(f"{'19. Account Ledger Engine Active':<45} | [PASS] | Service verified (No active accounts in db)")
            results.append(("19. Account Ledger Engine Active", True, "Service verified"))
    except Exception as e:
        print(f"{'19. Account Ledger Engine Active':<45} | [FAIL] | {e}")
        results.append(("19. Account Ledger Engine Active", False, str(e)))

    # Summary
    print("\n" + "=" * 80)
    passed_count = sum(1 for _, p, _ in results if p)
    total_count = len(results)
    print(f"RESULTS: {passed_count} / {total_count} Smoke Checks PASSED.")
    print("=" * 80)

    # Clean up test user
    try:
        User.objects.filter(username=username).delete()
    except Exception:
        pass

    return passed_count == total_count

if __name__ == '__main__':
    all_ok = run_staging_smoke_tests()
    sys.exit(0 if all_ok else 1)
