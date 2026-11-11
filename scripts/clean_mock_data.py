#!/usr/bin/env python
"""
Client Handover: Clean Slate Database Sanitizer.
Safely purges mock transactions, test accounts, mock receivables, and development users.
Preserves Machine Types, Expense Categories, and creates the client Owner account.
"""

import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_tracking_core.settings.development')

import django
django.setup()

from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from apps.accounts.models import UserProfile
from apps.finance.models import (
    Account, AccountTransaction, Customer, Supplier, 
    Receivable, Payable, CustomerPayment, SupplierPayment, DailyClosing
)
from apps.expenses.models import Expense
from apps.machines.models import MachineWorkEntry, MachineBooking, MaintenanceJob
from apps.employees.models import EmployeePayment, EmployeeCompensation
from apps.audit.models import AuditLog
from apps.reports.models import CompanyProfile


def sanitize_database():
    print("=" * 70)
    print("   AGRIBOS ERP -- CLIENT HANDOVER DATABASE SANITIZATION")
    print("=" * 70)

    with transaction.atomic():
        # 1. Clear Financial Transactions & Ledgers
        tx_count = AccountTransaction.objects.count()
        AccountTransaction.objects.all().delete()
        print(f"[OK] Cleared Account Transactions: {tx_count} records removed.")

        cp_count = CustomerPayment.objects.count()
        CustomerPayment.objects.all().delete()
        print(f"[OK] Cleared Customer Payments: {cp_count} records removed.")

        sp_count = SupplierPayment.objects.count()
        SupplierPayment.objects.all().delete()
        print(f"[OK] Cleared Supplier Payments: {sp_count} records removed.")

        rcv_count = Receivable.objects.count()
        Receivable.objects.all().delete()
        print(f"[OK] Cleared Receivables: {rcv_count} records removed.")

        pay_count = Payable.objects.count()
        Payable.objects.all().delete()
        print(f"[OK] Cleared Payables: {pay_count} records removed.")

        dc_count = DailyClosing.objects.count()
        DailyClosing.objects.all().delete()
        print(f"[OK] Cleared Daily Closings: {dc_count} records removed.")

        # 2. Clear Operational Fuel, Work Entries & Expenses (FuelEntry uses RESTRICT on Expense)
        from apps.fuel.models import FuelEntry
        from apps.budgets.models import Budget, BudgetItem
        fuel_count = FuelEntry.objects.count()
        FuelEntry.objects.all().delete()
        print(f"[OK] Cleared Fuel Entries: {fuel_count} records removed.")

        mwe_count = MachineWorkEntry.objects.count()
        MachineWorkEntry.objects.all().delete()
        print(f"[OK] Cleared Machine Work Entries: {mwe_count} records removed.")

        mb_count = MachineBooking.objects.count()
        MachineBooking.objects.all().delete()
        print(f"[OK] Cleared Machine Bookings: {mb_count} records removed.")

        mj_count = MaintenanceJob.objects.count()
        MaintenanceJob.objects.all().delete()
        print(f"[OK] Cleared Maintenance Jobs: {mj_count} records removed.")

        bi_count = BudgetItem.objects.count()
        BudgetItem.objects.all().delete()
        b_count = Budget.objects.count()
        Budget.objects.all().delete()
        print(f"[OK] Cleared Budgets & Items: {b_count} budgets, {bi_count} items removed.")

        exp_count = Expense.objects.count()
        Expense.objects.all().delete()
        print(f"[OK] Cleared Expense Vouchers: {exp_count} records removed.")

        # 3. Clear Wage Settlements (if any)
        ep_count = EmployeePayment.objects.count()
        EmployeePayment.objects.all().delete()
        print(f"[OK] Cleared Employee Payments: {ep_count} records removed.")

        ec_count = EmployeeCompensation.objects.count()
        EmployeeCompensation.objects.all().delete()
        print(f"[OK] Cleared Employee Compensations: {ec_count} records removed.")

        # 4. Clear Mock Customers & Suppliers
        cust_count = Customer.objects.count()
        Customer.objects.all().delete()
        print(f"[OK] Cleared Mock Customers: {cust_count} records removed.")

        supp_count = Supplier.objects.count()
        Supplier.objects.all().delete()
        print(f"[OK] Cleared Mock Suppliers: {supp_count} records removed.")

        # 5. Clear Accounts (client will enter real accounts)
        acc_count = Account.objects.count()
        Account.objects.all().delete()
        print(f"[OK] Cleared Accounts (including simulation accounts): {acc_count} records removed.")

        # 6. Clear Audit & Session History
        audit_count = AuditLog.objects.count()
        AuditLog.objects.all().delete()
        print(f"[OK] Cleared Audit Logs: {audit_count} records removed.")

        sess_count = Session.objects.count()
        Session.objects.all().delete()
        print(f"[OK] Cleared Sessions: {sess_count} records removed.")

        # 7. Setup Client Owner Account & Purge Demo Users
        # Also purge any leftover demo accountants
        demo_accounts = User.objects.filter(username__in=['ramesh_accountant', 'suresh_accountant'])
        if demo_accounts.exists():
            cnt = demo_accounts.count()
            demo_accounts.delete()
            print(f"[OK] Removed {cnt} demo accountant user(s).")

        # Create or update official client owner account without hardcoded credentials
        owner_username = os.getenv('OWNER_USERNAME', 'Doddanna Gowad').strip()
        owner_password = os.getenv('OWNER_PASSWORD', '').strip()
        owner_user, created = User.objects.get_or_create(
            username=owner_username,
            defaults={
                'email': os.getenv('OWNER_EMAIL', 'owner@sribasaveshwara.in'),
                'first_name': 'Doddanna',
                'last_name': 'Gowad',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if owner_password:
            owner_user.set_password(owner_password)
        elif created or not owner_user.has_usable_password():
            generated_pw = secrets.token_urlsafe(12)
            owner_user.set_password(generated_pw)
            print(f"[INFO] Generated temporary password for '{owner_username}' (set OWNER_PASSWORD env var to override).")
        owner_user.is_staff = True
        owner_user.is_superuser = True
        owner_user.save()

        profile, _ = UserProfile.objects.get_or_create(user=owner_user)
        profile.role = UserProfile.ROLE_OWNER
        profile.save()
        action_word = "Created" if created else "Updated"
        print(f"[OK] {action_word} official client user '{owner_username}' (Role: OWNER).")

        # 8. Reset Company Profile Bank Fields for Client Entry
        profile_obj = CompanyProfile.objects.first()
        if profile_obj:
            profile_obj.bank_name = None
            profile_obj.bank_account_no = None
            profile_obj.bank_ifsc = None
            profile_obj.upi_id = None
            profile_obj.gst_number = None
            profile_obj.save()
            print("[OK] Reset CompanyProfile banking and GST fields for clean client setup.")

    print("=" * 70)
    print("DATABASE CLEANUP COMPLETED SUCCESSFULLY. CLEAN SLATE READY.")
    print("Client can now log in as 'owner' and enter their real accounts.")
    print("=" * 70)


if __name__ == '__main__':
    sanitize_database()
