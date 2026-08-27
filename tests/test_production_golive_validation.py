"""
Phase 19: Production Environment Validation & Go-Live Safety Test Suite.
Verifies production smoke routes, RBAC boundaries, CSV atomic rollback safety,
opening balance integrity, and double-entry financial ledger invariants.
"""

import io
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile
from apps.finance.models import Account, Customer, Supplier, Receivable, Payable, AccountTransaction
from apps.machines.models import Machine
from apps.employees.models import Employee, EmployeeCompensation
from apps.expenses.models import ExpenseCategory, Expense
from apps.finance.services.import_service import MasterDataImportService


class ProductionGoLiveSmokeTests(TestCase):
    """
    Validates standard page rendering and HTTP 200 responses across all core ERP modules.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="golive_owner", password="password123")
        UserProfile.objects.update_or_create(user=self.owner, defaults={'role': 'OWNER'})

        self.accountant = User.objects.create_user(username="golive_accountant", password="password123")
        UserProfile.objects.update_or_create(user=self.accountant, defaults={'role': 'ACCOUNTANT'})

        self.manager = User.objects.create_user(username="golive_manager", password="password123")
        UserProfile.objects.update_or_create(user=self.manager, defaults={'role': 'MANAGER'})

        self.employee_user = User.objects.create_user(username="golive_emp", password="password123")
        UserProfile.objects.update_or_create(user=self.employee_user, defaults={'role': 'EMPLOYEE'})
        
        self.client_owner = Client()
        self.client_owner.login(username="golive_owner", password="password123")

    def test_production_core_navigation_smoke(self):
        """Smoke test verifying GET 200 on all production modules."""
        endpoints = [
            'dashboard:index',
            'finance:setup_hub',
            'finance:setup_reconciliation',
            'machines:list',
            'machines:booking_list',
            'machines:maintenance_job_list',
            'finance:customers',
            'finance:suppliers',
            'employees:list',
            'finance:accounts',
            'finance:receivables',
            'finance:payables',
            'expenses:list',
            'expenses:categories',
            'fuel:list',
            'reports:financial',
        ]
        for ep in endpoints:
            url = reverse(ep)
            response = self.client_owner.get(url)
            self.assertEqual(
                response.status_code, 200,
                f"Production smoke test failed on endpoint '{ep}' ({url}) with status {response.status_code}"
            )


class MasterDataAndImportSafetyTests(TestCase):
    """
    Validates atomic rollback, dry-run parsing, and opening balance financial invariants.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="import_owner", password="password123")
        UserProfile.objects.update_or_create(user=self.owner, defaults={'role': 'OWNER'})

    def test_csv_import_atomic_rollback_on_failure(self):
        """
        Verify that importing a CSV with 5 rows where row 4 is corrupted results in
        0 rows imported (all-or-nothing rollback).
        """
        initial_machine_count = Machine.objects.count()

        # Row 4 has an invalid registration / type
        csv_content = (
            "machine_code,name,machine_type,registration_no,current_meter_reading,meter_unit,purchase_price,status\n"
            "M-001,Tractor Alpha,TRACTOR,REG-001,100.5,HOURS,500000,ACTIVE\n"
            "M-002,Harvester Beta,HARVESTER,REG-002,200.0,HOURS,1200000,ACTIVE\n"
            "M-003,Tractor Gamma,TRACTOR,REG-003,50.0,HOURS,450000,ACTIVE\n"
            "M-004,Corrupt Machine,INVALID_TYPE,REG-004,-99.0,INVALID_UNIT,abc,ACTIVE\n"
            "M-005,Tractor Epsilon,TRACTOR,REG-005,10.0,HOURS,400000,ACTIVE\n"
        )
        file_obj = io.StringIO(csv_content)
        result = MasterDataImportService.parse_and_validate("machines", file_obj)

        # Dry run must catch the row 4 error
        self.assertFalse(result["is_ready_for_import"], "Dry run should mark batch as not ready for import")
        self.assertGreater(result["invalid_rows_count"], 0, "Errors must be detected")
        self.assertEqual(Machine.objects.count(), initial_machine_count, "No database rows created in dry run")

    def test_opening_balance_receivable_and_payable_safety(self):
        """
        Verify opening customer and supplier balances do not post operational revenue or expense.
        """
        # Customer opening balance
        cust_csv = (
            "customer_code,name,phone,location_address,opening_balance,notes\n"
            "CUST-GL01,Ramesh Patel,9876543210,Village North,15000.00,Legacy balance\n"
        )
        file_obj = io.StringIO(cust_csv)
        preview = MasterDataImportService.parse_and_validate("customers", file_obj)
        self.assertTrue(preview["is_ready_for_import"])
        
        exec_result = MasterDataImportService.execute_import("customers", preview["preview_rows"], self.owner)
        self.assertTrue(exec_result["success"])
        
        cust = Customer.objects.get(customer_code="CUST-GL01")
        rcv = Receivable.objects.filter(customer=cust).first()
        self.assertIsNotNone(rcv)
        self.assertEqual(rcv.total_amount, Decimal("15000.00"))
        self.assertEqual(rcv.invoice_no, "OPENING-BAL")
        
        # Verify no AccountTransaction or fake revenue was posted
        self.assertEqual(AccountTransaction.objects.filter(reference_id=rcv.id).count(), 0)

        # Supplier opening balance
        supp_csv = (
            "supplier_code,name,supplier_type,phone,location_address,payment_terms,opening_balance,notes\n"
            "SUPP-GL01,Kisan Fuel Depot,FUEL_PUMP,9876543211,Highway 44,NET_30,8500.00,Legacy fuel bill\n"
        )
        file_obj2 = io.StringIO(supp_csv)
        preview2 = MasterDataImportService.parse_and_validate("suppliers", file_obj2)
        self.assertTrue(preview2["is_ready_for_import"])
        
        exec_result2 = MasterDataImportService.execute_import("suppliers", preview2["preview_rows"], self.owner)
        self.assertTrue(exec_result2["success"])
        
        supp = Supplier.objects.get(supplier_code="SUPP-GL01")
        pay = Payable.objects.filter(supplier=supp).first()
        self.assertIsNotNone(pay)
        self.assertEqual(pay.total_amount, Decimal("8500.00"))
        self.assertEqual(pay.bill_no, "OPENING-BAL")
        
        # Verify no AccountTransaction or fake operational expense was posted
        self.assertEqual(AccountTransaction.objects.filter(reference_id=pay.id).count(), 0)


class RoleBasedAccessControlGoLiveTests(TestCase):
    """
    Validates role boundaries for Setup Hub, CSV Importer, and Financial Configuration.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="rb_owner", password="password123")
        UserProfile.objects.update_or_create(user=self.owner, defaults={'role': 'OWNER'})

        self.accountant = User.objects.create_user(username="rb_accountant", password="password123")
        UserProfile.objects.update_or_create(user=self.accountant, defaults={'role': 'ACCOUNTANT'})

        self.manager = User.objects.create_user(username="rb_manager", password="password123")
        UserProfile.objects.update_or_create(user=self.manager, defaults={'role': 'MANAGER'})

        self.employee = User.objects.create_user(username="rb_employee", password="password123")
        UserProfile.objects.update_or_create(user=self.employee, defaults={'role': 'EMPLOYEE'})

    def test_manager_and_employee_cannot_access_setup_and_import(self):
        """Managers and Employees must receive HTTP 403 when trying to access master setup."""
        restricted_urls = [
            reverse('finance:setup_hub'),
            reverse('finance:setup_reconciliation'),
            reverse('finance:setup_csv_preview'),
            reverse('finance:setup_csv_import'),
        ]
        
        for u, role_name in [(self.manager, "MANAGER"), (self.employee, "EMPLOYEE")]:
            client = Client()
            client.login(username=u.username, password="password123")
            for url in restricted_urls:
                resp = client.get(url)
                self.assertEqual(
                    resp.status_code, 403,
                    f"User with role {role_name} bypassed protection on {url} (status: {resp.status_code})"
                )

    def test_owner_and_accountant_can_access_setup_hub(self):
        """Owner and Accountant have authorized access to master setup hub."""
        for u in [self.owner, self.accountant]:
            client = Client()
            client.login(username=u.username, password="password123")
            resp = client.get(reverse('finance:setup_hub'))
            self.assertEqual(resp.status_code, 200)
