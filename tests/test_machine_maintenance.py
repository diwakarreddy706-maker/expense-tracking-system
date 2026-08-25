import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from apps.accounts.models import UserProfile
from apps.machines.models import (
    Machine, MachineType, MachineBooking,
    MachineMaintenanceSchedule, MaintenanceJob, MaintenancePartUsage
)
from apps.machines.services.maintenance_service import MaintenanceService
from apps.machines.services.booking_service import BookingService
from apps.finance.models import Supplier, Account, Customer
from apps.expenses.models import Expense, ExpenseCategory
from apps.audit.models import AuditLog


class MachineMaintenanceBaseTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Users & Profiles
        self.owner_user = User.objects.create_user(username='owner_user', password='password123')
        self.owner_user.profile.role = UserProfile.ROLE_OWNER
        self.owner_user.profile.save()

        self.manager_user = User.objects.create_user(username='manager_user', password='password123')
        self.manager_user.profile.role = UserProfile.ROLE_MANAGER
        self.manager_user.profile.save()

        self.accountant_user = User.objects.create_user(username='accountant_user', password='password123')
        self.accountant_user.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant_user.profile.save()

        # Machine Type & Machines
        self.harvester_type = MachineType.objects.create(name='Harvester', code='HARVESTER')
        self.tractor_type = MachineType.objects.create(name='Tractor', code='TRACTOR')

        self.harvester = Machine.objects.create(
            machine_code='MCH-HARV-01',
            name='Claas Crop Tiger 40',
            machine_type=self.harvester_type,
            registration_no='MH-12-AB-1234',
            status=Machine.STATUS_ACTIVE,
            current_meter_reading=Decimal('500.00'),
            meter_unit=Machine.METER_HOURS
        )

        self.tractor = Machine.objects.create(
            machine_code='MCH-TRAC-01',
            name='John Deere 5310',
            machine_type=self.tractor_type,
            registration_no='MH-12-CD-5678',
            status=Machine.STATUS_ACTIVE,
            current_meter_reading=Decimal('1200.00'),
            meter_unit=Machine.METER_HOURS
        )

        self.decommissioned_machine = Machine.objects.create(
            machine_code='MCH-OLD-99',
            name='Old Ford 3600',
            machine_type=self.tractor_type,
            registration_no='MH-12-XX-9999',
            status=Machine.STATUS_DECOMMISSIONED,
            current_meter_reading=Decimal('9000.00'),
            meter_unit=Machine.METER_HOURS
        )

        # Supplier (Spare parts & Workshop)
        self.parts_supplier = Supplier.objects.create(
            supplier_code='SUPP-PARTS-01',
            name='Kisan Tractor Spares',
            supplier_type=Supplier.TYPE_SPARE_PARTS,
            phone='9876543210',
            status=Supplier.STATUS_ACTIVE
        )
        self.workshop_supplier = Supplier.objects.create(
            supplier_code='SUPP-WORK-01',
            name='Guru Kripa Diesel Works',
            supplier_type=Supplier.TYPE_WORKSHOP,
            phone='9876543211',
            status=Supplier.STATUS_ACTIVE
        )

        # Account & Expense Category
        self.cash_account = Account.objects.create(
            account_name='Main Cash Drawer',
            account_type=Account.TYPE_CASH,
            opening_balance=Decimal('100000.00'),
            current_balance=Decimal('100000.00'),
            is_active=True
        )
        self.expense_category = ExpenseCategory.objects.create(
            name='Machinery Maintenance & Repairs',
            code='MAINTENANCE_REPAIRS',
            is_active=True
        )

        # Customer
        self.customer = Customer.objects.create(
            customer_code='CUST-TEST-01',
            name='Ramesh Patil',
            location_address='Koregaon',
            phone='9822000001',
            status=Customer.STATUS_ACTIVE
        )


# ==============================================================================
# 1. MAINTENANCE SCHEDULE MODEL & EVALUATION TESTS
# ==============================================================================

class MachineMaintenanceScheduleTests(MachineMaintenanceBaseTestCase):
    def test_create_meter_schedule(self):
        """Test creating meter-based schedule calculates next_service_meter correctly."""
        sch = MaintenanceService.create_schedule(
            machine=self.harvester,
            schedule_name='250 Hour Engine Oil Service',
            service_basis=MachineMaintenanceSchedule.BASIS_METER,
            service_interval_meter=Decimal('250.00'),
            last_service_meter=Decimal('500.00'),
            created_by=self.owner_user
        )
        self.assertEqual(sch.next_service_meter, Decimal('750.00'))
        self.assertIsNone(sch.next_service_date)
        self.assertTrue(sch.is_active)

    def test_create_date_schedule(self):
        """Test creating date-based schedule calculates next_service_date correctly."""
        today = timezone.now().date()
        sch = MaintenanceService.create_schedule(
            machine=self.tractor,
            schedule_name='Quarterly Hydraulic Inspection',
            service_basis=MachineMaintenanceSchedule.BASIS_DATE,
            service_interval_days=90,
            last_service_date=today,
            created_by=self.owner_user
        )
        expected_date = today + datetime.timedelta(days=90)
        self.assertEqual(sch.next_service_date, expected_date)
        self.assertIsNone(sch.next_service_meter)

    def test_create_both_basis_schedule(self):
        """Test creating schedule with both meter and date constraints."""
        today = timezone.now().date()
        sch = MaintenanceService.create_schedule(
            machine=self.tractor,
            schedule_name='Full Annual Overhaul',
            service_basis=MachineMaintenanceSchedule.BASIS_BOTH,
            service_interval_meter=Decimal('500.00'),
            service_interval_days=365,
            last_service_meter=Decimal('1200.00'),
            last_service_date=today,
            created_by=self.owner_user
        )
        self.assertEqual(sch.next_service_meter, Decimal('1700.00'))
        self.assertEqual(sch.next_service_date, today + datetime.timedelta(days=365))

    def test_schedule_interval_validations(self):
        """Test validation error raised if intervals are missing or negative."""
        with self.assertRaises(ValidationError):
            MaintenanceService.create_schedule(
                machine=self.harvester,
                schedule_name='Invalid Meter Schedule',
                service_basis=MachineMaintenanceSchedule.BASIS_METER,
                service_interval_meter=Decimal('0.00')
            )

        with self.assertRaises(ValidationError):
            MaintenanceService.create_schedule(
                machine=self.harvester,
                schedule_name='Invalid Date Schedule',
                service_basis=MachineMaintenanceSchedule.BASIS_DATE,
                service_interval_days=0
            )

    def test_schedule_evaluation_status_ok(self):
        """Test schedule status is OK when reading is well below next target."""
        sch = MaintenanceService.create_schedule(
            machine=self.harvester,
            schedule_name='500 Hour Service',
            service_basis=MachineMaintenanceSchedule.BASIS_METER,
            service_interval_meter=Decimal('250.00'),
            last_service_meter=Decimal('500.00'),
            warning_meter_before=Decimal('25.00')
        )
        eval_res = sch.evaluate_status()
        self.assertEqual(eval_res['status'], MachineMaintenanceSchedule.STATUS_OK)
        self.assertEqual(eval_res['remaining_meter'], Decimal('250.00'))

    def test_schedule_evaluation_status_due_soon(self):
        """Test schedule status is DUE_SOON when reading is within warning threshold."""
        self.harvester.current_meter_reading = Decimal('730.00')
        self.harvester.save()

        sch = MaintenanceService.create_schedule(
            machine=self.harvester,
            schedule_name='250 Hour Service',
            service_basis=MachineMaintenanceSchedule.BASIS_METER,
            service_interval_meter=Decimal('250.00'),
            last_service_meter=Decimal('500.00'),
            warning_meter_before=Decimal('25.00')
        )
        eval_res = sch.evaluate_status()
        self.assertEqual(eval_res['status'], MachineMaintenanceSchedule.STATUS_DUE_SOON)
        self.assertEqual(eval_res['remaining_meter'], Decimal('20.00'))

    def test_schedule_evaluation_status_due_exact(self):
        """Test schedule status is DUE when reading matches next target exactly."""
        self.harvester.current_meter_reading = Decimal('750.00')
        self.harvester.save()

        sch = MaintenanceService.create_schedule(
            machine=self.harvester,
            schedule_name='250 Hour Service',
            service_basis=MachineMaintenanceSchedule.BASIS_METER,
            service_interval_meter=Decimal('250.00'),
            last_service_meter=Decimal('500.00')
        )
        eval_res = sch.evaluate_status()
        self.assertEqual(eval_res['status'], MachineMaintenanceSchedule.STATUS_DUE)
        self.assertEqual(eval_res['remaining_meter'], Decimal('0.00'))

    def test_schedule_evaluation_status_overdue_meter(self):
        """Test schedule status is OVERDUE when reading exceeds target."""
        self.harvester.current_meter_reading = Decimal('760.00')
        self.harvester.save()

        sch = MaintenanceService.create_schedule(
            machine=self.harvester,
            schedule_name='250 Hour Service',
            service_basis=MachineMaintenanceSchedule.BASIS_METER,
            service_interval_meter=Decimal('250.00'),
            last_service_meter=Decimal('500.00')
        )
        eval_res = sch.evaluate_status()
        self.assertEqual(eval_res['status'], MachineMaintenanceSchedule.STATUS_OVERDUE)
        self.assertEqual(eval_res['remaining_meter'], Decimal('-10.00'))

    def test_schedule_evaluation_status_overdue_date(self):
        """Test date-based schedule evaluation when date is in the past."""
        past_date = timezone.now().date() - datetime.timedelta(days=10)
        sch = MachineMaintenanceSchedule.objects.create(
            machine=self.tractor,
            schedule_name='Old Service',
            service_basis=MachineMaintenanceSchedule.BASIS_DATE,
            service_interval_days=30,
            next_service_date=past_date,
            is_active=True
        )
        eval_res = sch.evaluate_status()
        self.assertEqual(eval_res['status'], MachineMaintenanceSchedule.STATUS_OVERDUE)
        self.assertEqual(eval_res['remaining_days'], -10)

    def test_inactive_schedule_evaluation(self):
        """Test evaluation of an inactive schedule."""
        sch = MachineMaintenanceSchedule.objects.create(
            machine=self.tractor,
            schedule_name='Inactive Service',
            service_basis=MachineMaintenanceSchedule.BASIS_DATE,
            service_interval_days=30,
            is_active=False
        )
        eval_res = sch.evaluate_status()
        self.assertEqual(eval_res['status'], 'INACTIVE')

    def test_update_schedule_recalculates_targets(self):
        """Test updating a schedule recalculates next metrics properly."""
        sch = MaintenanceService.create_schedule(
            machine=self.harvester,
            schedule_name='Service A',
            service_basis=MachineMaintenanceSchedule.BASIS_METER,
            service_interval_meter=Decimal('100.00'),
            last_service_meter=Decimal('500.00')
        )
        self.assertEqual(sch.next_service_meter, Decimal('600.00'))

        # Update interval to 200
        updated = MaintenanceService.update_schedule(
            schedule=sch,
            schedule_name='Service A (Updated)',
            service_basis=MachineMaintenanceSchedule.BASIS_METER,
            service_interval_meter=Decimal('200.00'),
            last_service_meter=Decimal('500.00'),
            user=self.owner_user
        )
        self.assertEqual(updated.next_service_meter, Decimal('700.00'))


# ==============================================================================
# 2. MAINTENANCE JOB LIFECYCLE & WORKSHOP TESTS
# ==============================================================================

class MaintenanceJobLifecycleTests(MachineMaintenanceBaseTestCase):
    def test_create_preventive_maintenance_job(self):
        """Test creating a preventive maintenance job."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Periodic 500h oil and filter change',
            reported_date=timezone.now().date(),
            meter_reading=Decimal('500.00'),
            labor_cost=Decimal('1500.00'),
            created_by=self.owner_user
        )
        self.assertTrue(job.maintenance_code.startswith('MNT-'))
        self.assertEqual(job.status, MaintenanceJob.STATUS_OPEN)
        self.assertEqual(job.parts_cost, Decimal('0.00'))
        self.assertEqual(job.labor_cost, Decimal('1500.00'))
        self.assertEqual(job.total_maintenance_cost, Decimal('1500.00'))
        self.assertEqual(self.harvester.status, Machine.STATUS_ACTIVE)

    def test_create_corrective_maintenance_job(self):
        """Test creating corrective maintenance job."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.tractor,
            maintenance_type=MaintenanceJob.TYPE_CORRECTIVE_REPAIR,
            problem_description='Hydraulic lift arm vibrating abnormally',
            labor_cost=Decimal('800.00'),
            created_by=self.manager_user
        )
        self.assertEqual(job.maintenance_type, MaintenanceJob.TYPE_CORRECTIVE_REPAIR)
        self.assertEqual(job.status, MaintenanceJob.STATUS_OPEN)

    def test_create_breakdown_job_with_stopped_machine(self):
        """Test creating a breakdown job with machine_stopped=True sets machine to UNDER_MAINTENANCE."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.tractor,
            maintenance_type=MaintenanceJob.TYPE_BREAKDOWN_REPAIR,
            problem_description='Hydraulic pump failure in field',
            breakdown_location='Farm Plot #12',
            breakdown_time=timezone.now(),
            machine_stopped=True,
            severity=MaintenanceJob.SEVERITY_HIGH,
            created_by=self.owner_user
        )
        self.assertEqual(job.status, MaintenanceJob.STATUS_OPEN)
        self.assertTrue(job.machine_stopped)
        self.tractor.refresh_from_db()
        self.assertEqual(self.tractor.status, Machine.STATUS_UNDER_MAINTENANCE)

    def test_create_job_code_sequence(self):
        """Test sequential maintenance code generation."""
        job1 = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Job 1'
        )
        job2 = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Job 2'
        )
        seq1 = int(job1.maintenance_code.split('-')[-1])
        seq2 = int(job2.maintenance_code.split('-')[-1])
        self.assertEqual(seq2, seq1 + 1)

    def test_create_job_negative_meter_fails(self):
        """Test creating job with negative meter reading raises ValidationError."""
        with self.assertRaises(ValidationError):
            MaintenanceService.create_maintenance_job(
                machine=self.harvester,
                maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
                problem_description='Test',
                meter_reading=Decimal('-50.00')
            )

    def test_create_job_negative_costs_fail(self):
        """Test creating job with negative cost values raises ValidationError."""
        with self.assertRaises(ValidationError):
            MaintenanceService.create_maintenance_job(
                machine=self.harvester,
                maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
                problem_description='Test',
                labor_cost=Decimal('-100.00')
            )

    def test_start_maintenance_job(self):
        """Test starting a job sets status IN_REPAIR and marks machine UNDER_MAINTENANCE."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='General servicing',
            machine_stopped=False,
            created_by=self.owner_user
        )
        self.harvester.refresh_from_db()
        self.assertEqual(self.harvester.status, Machine.STATUS_ACTIVE)

        started = MaintenanceService.start_maintenance_job(
            job=job,
            user=self.manager_user,
            diagnosis='Replacing oil and fuel filter'
        )
        self.assertEqual(started.status, MaintenanceJob.STATUS_IN_REPAIR)
        self.assertIsNotNone(started.started_date)
        self.harvester.refresh_from_db()
        self.assertEqual(self.harvester.status, Machine.STATUS_UNDER_MAINTENANCE)

    def test_under_maintenance_blocks_booking_availability(self):
        """Test that machine with UNDER_MAINTENANCE status is excluded from booking availability."""
        self.tractor.status = Machine.STATUS_UNDER_MAINTENANCE
        self.tractor.save()

        avail_machines = BookingService.get_available_machines(
            machine_type=self.tractor_type,
            work_date=timezone.now().date()
        )
        self.assertNotIn(self.tractor, avail_machines)

        # Booking validation should fail
        with self.assertRaises(ValidationError):
            BookingService.validate_machine_availability(
                machine=self.tractor,
                work_date=timezone.now().date()
            )

    def test_is_active_blocking_property(self):
        """Test is_active_blocking helper property on MaintenanceJob."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Test'
        )
        self.assertFalse(job.is_active_blocking)

        job.machine_stopped = True
        self.assertTrue(job.is_active_blocking)

        job.machine_stopped = False
        job.status = MaintenanceJob.STATUS_IN_REPAIR
        self.assertTrue(job.is_active_blocking)

        job.status = MaintenanceJob.STATUS_COMPLETED
        self.assertFalse(job.is_active_blocking)


# ==============================================================================
# 3. SPARE PARTS & COST AGGREGATION TESTS
# ==============================================================================

class MaintenanceCostAndPartsTests(MachineMaintenanceBaseTestCase):
    def setUp(self):
        super().setUp()
        self.job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Engine overhaul and filter replacements',
            labor_cost=Decimal('2000.00'),
            external_service_cost=Decimal('500.00'),
            other_cost=Decimal('100.00'),
            created_by=self.owner_user
        )

    def test_add_spare_parts_updates_job_totals(self):
        """Test adding spare parts calculates quantity * unit_cost and updates parent job."""
        part1 = MaintenanceService.add_part_usage(
            job=self.job,
            part_name='Engine Oil 15W40 (10L)',
            quantity=Decimal('2.00'),
            unit_cost=Decimal('1850.00'),
            part_number='OIL-15W40-10L',
            supplier=self.parts_supplier,
            user=self.manager_user
        )
        self.assertEqual(part1.total_cost, Decimal('3700.00'))

        part2 = MaintenanceService.add_part_usage(
            job=self.job,
            part_name='Oil Filter Cartridge',
            quantity=Decimal('1.00'),
            unit_cost=Decimal('650.00'),
            part_number='FLT-OIL-40',
            supplier=self.parts_supplier,
            user=self.manager_user
        )
        self.assertEqual(part2.total_cost, Decimal('650.00'))

        self.job.refresh_from_db()
        self.assertEqual(self.job.parts_cost, Decimal('4350.00'))
        self.assertEqual(self.job.total_maintenance_cost, Decimal('6950.00'))

    def test_add_part_invalid_quantity_or_cost_fails(self):
        """Test adding part with <= 0 quantity or negative cost fails."""
        with self.assertRaises(ValidationError):
            MaintenanceService.add_part_usage(
                job=self.job,
                part_name='Test Part',
                quantity=Decimal('0.00'),
                unit_cost=Decimal('100.00')
            )

        with self.assertRaises(ValidationError):
            MaintenanceService.add_part_usage(
                job=self.job,
                part_name='Test Part',
                quantity=Decimal('1.00'),
                unit_cost=Decimal('-10.00')
            )

    def test_update_spare_part_recalculates_job(self):
        """Test modifying a spare part item updates job total."""
        part = MaintenanceService.add_part_usage(
            job=self.job,
            part_name='Hydraulic Hose 1/2 inch',
            quantity=Decimal('1.00'),
            unit_cost=Decimal('1200.00'),
            user=self.manager_user
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.parts_cost, Decimal('1200.00'))

        # Update quantity to 3
        MaintenanceService.update_part_usage(
            part=part,
            quantity=Decimal('3.00'),
            unit_cost=Decimal('1200.00'),
            user=self.manager_user
        )
        part.refresh_from_db()
        self.assertEqual(part.total_cost, Decimal('3600.00'))

        self.job.refresh_from_db()
        self.assertEqual(self.job.parts_cost, Decimal('3600.00'))
        self.assertEqual(self.job.total_maintenance_cost, Decimal('6200.00'))

    def test_delete_spare_part_recalculates_job(self):
        """Test deleting a spare part item reduces job total."""
        part = MaintenanceService.add_part_usage(
            job=self.job,
            part_name='Hydraulic Hose',
            quantity=Decimal('2.00'),
            unit_cost=Decimal('1000.00'),
            user=self.manager_user
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.parts_cost, Decimal('2000.00'))

        MaintenanceService.delete_part_usage(part, user=self.manager_user)
        self.job.refresh_from_db()
        self.assertEqual(self.job.parts_cost, Decimal('0.00'))
        self.assertEqual(self.job.total_maintenance_cost, Decimal('2600.00'))

    def test_cannot_modify_parts_on_completed_job(self):
        """Test adding or deleting parts on a COMPLETED job raises ValidationError."""
        MaintenanceService.complete_maintenance_job(
            job=self.job,
            user=self.owner_user,
            work_performed='Replaced parts and tested equipment'
        )
        self.assertEqual(self.job.status, MaintenanceJob.STATUS_COMPLETED)

        with self.assertRaises(ValidationError):
            MaintenanceService.add_part_usage(
                job=self.job,
                part_name='Extra Belt',
                quantity=Decimal('1.00'),
                unit_cost=Decimal('500.00'),
                user=self.manager_user
            )


# ==============================================================================
# 4. MAINTENANCE COMPLETION & SCHEDULE ADVANCEMENT TESTS
# ==============================================================================

class MaintenanceCompletionTests(MachineMaintenanceBaseTestCase):
    def setUp(self):
        super().setUp()
        self.sch = MaintenanceService.create_schedule(
            machine=self.harvester,
            schedule_name='250h Engine Service',
            service_basis=MachineMaintenanceSchedule.BASIS_METER,
            service_interval_meter=Decimal('250.00'),
            last_service_meter=Decimal('250.00')
        )
        self.job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            maintenance_schedule=self.sch,
            problem_description='500h Engine Service',
            meter_reading=Decimal('505.00'),
            machine_stopped=True,
            created_by=self.owner_user
        )

    def test_complete_job_advances_schedule(self):
        """Test completing maintenance job advances schedule last and next service metrics."""
        self.harvester.refresh_from_db()
        self.assertEqual(self.harvester.status, Machine.STATUS_UNDER_MAINTENANCE)

        comp = MaintenanceService.complete_maintenance_job(
            job=self.job,
            user=self.owner_user,
            completed_date=timezone.now(),
            meter_reading=Decimal('505.00'),
            work_performed='Replaced engine oil, filter, and fan belt.',
            labor_cost=Decimal('1500.00')
        )
        self.assertEqual(comp.status, MaintenanceJob.STATUS_COMPLETED)
        self.harvester.refresh_from_db()
        self.assertEqual(self.harvester.status, Machine.STATUS_ACTIVE)
        self.assertEqual(self.harvester.current_meter_reading, Decimal('505.00'))

        # Schedule should be advanced
        self.sch.refresh_from_db()
        self.assertEqual(self.sch.last_service_meter, Decimal('505.00'))
        self.assertEqual(self.sch.next_service_meter, Decimal('755.00'))
        self.assertEqual(comp.next_service_meter, Decimal('755.00'))

    def test_complete_job_with_other_blocking_jobs_keeps_machine_under_maintenance(self):
        """Test that if another open blocking repair exists, machine stays UNDER_MAINTENANCE."""
        job2 = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_BREAKDOWN_REPAIR,
            problem_description='Cutter bar jammed',
            machine_stopped=True,
            created_by=self.owner_user
        )
        self.harvester.refresh_from_db()
        self.assertEqual(self.harvester.status, Machine.STATUS_UNDER_MAINTENANCE)

        # Complete first job
        MaintenanceService.complete_maintenance_job(
            job=self.job,
            user=self.owner_user,
            work_performed='Oil change finished'
        )
        self.harvester.refresh_from_db()
        self.assertEqual(self.harvester.status, Machine.STATUS_UNDER_MAINTENANCE)

        # Complete second job
        MaintenanceService.complete_maintenance_job(
            job=job2,
            user=self.owner_user,
            work_performed='Cutter bar aligned and cleared'
        )
        self.harvester.refresh_from_db()
        self.assertEqual(self.harvester.status, Machine.STATUS_ACTIVE)

    def test_decommissioned_machine_never_auto_activates(self):
        """Test that a decommissioned machine never returns to ACTIVE upon repair completion."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.decommissioned_machine,
            maintenance_type=MaintenanceJob.TYPE_CORRECTIVE_REPAIR,
            problem_description='Battery check',
            created_by=self.owner_user
        )
        MaintenanceService.complete_maintenance_job(
            job=job,
            user=self.owner_user,
            work_performed='Checked battery voltage'
        )
        self.decommissioned_machine.refresh_from_db()
        self.assertEqual(self.decommissioned_machine.status, Machine.STATUS_DECOMMISSIONED)

    def test_cancel_maintenance_job_restores_machine_status(self):
        """Test cancelling a maintenance job restores machine status to ACTIVE if safe."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.tractor,
            maintenance_type=MaintenanceJob.TYPE_BREAKDOWN_REPAIR,
            problem_description='Minor sensor alarm',
            machine_stopped=True,
            created_by=self.owner_user
        )
        self.tractor.refresh_from_db()
        self.assertEqual(self.tractor.status, Machine.STATUS_UNDER_MAINTENANCE)

        MaintenanceService.cancel_maintenance_job(
            job=job,
            user=self.manager_user,
            cancellation_reason='Sensor was dirty, cleaned on field without repair'
        )
        job.refresh_from_db()
        self.assertEqual(job.status, MaintenanceJob.STATUS_CANCELLED)
        self.tractor.refresh_from_db()
        self.assertEqual(self.tractor.status, Machine.STATUS_ACTIVE)

    def test_soft_delete_maintenance_job(self):
        """Test soft deleting a maintenance job."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Delete test',
            created_by=self.owner_user
        )
        MaintenanceService.soft_delete_maintenance_job(job, user=self.owner_user)
        job.refresh_from_db()
        self.assertTrue(job.is_deleted)


# ==============================================================================
# 5. FINANCIAL LEDGER ISOLATION & EXPLICIT POSTING TESTS
# ==============================================================================

class MaintenanceFinancialIntegrationTests(MachineMaintenanceBaseTestCase):
    def setUp(self):
        super().setUp()
        self.job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Oil change',
            labor_cost=Decimal('1000.00'),
            supplier=self.workshop_supplier,
            created_by=self.owner_user
        )
        MaintenanceService.add_part_usage(
            job=self.job,
            part_name='Engine Oil',
            quantity=Decimal('1.00'),
            unit_cost=Decimal('2500.00'),
            supplier=self.parts_supplier,
            user=self.manager_user
        )

    def test_operational_job_does_not_mutate_account_balance(self):
        """Test creating and completing a job does NOT automatically reduce account balance."""
        initial_balance = self.cash_account.current_balance

        MaintenanceService.complete_maintenance_job(
            job=self.job,
            user=self.owner_user,
            work_performed='All parts replaced'
        )
        self.cash_account.refresh_from_db()
        self.assertEqual(self.cash_account.current_balance, initial_balance)
        self.assertIsNone(self.job.linked_expense)

    def test_explicit_post_maintenance_expense(self):
        """Test Owner/Accountant can explicitly post completed maintenance to Expenses."""
        MaintenanceService.complete_maintenance_job(
            job=self.job,
            user=self.owner_user,
            work_performed='All parts replaced'
        )
        initial_balance = self.cash_account.current_balance

        expense = MaintenanceService.post_maintenance_expense(
            job=self.job,
            account=self.cash_account,
            category=self.expense_category,
            user=self.owner_user,
            payment_method=Expense.METHOD_CASH
        )
        self.assertIsNotNone(expense)
        self.assertEqual(expense.amount, Decimal('3500.00'))
        self.assertEqual(expense.machine, self.harvester)

        # Account balance must be reduced by 3500
        self.cash_account.refresh_from_db()
        self.assertEqual(self.cash_account.current_balance, initial_balance - Decimal('3500.00'))

        # Job must be linked to expense
        self.job.refresh_from_db()
        self.assertEqual(self.job.linked_expense, expense)

    def test_duplicate_expense_posting_is_prevented(self):
        """Test attempting to post the same maintenance job twice raises ValidationError."""
        MaintenanceService.complete_maintenance_job(
            job=self.job,
            user=self.owner_user,
            work_performed='All parts replaced'
        )
        # First post succeeds
        MaintenanceService.post_maintenance_expense(
            job=self.job,
            account=self.cash_account,
            category=self.expense_category,
            user=self.owner_user
        )

        # Second post must fail
        with self.assertRaises(ValidationError):
            MaintenanceService.post_maintenance_expense(
                job=self.job,
                account=self.cash_account,
                category=self.expense_category,
                user=self.owner_user
            )

    def test_cannot_post_uncompleted_job(self):
        """Test cannot post an OPEN or IN_REPAIR job to expenses."""
        with self.assertRaises(ValidationError):
            MaintenanceService.post_maintenance_expense(
                job=self.job,
                account=self.cash_account,
                category=self.expense_category,
                user=self.owner_user
            )

    def test_cannot_post_zero_cost_job(self):
        """Test cannot post a job with ₹0.00 cost to expenses."""
        zero_job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Zero cost check',
            labor_cost=Decimal('0.00')
        )
        MaintenanceService.complete_maintenance_job(
            job=zero_job,
            user=self.owner_user,
            work_performed='Check done'
        )
        with self.assertRaises(ValidationError):
            MaintenanceService.post_maintenance_expense(
                job=zero_job,
                account=self.cash_account,
                category=self.expense_category,
                user=self.owner_user
            )


# ==============================================================================
# 6. HTTP VIEWS & RBAC PERMISSION TESTS
# ==============================================================================

class MaintenanceViewAndRBACTests(MachineMaintenanceBaseTestCase):
    def test_maintenance_dashboard_view_access(self):
        """Test Owner, Manager, and Accountant can access maintenance dashboard."""
        url = reverse('machines:maintenance_dashboard')

        # Owner
        self.client.force_login(self.owner_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'machines/maintenance_dashboard.html')

        # Manager
        self.client.force_login(self.manager_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        # Accountant
        self.client.force_login(self.accountant_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

    def test_maintenance_job_list_view_and_filtering(self):
        """Test listing jobs and filtering by machine and type."""
        MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Test Job 1',
            created_by=self.owner_user
        )
        MaintenanceService.create_maintenance_job(
            machine=self.tractor,
            maintenance_type=MaintenanceJob.TYPE_BREAKDOWN_REPAIR,
            problem_description='Test Job 2',
            created_by=self.owner_user
        )

        self.client.force_login(self.manager_user)
        url = reverse('machines:maintenance_job_list')

        # All jobs
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['jobs']), 2)

        # Filter by machine
        res_m = self.client.get(url, {'machine': str(self.harvester.id)})
        self.assertEqual(len(res_m.context['jobs']), 1)

        # Filter by type
        res_t = self.client.get(url, {'type': MaintenanceJob.TYPE_BREAKDOWN_REPAIR})
        self.assertEqual(len(res_t.context['jobs']), 1)

    def test_maintenance_job_create_view_post(self):
        """Test creating a maintenance job via HTTP POST."""
        self.client.force_login(self.manager_user)
        url = reverse('machines:maintenance_job_create')
        data = {
            'machine': self.harvester.id,
            'maintenance_type': MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            'reported_date': timezone.now().strftime('%Y-%m-%d'),
            'meter_reading': '550.00',
            'problem_description': '250h Service Inspection',
            'severity': MaintenanceJob.SEVERITY_MEDIUM,
            'labor_cost': '1200.00',
            'external_service_cost': '0.00',
            'other_cost': '0.00',
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MaintenanceJob.objects.filter(problem_description='250h Service Inspection').count(), 1)

    def test_maintenance_job_detail_view(self):
        """Test viewing job detail page."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Detail view test',
            created_by=self.owner_user
        )
        self.client.force_login(self.owner_user)
        url = reverse('machines:maintenance_job_detail', kwargs={'job_id': job.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'machines/maintenance_job_detail.html')
        self.assertEqual(res.context['job'].id, job.id)

    def test_maintenance_part_add_and_delete_view_post(self):
        """Test adding and deleting a spare part via HTTP POST."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Parts test',
            created_by=self.owner_user
        )
        self.client.force_login(self.manager_user)

        # Add Part
        add_url = reverse('machines:maintenance_part_add', kwargs={'job_id': job.id})
        part_data = {
            'part_name': 'Air Filter Outer',
            'part_number': 'FLT-AIR-01',
            'quantity': '1.00',
            'unit_cost': '850.00',
            'supplier': self.parts_supplier.id
        }
        res_add = self.client.post(add_url, part_data)
        self.assertEqual(res_add.status_code, 302)
        self.assertEqual(job.part_usages.count(), 1)
        part = job.part_usages.first()
        self.assertEqual(part.total_cost, Decimal('850.00'))

        # Delete Part
        del_url = reverse('machines:maintenance_part_delete', kwargs={'job_id': job.id, 'part_id': part.id})
        res_del = self.client.post(del_url)
        self.assertEqual(res_del.status_code, 302)
        self.assertEqual(job.part_usages.count(), 0)

    def test_maintenance_job_start_view_post(self):
        """Test starting a job via HTTP POST view."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Start test',
            created_by=self.owner_user
        )
        self.client.force_login(self.manager_user)
        start_url = reverse('machines:maintenance_job_start', kwargs={'job_id': job.id})
        res = self.client.post(start_url, {'diagnosis': 'Started diagnosis'})
        self.assertEqual(res.status_code, 302)
        job.refresh_from_db()
        self.assertEqual(job.status, MaintenanceJob.STATUS_IN_REPAIR)

    def test_maintenance_job_complete_view_post(self):
        """Test completing a job via HTTP POST."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Job to complete',
            machine_stopped=True,
            created_by=self.owner_user
        )
        self.client.force_login(self.owner_user)
        complete_url = reverse('machines:maintenance_job_complete', kwargs={'job_id': job.id})
        data = {
            'completed_date': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'meter_reading': '520.00',
            'work_performed': 'Successfully completed all maintenance steps.',
            'labor_cost': '1000.00',
            'external_service_cost': '200.00',
            'other_cost': '50.00',
        }
        res = self.client.post(complete_url, data)
        self.assertEqual(res.status_code, 302)
        job.refresh_from_db()
        self.assertEqual(job.status, MaintenanceJob.STATUS_COMPLETED)
        self.assertEqual(job.total_maintenance_cost, Decimal('1250.00'))

    def test_maintenance_job_cancel_view_post(self):
        """Test cancelling a job via HTTP POST."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Job to cancel',
            created_by=self.owner_user
        )
        self.client.force_login(self.manager_user)
        cancel_url = reverse('machines:maintenance_job_cancel', kwargs={'job_id': job.id})
        res = self.client.post(cancel_url, {'cancellation_reason': 'Duplicate entry'})
        self.assertEqual(res.status_code, 302)
        job.refresh_from_db()
        self.assertEqual(job.status, MaintenanceJob.STATUS_CANCELLED)

    def test_maintenance_job_post_expense_view_post(self):
        """Test posting expense via HTTP POST view."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Job for expense posting',
            labor_cost=Decimal('1500.00'),
            created_by=self.owner_user
        )
        MaintenanceService.complete_maintenance_job(
            job=job,
            user=self.owner_user,
            work_performed='Done'
        )

        self.client.force_login(self.accountant_user)
        post_url = reverse('machines:maintenance_job_post_expense', kwargs={'job_id': job.id})
        data = {
            'account': self.cash_account.id,
            'category': self.expense_category.id,
            'payment_method': Expense.METHOD_CASH
        }
        res = self.client.post(post_url, data)
        self.assertEqual(res.status_code, 302)
        job.refresh_from_db()
        self.assertIsNotNone(job.linked_expense)
        self.assertEqual(job.linked_expense.amount, Decimal('1500.00'))

    def test_schedule_crud_views(self):
        """Test schedule list, create, and edit views."""
        self.client.force_login(self.manager_user)

        # 1. Create Schedule
        create_url = reverse('machines:maintenance_schedule_create')
        data = {
            'machine': self.harvester.id,
            'schedule_name': 'Greasing & Inspection',
            'service_basis': MachineMaintenanceSchedule.BASIS_METER,
            'service_interval_meter': '100.00',
            'warning_meter_before': '20.00',
            'warning_days_before': 7,
            'is_active': True
        }
        res_create = self.client.post(create_url, data)
        self.assertEqual(res_create.status_code, 302)
        sch = MachineMaintenanceSchedule.objects.get(schedule_name='Greasing & Inspection')

        # 2. List Schedules
        list_url = reverse('machines:maintenance_schedule_list')
        res_list = self.client.get(list_url)
        self.assertEqual(res_list.status_code, 200)
        self.assertTemplateUsed(res_list, 'machines/maintenance_schedule_list.html')

        # 3. Edit Schedule
        edit_url = reverse('machines:maintenance_schedule_edit', kwargs={'schedule_id': sch.id})
        res_edit = self.client.post(edit_url, {
            'machine': self.harvester.id,
            'schedule_name': 'Greasing & Full Inspection',
            'service_basis': MachineMaintenanceSchedule.BASIS_METER,
            'service_interval_meter': '150.00',
            'warning_meter_before': '20.00',
            'warning_days_before': 7,
            'is_active': True
        })
        self.assertEqual(res_edit.status_code, 302)
        sch.refresh_from_db()
        self.assertEqual(sch.schedule_name, 'Greasing & Full Inspection')

    def test_machine_service_history_view(self):
        """Test viewing dedicated machine service history timeline."""
        MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='History job 1',
            created_by=self.owner_user
        )
        self.client.force_login(self.owner_user)
        url = reverse('machines:machine_service_history', kwargs={'machine_id': self.harvester.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'machines/maintenance_history.html')
        self.assertEqual(res.context['machine'].id, self.harvester.id)
        self.assertEqual(res.context['total_jobs'], 1)

    def test_audit_logging_on_maintenance_events(self):
        """Test that key maintenance actions produce AuditLog records."""
        job = MaintenanceService.create_maintenance_job(
            machine=self.harvester,
            maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE,
            problem_description='Audit test job',
            created_by=self.owner_user
        )
        create_logs = AuditLog.objects.filter(entity_type='MaintenanceJob', entity_id=str(job.id), action=AuditLog.ACTION_CREATE)
        self.assertTrue(create_logs.exists())

        MaintenanceService.start_maintenance_job(job, user=self.owner_user)
        update_logs = AuditLog.objects.filter(entity_type='MaintenanceJob', entity_id=str(job.id), action=AuditLog.ACTION_UPDATE)
        self.assertTrue(update_logs.exists())
