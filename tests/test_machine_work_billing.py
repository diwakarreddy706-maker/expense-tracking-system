from decimal import Decimal
from datetime import time, date, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError

from apps.accounts.models import UserProfile
from apps.machines.models import Machine, MachineType, MachineWorkEntry
from apps.finance.models import Customer, Account, AccountTransaction, Receivable, Payable
from apps.employees.models import Employee
from apps.expenses.models import Expense
from apps.audit.models import AuditLog
from apps.machines.services.work_service import WorkService
from apps.machines.forms import MachineWorkEntryForm


class MachineWorkBillingTestCase(TestCase):
    """
    Comprehensive test suite for Phase 12.4 Machine Work Entry & Billing Workflow.
    Verifies mathematical correctness, Harvester vs Tractor differentiation,
    meter tracking separation, RBAC, audit logging, and absolute ledger isolation.
    """

    def setUp(self):
        self.client = Client()

        # Users & Roles
        self.owner_user = User.objects.create_user(username='m_owner', password='password123')
        self.owner_user.profile.role = UserProfile.ROLE_OWNER
        self.owner_user.profile.save()

        self.manager_user = User.objects.create_user(username='m_manager', password='password123')
        self.manager_user.profile.role = UserProfile.ROLE_MANAGER
        self.manager_user.profile.save()

        self.accountant_user = User.objects.create_user(username='m_accountant', password='password123')
        self.accountant_user.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant_user.profile.save()

        self.employee_user = User.objects.create_user(username='m_employee', password='password123')
        self.employee_user.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee_user.profile.save()

        # Machine Types
        self.harvester_type = MachineType.objects.create(name="Combine Harvester", code="COMBINE_HARVESTER")
        self.tractor_type = MachineType.objects.create(name="Tractor 4WD", code="TRACTOR")

        # Machines
        self.harvester = Machine.objects.create(
            machine_code="MCH-HARV-01",
            name="John Deere W70 Harvester",
            machine_type=self.harvester_type,
            registration_no="KA-04-HV-1001",
            current_meter_reading=Decimal('450.00'),
            meter_unit=Machine.METER_HOURS,
            status=Machine.STATUS_ACTIVE
        )
        self.tractor = Machine.objects.create(
            machine_code="MCH-TRAC-01",
            name="Mahindra 575 DI Tractor",
            machine_type=self.tractor_type,
            registration_no="KA-04-TR-2002",
            current_meter_reading=Decimal('1200.00'),
            meter_unit=Machine.METER_HOURS,
            status=Machine.STATUS_ACTIVE
        )

        # Customer & Employee
        self.customer = Customer.objects.create(
            customer_code="CUST-001",
            name="Ramesh Patel",
            phone="9876543210"
        )
        self.operator = Employee.objects.create(
            employee_code="EMP-001",
            full_name="Suresh Kumar",
            role=Employee.ROLE_HARVESTER_OPERATOR,
            phone_number="9123456780"
        )

        # Business Account (to verify no balance mutations occur)
        self.account = Account.objects.create(
            account_name="Main Current Account",
            account_type=Account.TYPE_BANK_CURRENT,
            opening_balance=Decimal('50000.00'),
            current_balance=Decimal('50000.00')
        )

    # --------------------------------------------------------------------------
    # 1. HARVESTER STANDARD CALCULATION
    # --------------------------------------------------------------------------
    def test_harvester_standard_calculation(self):
        """
        08:00 -> 17:30, Break = 1.5h, Rate = ₹2,400
        Expected: Elapsed = 9.50h, Net = 8.00h, Total = ₹19,200.00
        """
        res = WorkService.calculate_harvester_billing(
            start_time=time(8, 0),
            end_time=time(17, 30),
            break_hours=Decimal('1.50'),
            hourly_rate=Decimal('2400.00')
        )
        self.assertEqual(res['elapsed_hours'], Decimal('9.50'))
        self.assertEqual(res['net_working_hours'], Decimal('8.00'))
        self.assertEqual(res['total_amount'], Decimal('19200.00'))

    # --------------------------------------------------------------------------
    # 2. HARVESTER ZERO BREAK
    # --------------------------------------------------------------------------
    def test_harvester_zero_break(self):
        """
        09:00 -> 12:00, Break = 0.0h, Rate = ₹2,000
        Expected: Elapsed = 3.00h, Net = 3.00h, Total = ₹6,000.00
        """
        res = WorkService.calculate_harvester_billing(
            start_time=time(9, 0),
            end_time=time(12, 0),
            break_hours=Decimal('0.00'),
            hourly_rate=Decimal('2000.00')
        )
        self.assertEqual(res['elapsed_hours'], Decimal('3.00'))
        self.assertEqual(res['net_working_hours'], Decimal('3.00'))
        self.assertEqual(res['total_amount'], Decimal('6000.00'))

    # --------------------------------------------------------------------------
    # 3. HARVESTER FRACTIONAL BREAK
    # --------------------------------------------------------------------------
    def test_harvester_fractional_break(self):
        """
        07:30 -> 13:45 (6.25h), Break = 0.75h, Rate = ₹2,500
        Expected: Elapsed = 6.25h, Net = 5.50h, Total = ₹13,750.00
        """
        res = WorkService.calculate_harvester_billing(
            start_time=time(7, 30),
            end_time=time(13, 45),
            break_hours=Decimal('0.75'),
            hourly_rate=Decimal('2500.00')
        )
        self.assertEqual(res['elapsed_hours'], Decimal('6.25'))
        self.assertEqual(res['net_working_hours'], Decimal('5.50'))
        self.assertEqual(res['total_amount'], Decimal('13750.00'))

    # --------------------------------------------------------------------------
    # 4. INVALID HARVESTER TIME (end_time <= start_time)
    # --------------------------------------------------------------------------
    def test_invalid_harvester_time_rejected(self):
        """end_time <= start_time must raise ValidationError."""
        # Equal times
        with self.assertRaises(ValidationError):
            WorkService.calculate_harvester_billing(
                start_time=time(10, 0),
                end_time=time(10, 0),
                break_hours=Decimal('0.00'),
                hourly_rate=Decimal('2000.00')
            )
        # End time before start time
        with self.assertRaises(ValidationError):
            WorkService.calculate_harvester_billing(
                start_time=time(15, 0),
                end_time=time(11, 0),
                break_hours=Decimal('0.00'),
                hourly_rate=Decimal('2000.00')
            )

    # --------------------------------------------------------------------------
    # 5. BREAK >= ELAPSED TIME
    # --------------------------------------------------------------------------
    def test_break_greater_than_or_equal_to_elapsed_rejected(self):
        """Break duration >= elapsed time must raise ValidationError."""
        # Break equal to elapsed
        with self.assertRaises(ValidationError):
            WorkService.calculate_harvester_billing(
                start_time=time(8, 0),
                end_time=time(12, 0), # 4.0h
                break_hours=Decimal('4.00'),
                hourly_rate=Decimal('2000.00')
            )
        # Break exceeding elapsed
        with self.assertRaises(ValidationError):
            WorkService.calculate_harvester_billing(
                start_time=time(8, 0),
                end_time=time(12, 0), # 4.0h
                break_hours=Decimal('5.00'),
                hourly_rate=Decimal('2000.00')
            )
        # Negative break
        with self.assertRaises(ValidationError):
            WorkService.calculate_harvester_billing(
                start_time=time(8, 0),
                end_time=time(12, 0),
                break_hours=Decimal('-1.00'),
                hourly_rate=Decimal('2000.00')
            )

    # --------------------------------------------------------------------------
    # 6. TRACTOR ACRE BILLING
    # --------------------------------------------------------------------------
    def test_tractor_acre_billing(self):
        """15.5 acres * ₹1,200/acre = ₹18,600.00"""
        res = WorkService.calculate_tractor_billing(
            quantity=Decimal('15.50'),
            unit_rate=Decimal('1200.00')
        )
        self.assertEqual(res['total_amount'], Decimal('18600.00'))

    # --------------------------------------------------------------------------
    # 7. TRACTOR PIECE BILLING
    # --------------------------------------------------------------------------
    def test_tractor_piece_billing(self):
        """250 pieces * ₹50/piece = ₹12,500.00"""
        res = WorkService.calculate_tractor_billing(
            quantity=Decimal('250.00'),
            unit_rate=Decimal('50.00')
        )
        self.assertEqual(res['total_amount'], Decimal('12500.00'))

    # --------------------------------------------------------------------------
    # 8. TRACTOR DOES NOT REQUIRE TIME FIELDS
    # --------------------------------------------------------------------------
    def test_tractor_does_not_require_time_fields(self):
        """A tractor work entry should validate and save without start/end times."""
        entry = WorkService.create_work_entry(
            work_date=date.today(),
            machine=self.tractor,
            customer=self.customer,
            operator=self.operator,
            billing_type=MachineWorkEntry.BILLING_ACRE,
            quantity=Decimal('10.00'),
            unit_rate=Decimal('1500.00'),
            created_by=self.owner_user
        )
        self.assertIsNotNone(entry.id)
        self.assertIsNone(entry.start_time)
        self.assertIsNone(entry.end_time)
        self.assertEqual(entry.total_amount, Decimal('15000.00'))

    # --------------------------------------------------------------------------
    # 9. METER DIFFERENCE CALCULATION
    # --------------------------------------------------------------------------
    def test_meter_difference_calculation(self):
        """Start = 450.00, End = 458.50 -> Difference = 8.50"""
        diff = WorkService.calculate_meter_difference(
            start_meter=Decimal('450.00'),
            end_meter=Decimal('458.50')
        )
        self.assertEqual(diff, Decimal('8.50'))

    # --------------------------------------------------------------------------
    # 10. INVALID METER (End < Start)
    # --------------------------------------------------------------------------
    def test_invalid_meter_rollback_rejected(self):
        """End meter < Start meter must raise ValidationError."""
        with self.assertRaises(ValidationError):
            WorkService.calculate_meter_difference(
                start_meter=Decimal('460.00'),
                end_meter=Decimal('455.00')
            )

    # --------------------------------------------------------------------------
    # 11. BILLING AND METER SEPARATION
    # --------------------------------------------------------------------------
    def test_billing_and_meter_separation(self):
        """
        Billing hours = 8.00 hrs (08:00 to 17:30 with 1.5h break).
        Meter hours = 8.50 hrs (450.00 to 458.50).
        Total bill must remain 8.0 * ₹2,400 = ₹19,200.00, NEVER 8.5 * ₹2,400.
        """
        entry = WorkService.create_work_entry(
            work_date=date.today(),
            machine=self.harvester,
            customer=self.customer,
            operator=self.operator,
            billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
            start_time=time(8, 0),
            end_time=time(17, 30),
            break_hours=Decimal('1.50'),
            hourly_rate=Decimal('2400.00'),
            start_meter=Decimal('450.00'),
            end_meter=Decimal('458.50'),
            created_by=self.owner_user
        )
        self.assertEqual(entry.net_working_hours, Decimal('8.00'))
        self.assertEqual(entry.meter_difference, Decimal('8.50'))
        self.assertEqual(entry.total_amount, Decimal('19200.00'))
        self.assertNotEqual(entry.total_amount, Decimal('8.50') * Decimal('2400.00'))

    # --------------------------------------------------------------------------
    # 12. DECIMAL PRECISION (₹0.01)
    # --------------------------------------------------------------------------
    def test_decimal_precision(self):
        """Calculations must be accurate to ₹0.01 precision."""
        res = WorkService.calculate_harvester_billing(
            start_time=time(8, 0),
            end_time=time(9, 20), # 1 hour 20 min = 1.3333... hours
            break_hours=Decimal('0.00'),
            hourly_rate=Decimal('2150.75')
        )
        self.assertIsInstance(res['total_amount'], Decimal)
        # 1.33 * 2150.75 = 2860.4975 -> 2860.50
        self.assertEqual(res['total_amount'], Decimal('2860.50'))

    # --------------------------------------------------------------------------
    # 13. SERVER-SIDE TAMPERING PROTECTION
    # --------------------------------------------------------------------------
    def test_server_side_tampering_protection(self):
        """Submitting fabricated total_amount in form must be recalculated by server."""
        self.client.login(username='m_owner', password='password123')
        post_data = {
            'work_date': date.today().strftime('%Y-%m-%d'),
            'customer': self.customer.id,
            'machine': self.harvester.id,
            'operator': self.operator.id,
            'billing_type': 'TIME_HOURLY',
            'start_time': '08:00',
            'end_time': '17:30',
            'break_hours': '1.50',
            'hourly_rate': '2400.00',
            'start_meter': '450.00',
            'end_meter': '458.50',
            'total_amount': '10.00', # Fabricated tamper value
            'net_working_hours': '1.00', # Fabricated tamper value
        }
        response = self.client.post(reverse('machines:work_create'), post_data)
        self.assertEqual(response.status_code, 302)

        entry = MachineWorkEntry.objects.latest('id')
        self.assertEqual(entry.total_amount, Decimal('19200.00'))
        self.assertEqual(entry.net_working_hours, Decimal('8.00'))

    # --------------------------------------------------------------------------
    # 14. RBAC ACCESS CONTROL
    # --------------------------------------------------------------------------
    def test_rbac_access_control(self):
        """OWNER, MANAGER, ACCOUNTANT have access; EMPLOYEE gets 403 Forbidden."""
        url = reverse('machines:work_list')

        # Owner -> 200
        self.client.login(username='m_owner', password='password123')
        self.assertEqual(self.client.get(url).status_code, 200)

        # Manager -> 200
        self.client.login(username='m_manager', password='password123')
        self.assertEqual(self.client.get(url).status_code, 200)

        # Accountant -> 200
        self.client.login(username='m_accountant', password='password123')
        self.assertEqual(self.client.get(url).status_code, 200)

        # Employee -> 403
        self.client.login(username='m_employee', password='password123')
        self.assertEqual(self.client.get(url).status_code, 403)

    # --------------------------------------------------------------------------
    # 15. AUDIT LOGGING (CREATE, UPDATE, SOFT_DELETE)
    # --------------------------------------------------------------------------
    def test_audit_logging_lifecycle(self):
        """CREATE, UPDATE, and SOFT_DELETE actions must write to AuditLog."""
        initial_count = AuditLog.objects.filter(entity_type='MachineWorkEntry').count()

        # CREATE
        entry = WorkService.create_work_entry(
            work_date=date.today(),
            machine=self.harvester,
            customer=self.customer,
            operator=self.operator,
            billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
            start_time=time(8, 0),
            end_time=time(16, 0),
            break_hours=Decimal('1.00'),
            hourly_rate=Decimal('2000.00'),
            created_by=self.owner_user
        )
        self.assertEqual(
            AuditLog.objects.filter(entity_type='MachineWorkEntry', entity_id=str(entry.id), action=AuditLog.ACTION_CREATE).count(),
            1
        )

        # UPDATE
        WorkService.update_work_entry(
            entry=entry,
            work_date=date.today(),
            machine=self.harvester,
            customer=self.customer,
            operator=self.operator,
            billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
            start_time=time(8, 0),
            end_time=time(17, 0), # +1 hr
            break_hours=Decimal('1.00'),
            hourly_rate=Decimal('2000.00'),
            user=self.manager_user
        )
        self.assertEqual(
            AuditLog.objects.filter(entity_type='MachineWorkEntry', entity_id=str(entry.id), action=AuditLog.ACTION_UPDATE).count(),
            1
        )

        # SOFT_DELETE
        WorkService.soft_delete_work_entry(entry, user=self.owner_user)
        self.assertEqual(
            AuditLog.objects.filter(entity_type='MachineWorkEntry', entity_id=str(entry.id), action=AuditLog.ACTION_SOFT_DELETE).count(),
            1
        )
        entry.refresh_from_db()
        self.assertTrue(entry.is_deleted)

    # --------------------------------------------------------------------------
    # 16. LEDGER ISOLATION GUARANTEE
    # --------------------------------------------------------------------------
    def test_ledger_isolation_guarantee(self):
        """
        Creating, modifying, and deleting a MachineWorkEntry must produce:
        0 AccountTransaction
        0 Expense
        0 Receivable
        0 Payable
        0 Balance mutations on Account
        """
        txn_count_before = AccountTransaction.objects.count()
        exp_count_before = Expense.objects.count()
        rcv_count_before = Receivable.objects.count()
        pay_count_before = Payable.objects.count()
        self.account.refresh_from_db()
        bal_before = self.account.current_balance

        # Create Work Entry
        entry = WorkService.create_work_entry(
            work_date=date.today(),
            machine=self.harvester,
            customer=self.customer,
            operator=self.operator,
            billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
            start_time=time(8, 0),
            end_time=time(17, 30),
            break_hours=Decimal('1.50'),
            hourly_rate=Decimal('2400.00'),
            start_meter=Decimal('450.00'),
            end_meter=Decimal('458.50'),
            created_by=self.owner_user
        )

        # Update Work Entry
        WorkService.update_work_entry(
            entry=entry,
            work_date=date.today(),
            machine=self.harvester,
            customer=self.customer,
            operator=self.operator,
            billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
            start_time=time(8, 0),
            end_time=time(18, 0),
            break_hours=Decimal('1.00'),
            hourly_rate=Decimal('2400.00'),
            start_meter=Decimal('450.00'),
            end_meter=Decimal('459.00'),
            user=self.owner_user
        )

        # Delete Work Entry
        WorkService.soft_delete_work_entry(entry, user=self.owner_user)

        # Assert zero mutations on financial ledger
        self.assertEqual(AccountTransaction.objects.count(), txn_count_before)
        self.assertEqual(Expense.objects.count(), exp_count_before)
        self.assertEqual(Receivable.objects.count(), rcv_count_before)
        self.assertEqual(Payable.objects.count(), pay_count_before)

        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, bal_before)
