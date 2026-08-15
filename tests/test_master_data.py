"""
Phase 3 Comprehensive Test Suite: Master Data & Entity Setup.
Validates Business Accounts, Expense Categories, Machines & Equipment,
Employees, Customers, Suppliers, unique constraints, soft deletes, RBAC, and audit trail.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.db import IntegrityError
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.finance.models import Account, Customer, Supplier
from apps.expenses.models import ExpenseCategory
from apps.machines.models import Machine, MachineType
from apps.employees.models import Employee


class MasterDataEntityTests(TestCase):
    """Verifies core model constraints, validations, and helper properties."""

    def setUp(self):
        self.tractor_type = MachineType.objects.create(name="Tractor", code="TRACTOR")

    def test_account_creation_and_masking(self):
        """Verifies account creation and masked account number presentation."""
        acc = Account.objects.create(
            account_name="SBI Current 4091",
            account_type=Account.TYPE_BANK_CURRENT,
            account_number="123456784091",
            bank_name="State Bank of India",
            opening_balance=Decimal('50000.00'),
            is_active=True
        )
        self.assertEqual(acc.masked_account_number, "XXXX XXXX 4091")
        self.assertEqual(acc.opening_balance, Decimal('50000.00'))

        # Unique name constraint
        with self.assertRaises(IntegrityError):
            Account.objects.create(
                account_name="SBI Current 4091",
                account_type=Account.TYPE_CASH
            )

    def test_category_hierarchy_and_uniqueness(self):
        """Verifies expense category creation and unique constraints."""
        cat_parent = ExpenseCategory.objects.create(name="Vehicle Operations", code="CAT-VEH")
        cat_child = ExpenseCategory.objects.create(name="Diesel Fuel", code="CAT-DIESEL", parent=cat_parent)

        self.assertEqual(cat_child.parent, cat_parent)
        self.assertIn("Vehicle Operations", str(cat_child))

        # Duplicate code prevention
        with self.assertRaises(IntegrityError):
            ExpenseCategory.objects.create(name="Another Fuel", code="CAT-DIESEL")

    def test_machine_master_and_meter_unit(self):
        """Verifies machine registration, meter unit, and code uniqueness."""
        mch = Machine.objects.create(
            machine_code="MCH-TRAC-01",
            name="John Deere 5310",
            machine_type=self.tractor_type,
            registration_no="KA-05-AA-1234",
            meter_unit=Machine.METER_HOURS,
            current_meter_reading=Decimal('1250.50'),
            status=Machine.STATUS_ACTIVE
        )
        self.assertEqual(mch.meter_unit, 'HOURS')
        self.assertEqual(mch.current_meter_reading, Decimal('1250.50'))

        # Duplicate machine code prevention
        with self.assertRaises(IntegrityError):
            Machine.objects.create(
                machine_code="MCH-TRAC-01",
                name="Duplicate Tractor",
                machine_type=self.tractor_type
            )

    def test_employee_master_and_role(self):
        """Verifies employee record and role configuration."""
        emp = Employee.objects.create(
            employee_code="EMP-001",
            full_name="Ramesh Kumar",
            role=Employee.ROLE_TRACTOR_DRIVER,
            wage_type=Employee.WAGE_DAILY,
            base_rate=Decimal('600.00'),
            status=Employee.STATUS_ACTIVE
        )
        self.assertEqual(emp.role, 'TRACTOR_DRIVER')
        self.assertEqual(emp.base_rate, Decimal('600.00'))

        # Duplicate employee code prevention
        with self.assertRaises(IntegrityError):
            Employee.objects.create(
                employee_code="EMP-001",
                full_name="Another Staff",
                role=Employee.ROLE_SHOP_STAFF
            )

    def test_customer_and_supplier_soft_delete(self):
        """Verifies Customer and Supplier records and soft-delete flag behavior."""
        cust = Customer.objects.create(customer_code="CUST-001", name="Anand Patel")
        supp = Supplier.objects.create(supplier_code="SUPP-001", name="Kisan Fuel Pump", supplier_type=Supplier.TYPE_FUEL_PUMP)

        self.assertFalse(cust.is_deleted)
        self.assertFalse(supp.is_deleted)

        cust.is_deleted = True
        cust.save()
        supp.is_deleted = True
        supp.save()

        self.assertTrue(Customer.objects.get(id=cust.id).is_deleted)
        self.assertTrue(Supplier.objects.get(id=supp.id).is_deleted)


class MasterDataRBACTests(TestCase):
    """Verifies server-side authorization on Master Data views."""

    def setUp(self):
        self.client = Client()
        self.password = "SecretPass123!"

        self.owner = User.objects.create_user(username="master_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.accountant = User.objects.create_user(username="master_acc", password=self.password)
        self.accountant.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant.profile.save()

        self.manager = User.objects.create_user(username="master_mgr", password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.employee = User.objects.create_user(username="master_emp", password=self.password)
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        self.tractor_type = MachineType.objects.create(name="Tractor", code="TRACTOR")

    def test_owner_master_access(self):
        """Verifies OWNER can access and manage all master entities."""
        self.client.login(username='master_owner', password=self.password)

        self.assertEqual(self.client.get(reverse('finance:accounts')).status_code, 200)
        self.assertEqual(self.client.get(reverse('expenses:categories')).status_code, 200)
        self.assertEqual(self.client.get(reverse('machines:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('employees:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:customers')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:suppliers')).status_code, 200)

    def test_accountant_master_access_and_restrictions(self):
        """Verifies ACCOUNTANT can access financial masters (Accounts, Categories, Customers, Suppliers) but blocked from Machines."""
        self.client.login(username='master_acc', password=self.password)

        self.assertEqual(self.client.get(reverse('finance:accounts')).status_code, 200)
        self.assertEqual(self.client.get(reverse('expenses:categories')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:customers')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:suppliers')).status_code, 200)

        # Blocked from Machines management
        self.assertEqual(self.client.get(reverse('machines:list')).status_code, 403)

    def test_manager_master_access_and_restrictions(self):
        """Verifies MANAGER can manage Machines, Employees, Customers, Suppliers; blocked from Accounts & Categories."""
        self.client.login(username='master_mgr', password=self.password)

        self.assertEqual(self.client.get(reverse('machines:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('employees:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:customers')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:suppliers')).status_code, 200)

        # Blocked from Accounts & Categories
        self.assertEqual(self.client.get(reverse('finance:accounts')).status_code, 403)
        self.assertEqual(self.client.get(reverse('expenses:categories')).status_code, 403)

    def test_employee_strict_restrictions(self):
        """Verifies EMPLOYEE is strictly blocked from all master data management views."""
        self.client.login(username='master_emp', password=self.password)

        self.assertEqual(self.client.get(reverse('finance:accounts')).status_code, 403)
        self.assertEqual(self.client.get(reverse('expenses:categories')).status_code, 403)
        self.assertEqual(self.client.get(reverse('machines:list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('employees:list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('finance:customers')).status_code, 403)
        self.assertEqual(self.client.get(reverse('finance:suppliers')).status_code, 403)


class MasterDataAuditTests(TestCase):
    """Verifies audit trail creation upon master entity mutations."""

    def setUp(self):
        self.client = Client()
        self.password = "AdminSecretPass123!"
        self.owner = User.objects.create_user(username="audit_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()
        self.client.login(username='audit_owner', password=self.password)

    def test_account_creation_audit(self):
        """Verifies creating an account generates an AuditLog entry."""
        response = self.client.post(reverse('finance:account_create'), {
            'account_name': 'HDFC Cash Box',
            'account_type': 'CASH',
            'opening_balance': '15000.00',
            'opening_balance_date': '2026-08-15',
            'is_active': True
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        audit = AuditLog.objects.filter(action=AuditLog.ACTION_CREATE, entity_type='Account').first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.user, self.owner)

    def test_customer_soft_delete_audit(self):
        """Verifies soft deleting a customer generates a SOFT_DELETE audit log."""
        cust = Customer.objects.create(customer_code="CUST-AUDIT", name="Audit Customer")
        response = self.client.get(reverse('finance:customer_delete', args=[cust.id]), follow=True)
        self.assertEqual(response.status_code, 200)

        cust.refresh_from_db()
        self.assertTrue(cust.is_deleted)

        audit = AuditLog.objects.filter(action=AuditLog.ACTION_SOFT_DELETE, entity_type='Customer', entity_id=str(cust.id)).first()
        self.assertIsNotNone(audit)
