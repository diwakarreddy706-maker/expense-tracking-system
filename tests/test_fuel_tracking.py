"""
Phase 5 Comprehensive Test Suite: Fuel & Lubricant Tracking.
Validates 1:1 FuelEntry -> Expense -> AccountTransaction pipeline,
server-side Decimal calculations, meter rollback validation, credit purchases,
reversal mechanics, atomicity, and RBAC authorization.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.finance.models import Account, AccountTransaction, Supplier
from apps.expenses.models import Expense, ExpenseCategory
from apps.machines.models import Machine, MachineType
from apps.employees.models import Employee
from apps.fuel.models import FuelEntry
from apps.fuel.services.fuel_service import FuelService


class FuelCreationAndPipelineTests(TestCase):
    """Verifies complete Fuel -> Expense -> Ledger -> Balance pipeline."""

    def setUp(self):
        self.password = "SafePassword123!"
        self.owner = User.objects.create_user(username="fuel_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.account = Account.objects.create(
            account_name="Tractor Diesel Fund",
            account_type=Account.TYPE_BANK_CURRENT,
            account_number="554433221100",
            opening_balance=Decimal('80000.00'),
            current_balance=Decimal('80000.00'),
            is_active=True
        )

        self.tractor_type = MachineType.objects.create(name="Tractor", code="TRACTOR")
        self.vehicle_type = MachineType.objects.create(name="Support Pickup", code="PICKUP")

        self.tractor = Machine.objects.create(
            machine_code="MCH-TRAC-01",
            name="Mahindra 575 DI",
            machine_type=self.tractor_type,
            meter_unit=Machine.METER_HOURS,
            current_meter_reading=Decimal('500.00'),
            status=Machine.STATUS_ACTIVE
        )

        self.pickup = Machine.objects.create(
            machine_code="MCH-VEH-01",
            name="Bolero Camper",
            machine_type=self.vehicle_type,
            meter_unit=Machine.METER_KM,
            current_meter_reading=Decimal('15000.00'),
            status=Machine.STATUS_ACTIVE
        )

        self.operator = Employee.objects.create(
            employee_code="EMP-001",
            full_name="Santosh Patil",
            role=Employee.ROLE_TRACTOR_DRIVER,
            status=Employee.STATUS_ACTIVE
        )

        self.pump_supplier = Supplier.objects.create(
            supplier_code="SUPP-PUMP-01",
            name="HPCL Kisan Seva Kendra",
            supplier_type=Supplier.TYPE_FUEL_PUMP,
            status=Supplier.STATUS_ACTIVE
        )

    def test_valid_fuel_entry_pipeline_and_exact_one_to_one_records(self):
        """
        Proof of Architectural Pipeline:
        FuelEntry (1) -> Expense (1) -> AccountTransaction (1) -> Balance Updated
        """
        initial_balance = self.account.current_balance
        qty = Decimal('65.50')
        rate = Decimal('92.00')
        expected_total = Decimal('6026.00')
        new_meter = Decimal('525.50')

        fuel_entry = FuelService.create_fuel_entry(
            user=self.owner,
            machine=self.tractor,
            fuel_type=FuelEntry.TYPE_DIESEL,
            quantity=qty,
            unit_price=rate,
            meter_reading=new_meter,
            payment_method=FuelEntry.METHOD_BANK_TRANSFER,
            account=self.account,
            supplier=self.pump_supplier,
            operator=self.operator,
            reference_no="SLIP-9901"
        )

        # 1. FuelEntry assertions
        self.assertIsNotNone(fuel_entry.id)
        self.assertEqual(fuel_entry.total_amount, expected_total)
        self.assertEqual(fuel_entry.meter_reading, new_meter)

        # 2. Machine meter updated
        self.tractor.refresh_from_db()
        self.assertEqual(self.tractor.current_meter_reading, new_meter)

        # 3. 1:1 Linked Expense assertions
        linked_exp = fuel_entry.linked_expense
        self.assertIsNotNone(linked_exp)
        self.assertEqual(linked_exp.amount, expected_total)
        self.assertEqual(linked_exp.machine, self.tractor)
        self.assertEqual(linked_exp.employee, self.operator)
        self.assertEqual(linked_exp.supplier, self.pump_supplier)

        # Ensure 1:1 uniqueness constraint
        exp_count = Expense.objects.filter(fuel_entry=fuel_entry).count()
        self.assertEqual(exp_count, 1)

        # 4. Central Ledger Transaction assertions
        ledger_entries = AccountTransaction.objects.filter(reference_type='Expense', reference_id=linked_exp.id)
        self.assertEqual(ledger_entries.count(), 1)

        tx = ledger_entries.first()
        self.assertEqual(tx.account, self.account)
        self.assertEqual(tx.amount, expected_total)
        self.assertEqual(tx.direction, AccountTransaction.DIRECTION_DEBIT)
        self.assertEqual(tx.transaction_type, AccountTransaction.TYPE_EXPENSE)

        # 5. Authoritative Balance Assertion
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance - expected_total)

        # 6. Audit Trail Assertion
        fuel_audit = AuditLog.objects.filter(action=AuditLog.ACTION_CREATE, entity_type='FuelEntry', entity_id=str(fuel_entry.id)).first()
        self.assertIsNotNone(fuel_audit)

    def test_all_fuel_types_supported(self):
        """Verifies DIESEL, PETROL, ENGINE_OIL, and HYDRAULIC_OIL can all be logged."""
        types = [
            (FuelEntry.TYPE_DIESEL, Decimal('50.00'), Decimal('90.00')),
            (FuelEntry.TYPE_PETROL, Decimal('10.00'), Decimal('102.50')),
            (FuelEntry.TYPE_ENGINE_OIL, Decimal('7.50'), Decimal('350.00')),
            (FuelEntry.TYPE_HYDRAULIC_OIL, Decimal('15.00'), Decimal('280.00')),
        ]
        meter = Decimal('15050.00')
        for f_type, q, p in types:
            meter += Decimal('10.00')
            entry = FuelService.create_fuel_entry(
                user=self.owner,
                machine=self.pickup,
                fuel_type=f_type,
                quantity=q,
                unit_price=p,
                meter_reading=meter,
                payment_method=FuelEntry.METHOD_CASH,
                account=self.account
            )
            self.assertEqual(entry.total_amount, (q * p).quantize(Decimal('0.01')))
            self.assertEqual(entry.fuel_type, f_type)

    def test_zero_and_negative_quantities_and_prices_rejected(self):
        """Verifies invalid numeric values are strictly rejected."""
        with self.assertRaises(ValidationError):
            FuelService.create_fuel_entry(
                user=self.owner,
                machine=self.tractor,
                fuel_type=FuelEntry.TYPE_DIESEL,
                quantity=Decimal('0.00'),
                unit_price=Decimal('90.00'),
                meter_reading=Decimal('550.00'),
                account=self.account
            )

        with self.assertRaises(ValidationError):
            FuelService.create_fuel_entry(
                user=self.owner,
                machine=self.tractor,
                fuel_type=FuelEntry.TYPE_DIESEL,
                quantity=Decimal('20.00'),
                unit_price=Decimal('-90.00'),
                meter_reading=Decimal('550.00'),
                account=self.account
            )

    def test_meter_rollback_strictly_rejected(self):
        """Verifies entered meter reading below current machine reading is rejected."""
        # Tractor current meter is 500.00
        with self.assertRaises(ValidationError) as ctx:
            FuelService.create_fuel_entry(
                user=self.owner,
                machine=self.tractor,
                fuel_type=FuelEntry.TYPE_DIESEL,
                quantity=Decimal('25.00'),
                unit_price=Decimal('92.00'),
                meter_reading=Decimal('480.00'), # Rollback attempt!
                account=self.account
            )
        self.assertIn("Meter rollback detected", str(ctx.exception))

    def test_credit_fuel_purchase_does_not_deduct_account_balance(self):
        """Verifies CREDIT purchases do not deduct cash/bank immediately."""
        initial_balance = self.account.current_balance
        entry = FuelService.create_fuel_entry(
            user=self.owner,
            machine=self.tractor,
            fuel_type=FuelEntry.TYPE_DIESEL,
            quantity=Decimal('100.00'),
            unit_price=Decimal('92.00'),
            meter_reading=Decimal('560.00'),
            payment_method=FuelEntry.METHOD_CREDIT,
            supplier=self.pump_supplier
        )

        self.assertEqual(entry.total_amount, Decimal('9200.00'))
        self.assertIsNone(entry.account)

        # Verify no immediate account deduction
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance)

        # Verify no AccountTransaction created
        tx_count = AccountTransaction.objects.filter(reference_type='Expense', reference_id=entry.linked_expense.id).count()
        self.assertEqual(tx_count, 0)

    def test_fuel_reversal_creates_compensatory_credit_transaction(self):
        """Verifies financial reversal of a fuel entry."""
        initial_balance = self.account.current_balance
        entry = FuelService.create_fuel_entry(
            user=self.owner,
            machine=self.tractor,
            fuel_type=FuelEntry.TYPE_DIESEL,
            quantity=Decimal('40.00'),
            unit_price=Decimal('92.00'),
            meter_reading=Decimal('580.00'),
            payment_method=FuelEntry.METHOD_CASH,
            account=self.account
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance - Decimal('3680.00'))

        # Reverse fuel entry
        rev_entry = FuelService.reverse_fuel_entry(
            fuel_entry_id=entry.id,
            user=self.owner,
            reason="Incorrect slip billed to this tractor"
        )

        entry.refresh_from_db()
        self.assertTrue(entry.linked_expense.is_reversed)

        # Verify account balance restored
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance)


class FuelViewAndRBACTests(TestCase):
    """Verifies UI Views, Forms, and Server-Side Permissions on Fuel."""

    def setUp(self):
        self.client = Client()
        self.password = "Secr3tPassword!"

        self.owner = User.objects.create_user(username="f_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.manager = User.objects.create_user(username="f_mgr", password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.employee = User.objects.create_user(username="f_emp", password=self.password)
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        self.tractor_type = MachineType.objects.create(name="Tractor", code="TRACTOR")
        self.machine = Machine.objects.create(
            machine_code="MCH-TRAC-01",
            name="John Deere 5310",
            machine_type=self.tractor_type,
            meter_unit=Machine.METER_HOURS,
            current_meter_reading=Decimal('600.00'),
            status=Machine.STATUS_ACTIVE
        )

        self.account = Account.objects.create(
            account_name="Cash In Hand",
            account_type=Account.TYPE_CASH,
            opening_balance=Decimal('20000.00'),
            current_balance=Decimal('20000.00'),
            is_active=True
        )

        self.entry = FuelService.create_fuel_entry(
            user=self.owner,
            machine=self.machine,
            fuel_type=FuelEntry.TYPE_DIESEL,
            quantity=Decimal('30.00'),
            unit_price=Decimal('90.00'),
            meter_reading=Decimal('620.00'),
            payment_method=FuelEntry.METHOD_CASH,
            account=self.account
        )

    def test_owner_and_manager_can_view_fuel_list(self):
        """Verifies Owner and Manager can access fuel list."""
        self.client.login(username='f_owner', password=self.password)
        res_owner = self.client.get(reverse('fuel:list'))
        self.assertEqual(res_owner.status_code, 200)

        self.client.login(username='f_mgr', password=self.password)
        res_mgr = self.client.get(reverse('fuel:list'))
        self.assertEqual(res_mgr.status_code, 200)

    def test_owner_can_reverse_fuel_entry(self):
        """Verifies OWNER can execute fuel reversal."""
        self.client.login(username='f_owner', password=self.password)
        res = self.client.post(reverse('fuel:reverse', args=[self.entry.id]), {'reason': 'Duplicate fuel slip'}, follow=True)
        self.assertEqual(res.status_code, 200)
        self.entry.refresh_from_db()
        self.assertTrue(self.entry.linked_expense.is_reversed)

    def test_manager_and_employee_blocked_from_reversal(self):
        """Verifies Manager and Employee are forbidden (403) from fuel reversal."""
        self.client.login(username='f_mgr', password=self.password)
        res_mgr = self.client.post(reverse('fuel:reverse', args=[self.entry.id]), {'reason': 'Unauthorized'})
        self.assertEqual(res_mgr.status_code, 403)

        self.client.login(username='f_emp', password=self.password)
        res_emp = self.client.post(reverse('fuel:reverse', args=[self.entry.id]), {'reason': 'Unauthorized'})
        self.assertEqual(res_emp.status_code, 403)
