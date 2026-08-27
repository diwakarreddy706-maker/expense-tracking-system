"""
Phase 17 Comprehensive Test Suite: Business Master Data Setup & Onboarding.
Validates end-to-end master data operations, accounts, machinery, customers,
suppliers, employees, wage configurations, opening balances, RBAC security,
and Master Data Setup Hub dashboard calculations.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.db import IntegrityError

from apps.accounts.models import UserProfile
from apps.finance.models import Account, Customer, Supplier, Receivable, Payable
from apps.machines.models import Machine, MachineType
from apps.employees.models import Employee, EmployeeCompensation
from apps.expenses.models import ExpenseCategory
from apps.budgets.models import Budget
from apps.finance.services.balance_service import FinancialCalculationService


class MasterDataOnboardingWorkflowTests(TestCase):
    """Verifies master data CRUD, opening balances, and Setup Hub view."""

    def setUp(self):
        self.client = Client()

        # Seed RBAC users
        self.owner_user = User.objects.create_user(username='onboard_owner', password='OwnerPass123!')
        UserProfile.objects.update_or_create(user=self.owner_user, defaults={'role': 'OWNER', 'phone_number': '9876543210'})

        self.accountant_user = User.objects.create_user(username='onboard_acct', password='AcctPass123!')
        UserProfile.objects.update_or_create(user=self.accountant_user, defaults={'role': 'ACCOUNTANT', 'phone_number': '9876543211'})

        self.employee_user = User.objects.create_user(username='onboard_emp', password='EmpPass123!')
        UserProfile.objects.update_or_create(user=self.employee_user, defaults={'role': 'EMPLOYEE', 'phone_number': '9876543212'})

        # Machine Types
        self.tractor_type = MachineType.objects.create(name="Tractor", code="TRACTOR")
        self.harvester_type = MachineType.objects.create(name="Paddy Harvester", code="PADDY_HARVESTER")

    def test_account_creation_and_opening_balance_math(self):
        """Verifies account creation and authoritative opening balance calculation."""
        acc = Account.objects.create(
            account_name="HDFC Current 9901",
            account_type=Account.TYPE_BANK_CURRENT,
            account_number="123456789901",
            bank_name="HDFC Bank",
            ifsc_code="HDFC0001234",
            opening_balance=Decimal('75000.00'),
            is_active=True
        )
        self.assertEqual(acc.masked_account_number, "XXXX XXXX 9901")
        
        # Test authoritative balance calculation
        calculated_bal = FinancialCalculationService.recalculate_account_balance(acc.id)
        self.assertEqual(calculated_bal, Decimal('75000.00'))

    def test_machinery_master_onboarding(self):
        """Verifies machine registration, meter reading, and unique constraints."""
        mch = Machine.objects.create(
            machine_code="MCH-HARV-01",
            name="Kubota DC-68G",
            machine_type=self.harvester_type,
            registration_no="KA-04-E-5678",
            meter_unit=Machine.METER_HOURS,
            current_meter_reading=Decimal('450.00'),
            status=Machine.STATUS_ACTIVE
        )
        self.assertEqual(mch.machine_code, "MCH-HARV-01")
        self.assertEqual(mch.current_meter_reading, Decimal('450.00'))

        # Duplicate code prevented
        with self.assertRaises(IntegrityError):
            Machine.objects.create(
                machine_code="MCH-HARV-01",
                name="Duplicate Harvester",
                machine_type=self.harvester_type
            )

    def test_customer_and_supplier_onboarding(self):
        """Verifies customer and supplier entity creation and phone / location records."""
        cust = Customer.objects.create(
            customer_code="CUST-101",
            name="Venkatesh Rao",
            phone="9845012345",
            location_address="Gowribidanur Village",
            status=Customer.STATUS_ACTIVE
        )
        self.assertEqual(cust.customer_code, "CUST-101")
        self.assertEqual(cust.name, "Venkatesh Rao")

        supp = Supplier.objects.create(
            supplier_code="SUPP-101",
            name="Sri Lakshmi Petrol Bunk",
            supplier_type="FUEL_PUMP",
            phone="9845098765",
            location_address="State Highway 9",
            payment_terms="Net 15",
            status=Supplier.STATUS_ACTIVE
        )
        self.assertEqual(supp.supplier_code, "SUPP-101")
        self.assertEqual(supp.supplier_type, "FUEL_PUMP")

    def test_employee_and_wage_rate_onboarding(self):
        """Verifies staff profile creation and compensation rate assignment."""
        emp = Employee.objects.create(
            employee_code="EMP-201",
            full_name="Anand Kumar",
            role=Employee.ROLE_HARVESTER_OPERATOR,
            wage_type=Employee.WAGE_PER_ACRE,
            base_rate=Decimal('500.00'),
            status=Employee.STATUS_ACTIVE
        )
        comp = EmployeeCompensation.objects.create(
            employee=emp,
            wage_type=Employee.WAGE_PER_ACRE,
            rate=Decimal('500.00'),
            is_active=True
        )
        self.assertEqual(emp.role, 'HARVESTER_OPERATOR')
        self.assertEqual(comp.rate, Decimal('500.00'))

    def test_master_data_setup_hub_rbac(self):
        """Verifies access control: OWNER & ACCOUNTANT allowed, EMPLOYEE & Unauth blocked."""
        setup_url = reverse('finance:setup_hub')

        # 1. Unauthenticated -> Redirect to Login
        res_unauth = self.client.get(setup_url)
        self.assertEqual(res_unauth.status_code, 302)
        self.assertIn('/accounts/login/', res_unauth.url)

        # 2. Employee -> 403 Forbidden
        self.client.login(username='onboard_emp', password='EmpPass123!')
        res_emp = self.client.get(setup_url)
        self.assertEqual(res_emp.status_code, 403)
        self.client.logout()

        # 3. Accountant -> 200 OK
        self.client.login(username='onboard_acct', password='AcctPass123!')
        res_acct = self.client.get(setup_url)
        self.assertEqual(res_acct.status_code, 200)
        self.client.logout()

        # 4. Owner -> 200 OK
        self.client.login(username='onboard_owner', password='OwnerPass123!')
        res_owner = self.client.get(setup_url)
        self.assertEqual(res_owner.status_code, 200)
        self.assertContains(res_owner, "Master Data Setup & Business Onboarding")
        self.assertContains(res_owner, "Machinery Fleet Registry")
        self.assertContains(res_owner, "Financial Accounts & Wallets")
        self.assertContains(res_owner, "Farmers & Clients Master")
        self.assertContains(res_owner, "Suppliers & Outlets")
        self.assertContains(res_owner, "Staff, Drivers & Operators")
