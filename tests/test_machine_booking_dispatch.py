import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.machines.models import Machine, MachineType, MachineBooking, MachineWorkEntry
from apps.employees.models import Employee, EmployeePayment
from apps.finance.models import Customer, Account, AccountTransaction, Receivable, Payable
from apps.expenses.models import Expense
from apps.audit.models import AuditLog
from apps.machines.services.booking_service import BookingService
from apps.machines.services.work_service import WorkService


class MachineBookingDispatchWorkflowTests(TestCase):
    """
    Phase 12.5 Comprehensive Test Suite:
    Machine Booking, Availability, Operator Assignment, Dispatch Lifecycle,
    and Phase 12.4 Work Entry Integration.
    """

    def setUp(self):
        # 1. Setup RBAC Users
        self.owner = User.objects.create_user(username='b_owner', password='password123')
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.manager = User.objects.create_user(username='b_manager', password='password123')
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.accountant = User.objects.create_user(username='b_accountant', password='password123')
        self.accountant.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant.profile.save()

        self.employee = User.objects.create_user(username='b_employee', password='password123')
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        # 2. Master Data
        self.customer = Customer.objects.create(
            customer_code='CUST-TEST-01',
            name='Ramesh Patel',
            phone='9876543210',
            status=Customer.STATUS_ACTIVE
        )

        self.tractor_type = MachineType.objects.create(name='Tractor', code='TRACTOR')
        self.harvester_type = MachineType.objects.create(name='Combine Harvester', code='HARVESTER')

        self.tractor = Machine.objects.create(
            machine_code='TRAC-01',
            name='Mahindra 575 DI',
            machine_type=self.tractor_type,
            status=Machine.STATUS_ACTIVE,
            current_meter_reading=Decimal('1200.00'),
            is_active=True
        )

        self.harvester = Machine.objects.create(
            machine_code='HARV-01',
            name='Preet 987 Harvester',
            machine_type=self.harvester_type,
            status=Machine.STATUS_ACTIVE,
            current_meter_reading=Decimal('450.00'),
            is_active=True
        )

        self.tractor_driver = Employee.objects.create(
            employee_code='EMP-TRAC-01',
            full_name='Narayan Reddy',
            role=Employee.ROLE_TRACTOR_DRIVER,
            status=Employee.STATUS_ACTIVE
        )

        self.harvester_operator = Employee.objects.create(
            employee_code='EMP-HARV-01',
            full_name='Suresh Kumar',
            role=Employee.ROLE_HARVESTER_OPERATOR,
            status=Employee.STATUS_ACTIVE
        )

        self.inactive_operator = Employee.objects.create(
            employee_code='EMP-INACT-01',
            full_name='Vikram Singh',
            role=Employee.ROLE_TRACTOR_DRIVER,
            status=Employee.STATUS_INACTIVE
        )

        self.leave_operator = Employee.objects.create(
            employee_code='EMP-LEAVE-01',
            full_name='Anil Sharma',
            role=Employee.ROLE_HARVESTER_OPERATOR,
            status=Employee.STATUS_ON_LEAVE
        )

        self.shop_staff = Employee.objects.create(
            employee_code='EMP-SHOP-01',
            full_name='Manoj Verma',
            role=Employee.ROLE_SHOP_STAFF,
            status=Employee.STATUS_ACTIVE
        )

        self.today = timezone.now().date()
        self.client = Client()

    # --------------------------------------------------------------------------
    # 1. Booking Creation Tests
    # --------------------------------------------------------------------------
    def test_tractor_booking_creation(self):
        """1. Verify creation of a tractor acre-based booking."""
        booking = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            expected_quantity=Decimal('15.50'),
            village='Kothur',
            crop_description='Paddy Tillage',
            created_by=self.owner
        )
        self.assertTrue(booking.booking_code.startswith('BKG-'))
        self.assertEqual(booking.status, MachineBooking.STATUS_PENDING)
        self.assertEqual(booking.expected_quantity, Decimal('15.50'))
        self.assertEqual(booking.customer, self.customer)

    def test_harvester_booking_creation(self):
        """2. Verify creation of a harvester time-based hourly booking."""
        booking = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.harvester_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_TIME_HOURLY,
            requested_start_time=datetime.time(8, 0),
            expected_duration_hours=Decimal('8.00'),
            village='Nandigama',
            crop_description='Paddy Harvesting',
            created_by=self.manager
        )
        self.assertEqual(booking.status, MachineBooking.STATUS_PENDING)
        self.assertEqual(booking.requested_start_time, datetime.time(8, 0))
        self.assertEqual(booking.expected_duration_hours, Decimal('8.00'))

    # --------------------------------------------------------------------------
    # 2. Machine Availability & Assignment Tests
    # --------------------------------------------------------------------------
    def test_machine_availability_detection(self):
        """3. Verify get_available_machines filters correctly."""
        available = BookingService.get_available_machines(self.tractor_type, self.today)
        self.assertIn(self.tractor, available)

    def test_prevent_overlapping_machine_bookings(self):
        """4. Prevent assigning a machine on the same work_date if already active."""
        # Booking 1 confirmed with tractor
        b1 = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            machine=self.tractor,
            operator=self.tractor_driver,
            created_by=self.owner
        )
        BookingService.confirm_booking(b1, self.owner)

        # Booking 2 on same date attempting to assign same tractor
        b2 = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            created_by=self.owner
        )
        with self.assertRaises(ValidationError) as ctx:
            BookingService.confirm_booking(b2, self.owner, machine=self.tractor, operator=self.tractor_driver)
        self.assertIn('already assigned to active booking', str(ctx.exception))

    def test_prevent_maintenance_machine_dispatch(self):
        """5. Prevent assigning or dispatching a machine under maintenance."""
        self.tractor.status = Machine.STATUS_UNDER_MAINTENANCE
        self.tractor.save()

        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            created_by=self.owner
        )
        with self.assertRaises(ValidationError) as ctx:
            BookingService.confirm_booking(b, self.owner, machine=self.tractor, operator=self.tractor_driver)
        self.assertIn('UNDER MAINTENANCE', str(ctx.exception))

    def test_prevent_decommissioned_machine_dispatch(self):
        """6. Prevent assigning or dispatching a decommissioned machine."""
        self.harvester.status = Machine.STATUS_DECOMMISSIONED
        self.harvester.save()

        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.harvester_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_TIME_HOURLY,
            created_by=self.owner
        )
        with self.assertRaises(ValidationError) as ctx:
            BookingService.confirm_booking(b, self.owner, machine=self.harvester, operator=self.harvester_operator)
        self.assertIn('DECOMMISSIONED', str(ctx.exception))

    # --------------------------------------------------------------------------
    # 3. Operator Validation Tests
    # --------------------------------------------------------------------------
    def test_assign_compatible_tractor_driver(self):
        """7. Compatible tractor driver assignment succeeds."""
        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            machine=self.tractor,
            operator=self.tractor_driver,
            created_by=self.owner
        )
        self.assertEqual(b.operator, self.tractor_driver)

    def test_assign_compatible_harvester_operator(self):
        """8. Compatible harvester operator assignment succeeds."""
        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.harvester_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_TIME_HOURLY,
            machine=self.harvester,
            operator=self.harvester_operator,
            created_by=self.owner
        )
        self.assertEqual(b.operator, self.harvester_operator)

    def test_reject_inactive_operator(self):
        """9. Inactive operator is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            BookingService.validate_operator(self.inactive_operator, self.tractor_type)
        self.assertIn('INACTIVE', str(ctx.exception))

    def test_reject_on_leave_operator(self):
        """10. On-leave operator is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            BookingService.validate_operator(self.leave_operator, self.harvester_type)
        self.assertIn('ON LEAVE', str(ctx.exception))

    def test_reject_unrelated_role_operator(self):
        """Verify shop staff / non-operator roles are rejected for machines."""
        with self.assertRaises(ValidationError) as ctx:
            BookingService.validate_operator(self.shop_staff, self.tractor_type)
        self.assertIn('not authorized', str(ctx.exception))

    # --------------------------------------------------------------------------
    # 4. Lifecycle Transitions Tests
    # --------------------------------------------------------------------------
    def test_confirm_booking_transition(self):
        """11. Confirm booking state transition PENDING -> CONFIRMED."""
        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            created_by=self.owner
        )
        self.assertEqual(b.status, MachineBooking.STATUS_PENDING)

        confirmed = BookingService.confirm_booking(b, self.owner, machine=self.tractor, operator=self.tractor_driver)
        self.assertEqual(confirmed.status, MachineBooking.STATUS_CONFIRMED)
        self.assertEqual(confirmed.machine, self.tractor)
        self.assertEqual(confirmed.operator, self.tractor_driver)

    def test_dispatch_booking_transition(self):
        """12. Dispatch booking state transition CONFIRMED -> DISPATCHED."""
        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            machine=self.tractor,
            operator=self.tractor_driver,
            created_by=self.owner
        )
        BookingService.confirm_booking(b, self.owner)
        dispatched = BookingService.dispatch_booking(b, self.owner, dispatch_notes='Route via Highway 44')

        self.assertEqual(dispatched.status, MachineBooking.STATUS_DISPATCHED)
        self.assertIsNotNone(dispatched.dispatched_at)
        self.assertEqual(dispatched.dispatch_notes, 'Route via Highway 44')

    def test_start_work_transition(self):
        """13. Start work transition DISPATCHED -> IN_PROGRESS."""
        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.harvester_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_TIME_HOURLY,
            machine=self.harvester,
            operator=self.harvester_operator,
            created_by=self.owner
        )
        BookingService.confirm_booking(b, self.owner)
        BookingService.dispatch_booking(b, self.owner)
        started = BookingService.start_work(b, self.owner)

        self.assertEqual(started.status, MachineBooking.STATUS_IN_PROGRESS)
        self.assertIsNotNone(started.started_at)

    def test_complete_work_transition(self):
        """14. Complete work transition IN_PROGRESS -> COMPLETED."""
        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.harvester_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_TIME_HOURLY,
            machine=self.harvester,
            operator=self.harvester_operator,
            created_by=self.owner
        )
        BookingService.confirm_booking(b, self.owner)
        BookingService.dispatch_booking(b, self.owner)
        BookingService.start_work(b, self.owner)
        completed = BookingService.complete_work(b, self.owner)

        self.assertEqual(completed.status, MachineBooking.STATUS_COMPLETED)
        self.assertIsNotNone(completed.completed_at)

    def test_cancel_booking_transition(self):
        """15. Cancel booking transition."""
        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            created_by=self.owner
        )
        cancelled = BookingService.cancel_booking(b, self.owner, cancellation_reason='Heavy rain forecast')
        self.assertEqual(cancelled.status, MachineBooking.STATUS_CANCELLED)
        self.assertEqual(cancelled.cancellation_reason, 'Heavy rain forecast')

        # Cannot cancel completed booking
        b2 = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            machine=self.tractor,
            operator=self.tractor_driver,
            created_by=self.owner
        )
        BookingService.confirm_booking(b2, self.owner)
        BookingService.dispatch_booking(b2, self.owner)
        BookingService.start_work(b2, self.owner)
        BookingService.complete_work(b2, self.owner)

        with self.assertRaises(ValidationError):
            BookingService.cancel_booking(b2, self.owner)

    def test_invalid_lifecycle_transition(self):
        """Verify skipping state machine transitions is blocked."""
        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            created_by=self.owner
        )
        # Cannot dispatch pending booking directly without confirmation
        with self.assertRaises(ValidationError):
            BookingService.dispatch_booking(b, self.owner)

        # Cannot start un-dispatched booking
        with self.assertRaises(ValidationError):
            BookingService.start_work(b, self.owner)

    # --------------------------------------------------------------------------
    # 5. Booking -> Phase 12.4 Work Entry Link Tests
    # --------------------------------------------------------------------------
    def test_booking_links_to_work_entry(self):
        """16. Verify Phase 12.4 MachineWorkEntry links to MachineBooking."""
        booking = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.harvester_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_TIME_HOURLY,
            machine=self.harvester,
            operator=self.harvester_operator,
            created_by=self.owner
        )
        BookingService.confirm_booking(booking, self.owner)
        BookingService.dispatch_booking(booking, self.owner)
        BookingService.start_work(booking, self.owner)
        BookingService.complete_work(booking, self.owner)

        entry = WorkService.create_work_entry(
            work_date=self.today,
            machine=self.harvester,
            customer=self.customer,
            operator=self.harvester_operator,
            booking=booking,
            billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(17, 30),
            break_hours=Decimal('1.50'),
            hourly_rate=Decimal('2400.00'),
            start_meter=Decimal('450.00'),
            end_meter=Decimal('458.50'),
            created_by=self.owner
        )
        self.assertEqual(entry.booking, booking)
        self.assertIn(entry, booking.work_entries.all())

    def test_harvester_workflow_remains_time_based(self):
        """17. Verify Harvester calculation formula remains authoritative: (9.5 - 1.5) * 2400 = 19200."""
        calc = WorkService.calculate_harvester_billing(
            start_time=datetime.time(8, 0),
            end_time=datetime.time(17, 30),
            break_hours=Decimal('1.50'),
            hourly_rate=Decimal('2400.00')
        )
        self.assertEqual(calc['elapsed_hours'], Decimal('9.50'))
        self.assertEqual(calc['net_working_hours'], Decimal('8.00'))
        self.assertEqual(calc['total_amount'], Decimal('19200.00'))

    def test_tractor_workflow_remains_acre_piece_based(self):
        """18. Verify Tractor calculation formula remains authoritative: 15.5 * 1200 = 18600."""
        calc = WorkService.calculate_tractor_billing(
            quantity=Decimal('15.50'),
            unit_rate=Decimal('1200.00')
        )
        self.assertEqual(calc['total_amount'], Decimal('18600.00'))

    def test_meter_tracking_remains_independent(self):
        """19. Machine meter tracking (450 -> 458.5 = 8.5) does not alter commercial billing."""
        entry = WorkService.create_work_entry(
            work_date=self.today,
            machine=self.harvester,
            customer=self.customer,
            operator=self.harvester_operator,
            billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(17, 30),
            break_hours=Decimal('1.50'),
            hourly_rate=Decimal('2400.00'),
            start_meter=Decimal('450.00'),
            end_meter=Decimal('458.50'),
            created_by=self.owner
        )
        self.assertEqual(entry.meter_difference, Decimal('8.50'))
        self.assertEqual(entry.total_amount, Decimal('19200.00'))

    # --------------------------------------------------------------------------
    # 6. RBAC, Audit Logging, and Financial Ledger Isolation
    # --------------------------------------------------------------------------
    def test_rbac_access_control(self):
        """20. Test RBAC permissions on booking and dispatch views."""
        # 1. Owner can access list, create, and dispatch
        self.client.force_login(self.owner)
        resp = self.client.get('/machines/bookings/')
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get('/machines/dispatch/')
        self.assertEqual(resp.status_code, 200)

        # 2. Manager can access list, create, and dispatch
        self.client.force_login(self.manager)
        resp = self.client.get('/machines/bookings/add/')
        self.assertEqual(resp.status_code, 200)

        # 3. Accountant can view list and dispatch board AND create bookings
        self.client.force_login(self.accountant)
        resp = self.client.get('/machines/bookings/')
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get('/machines/bookings/add/')
        self.assertEqual(resp.status_code, 200)

        # 4. Employee is forbidden from viewing bookings
        self.client.force_login(self.employee)
        resp = self.client.get('/machines/bookings/')
        self.assertEqual(resp.status_code, 403)

    def test_audit_logging_lifecycle(self):
        """21. Verify AuditLog records across booking lifecycle."""
        initial_count = AuditLog.objects.filter(entity_type='MachineBooking').count()

        booking = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            created_by=self.owner
        )
        BookingService.confirm_booking(booking, self.owner, machine=self.tractor, operator=self.tractor_driver)
        BookingService.dispatch_booking(booking, self.owner, dispatch_notes='Dispatched')
        BookingService.start_work(booking, self.owner)
        BookingService.complete_work(booking, self.owner)
        BookingService.soft_delete_booking(booking, self.owner)

        final_count = AuditLog.objects.filter(entity_type='MachineBooking').count()
        self.assertEqual(final_count - initial_count, 6)

    def test_financial_ledger_isolation(self):
        """22. Verify booking and dispatch workflow generates ZERO financial transactions."""
        initial_transactions = AccountTransaction.objects.count()
        initial_expenses = Expense.objects.count()
        initial_receivables = Receivable.objects.count()
        initial_payables = Payable.objects.count()
        initial_wages = EmployeePayment.objects.count()

        # Run complete booking, dispatch, and work completion flow
        b = BookingService.create_booking(
            customer=self.customer,
            machine_type=self.tractor_type,
            work_date=self.today,
            billing_type=MachineBooking.BILLING_ACRE,
            expected_quantity=Decimal('20.00'),
            created_by=self.owner
        )
        BookingService.confirm_booking(b, self.owner, machine=self.tractor, operator=self.tractor_driver)
        BookingService.dispatch_booking(b, self.owner)
        BookingService.start_work(b, self.owner)
        BookingService.complete_work(b, self.owner)

        # Assert no financial records were created
        self.assertEqual(AccountTransaction.objects.count(), initial_transactions)
        self.assertEqual(Expense.objects.count(), initial_expenses)
        self.assertEqual(Receivable.objects.count(), initial_receivables)
        self.assertEqual(Payable.objects.count(), initial_payables)
        self.assertEqual(EmployeePayment.objects.count(), initial_wages)
