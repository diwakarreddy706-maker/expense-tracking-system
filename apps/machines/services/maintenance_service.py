import logging
import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.contrib.auth.models import User

from apps.machines.models import Machine, MachineMaintenanceSchedule, MaintenanceJob, MaintenancePartUsage
from apps.finance.models import Supplier, Account
from apps.expenses.models import Expense, ExpenseCategory
from apps.expenses.services.expense_service import ExpenseService
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog

logger = logging.getLogger('expense_tracking.financial')


class MaintenanceService:
    """
    Central Service for Machinery Maintenance, Breakdown Tracking,
    Spare Part Usage, and Service Schedule Intervals (Phase 15).
    Operates strictly as an operational layer with explicit optional financial expense posting.
    """

    @classmethod
    def generate_maintenance_code(cls, date_val=None) -> str:
        """Generates unique sequential maintenance code e.g. MNT-20260816-0001."""
        target_date = date_val or timezone.now().date()
        date_str = target_date.strftime('%Y%m%d')
        prefix = f"MNT-{date_str}-"

        last_entry = MaintenanceJob.objects.filter(maintenance_code__startswith=prefix).order_by('-id').first()
        if last_entry:
            try:
                seq = int(last_entry.maintenance_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def calculate_part_total(cls, quantity: Decimal, unit_cost: Decimal) -> Decimal:
        """Calculates total cost of a part usage item with 2 decimal places."""
        if not isinstance(quantity, Decimal):
            quantity = Decimal(str(quantity))
        if not isinstance(unit_cost, Decimal):
            unit_cost = Decimal(str(unit_cost))
        return (quantity * unit_cost).quantize(Decimal('0.01'))

    @classmethod
    def recalculate_job_costs(cls, job: MaintenanceJob) -> MaintenanceJob:
        """
        Authoritative recalculation of all parts and total maintenance costs for a job.
        Formula:
        parts_cost = SUM(part_usages.total_cost)
        total_maintenance_cost = parts_cost + labor_cost + external_service_cost + other_cost
        """
        parts_total = Decimal('0.00')
        for part in job.part_usages.all():
            parts_total += (part.total_cost or Decimal('0.00'))

        job.parts_cost = parts_total.quantize(Decimal('0.01'))
        labor = job.labor_cost or Decimal('0.00')
        external = job.external_service_cost or Decimal('0.00')
        other = job.other_cost or Decimal('0.00')

        job.total_maintenance_cost = (job.parts_cost + labor + external + other).quantize(Decimal('0.01'))
        job.save(update_fields=['parts_cost', 'total_maintenance_cost', 'updated_at'])
        return job

    # --------------------------------------------------------------------------
    # 1. Maintenance Schedule Management
    # --------------------------------------------------------------------------
    @classmethod
    def create_schedule(
        cls,
        machine: Machine,
        schedule_name: str,
        service_basis: str = MachineMaintenanceSchedule.BASIS_METER,
        service_interval_meter: Optional[Decimal] = None,
        service_interval_days: Optional[int] = None,
        last_service_date=None,
        last_service_meter: Optional[Decimal] = None,
        warning_meter_before: Optional[Decimal] = Decimal('25.00'),
        warning_days_before: Optional[int] = 7,
        notes: Optional[str] = None,
        created_by: Optional[User] = None,
        request=None
    ) -> MachineMaintenanceSchedule:
        """Creates a preventive maintenance schedule with calculated next service metrics."""
        if not machine or machine.is_deleted:
            raise ValidationError("A valid active machine is required.")

        if not schedule_name or not schedule_name.strip():
            raise ValidationError("Schedule name is required.")

        # Validate intervals based on service_basis
        if service_basis in [MachineMaintenanceSchedule.BASIS_METER, MachineMaintenanceSchedule.BASIS_BOTH]:
            if not service_interval_meter or Decimal(str(service_interval_meter)) <= Decimal('0.00'):
                raise ValidationError("Meter-based schedule requires a positive service_interval_meter.")
            service_interval_meter = Decimal(str(service_interval_meter))

        if service_basis in [MachineMaintenanceSchedule.BASIS_DATE, MachineMaintenanceSchedule.BASIS_BOTH]:
            if not service_interval_days or int(service_interval_days) <= 0:
                raise ValidationError("Date-based schedule requires a positive service_interval_days.")
            service_interval_days = int(service_interval_days)

        # Calculate initial next service metrics
        next_m = None
        if service_interval_meter:
            base_meter = last_service_meter if last_service_meter is not None else (machine.current_meter_reading or Decimal('0.00'))
            next_m = (base_meter + service_interval_meter).quantize(Decimal('0.01'))

        next_d = None
        if service_interval_days:
            base_date = last_service_date or timezone.now().date()
            if isinstance(base_date, datetime.datetime):
                base_date = base_date.date()
            next_d = base_date + datetime.timedelta(days=service_interval_days)

        schedule = MachineMaintenanceSchedule.objects.create(
            machine=machine,
            schedule_name=schedule_name.strip(),
            service_basis=service_basis,
            service_interval_meter=service_interval_meter,
            service_interval_days=service_interval_days,
            last_service_date=last_service_date,
            last_service_meter=last_service_meter,
            next_service_date=next_d,
            next_service_meter=next_m,
            warning_meter_before=Decimal(str(warning_meter_before or '25.00')),
            warning_days_before=int(warning_days_before or 7),
            notes=notes,
            created_by=created_by,
            is_active=True
        )

        log_audit_event(
            created_by,
            AuditLog.ACTION_CREATE,
            'MachineMaintenanceSchedule',
            schedule.id,
            changes={
                'machine': machine.name,
                'schedule_name': schedule.schedule_name,
                'basis': schedule.service_basis,
                'next_meter': str(schedule.next_service_meter),
                'next_date': str(schedule.next_service_date),
            },
            request=request
        )
        return schedule

    @classmethod
    def update_schedule(
        cls,
        schedule: MachineMaintenanceSchedule,
        schedule_name: str,
        service_basis: str,
        service_interval_meter: Optional[Decimal] = None,
        service_interval_days: Optional[int] = None,
        last_service_date=None,
        last_service_meter: Optional[Decimal] = None,
        warning_meter_before: Optional[Decimal] = Decimal('25.00'),
        warning_days_before: Optional[int] = 7,
        notes: Optional[str] = None,
        is_active: bool = True,
        user: Optional[User] = None,
        request=None
    ) -> MachineMaintenanceSchedule:
        """Updates a maintenance schedule and recalculates next service projections."""
        schedule.schedule_name = schedule_name.strip()
        schedule.service_basis = service_basis
        schedule.is_active = is_active
        schedule.notes = notes

        if service_basis in [MachineMaintenanceSchedule.BASIS_METER, MachineMaintenanceSchedule.BASIS_BOTH]:
            if not service_interval_meter or Decimal(str(service_interval_meter)) <= Decimal('0.00'):
                raise ValidationError("Meter interval must be greater than zero.")
            schedule.service_interval_meter = Decimal(str(service_interval_meter))
        else:
            schedule.service_interval_meter = None

        if service_basis in [MachineMaintenanceSchedule.BASIS_DATE, MachineMaintenanceSchedule.BASIS_BOTH]:
            if not service_interval_days or int(service_interval_days) <= 0:
                raise ValidationError("Days interval must be greater than zero.")
            schedule.service_interval_days = int(service_interval_days)
        else:
            schedule.service_interval_days = None

        schedule.last_service_date = last_service_date
        schedule.last_service_meter = last_service_meter
        schedule.warning_meter_before = Decimal(str(warning_meter_before or '25.00'))
        schedule.warning_days_before = int(warning_days_before or 7)

        # Recalculate next targets
        if schedule.service_interval_meter:
            base_meter = schedule.last_service_meter if schedule.last_service_meter is not None else (schedule.machine.current_meter_reading or Decimal('0.00'))
            schedule.next_service_meter = (base_meter + schedule.service_interval_meter).quantize(Decimal('0.01'))
        else:
            schedule.next_service_meter = None

        if schedule.service_interval_days:
            base_date = schedule.last_service_date or timezone.now().date()
            if isinstance(base_date, datetime.datetime):
                base_date = base_date.date()
            schedule.next_service_date = base_date + datetime.timedelta(days=schedule.service_interval_days)
        else:
            schedule.next_service_date = None

        schedule.save()

        log_audit_event(
            user,
            AuditLog.ACTION_UPDATE,
            'MachineMaintenanceSchedule',
            schedule.id,
            changes={
                'schedule_name': schedule.schedule_name,
                'is_active': schedule.is_active,
                'next_meter': str(schedule.next_service_meter),
                'next_date': str(schedule.next_service_date),
            },
            request=request
        )
        return schedule

    # --------------------------------------------------------------------------
    # 2. Maintenance Job Lifecycle Management
    # --------------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def create_maintenance_job(
        cls,
        machine: Machine,
        maintenance_type: str,
        problem_description: str,
        reported_date=None,
        maintenance_schedule: Optional[MachineMaintenanceSchedule] = None,
        meter_reading: Optional[Decimal] = None,
        breakdown_location: Optional[str] = None,
        breakdown_time=None,
        machine_stopped: bool = False,
        severity: str = MaintenanceJob.SEVERITY_MEDIUM,
        supplier: Optional[Supplier] = None,
        external_workshop_name: Optional[str] = None,
        labor_cost: Optional[Decimal] = Decimal('0.00'),
        external_service_cost: Optional[Decimal] = Decimal('0.00'),
        other_cost: Optional[Decimal] = Decimal('0.00'),
        diagnosis: Optional[str] = None,
        notes: Optional[str] = None,
        created_by: Optional[User] = None,
        request=None
    ) -> MaintenanceJob:
        """
        Creates a Maintenance / Breakdown job.
        Validates costs and meter reading.
        If machine_stopped is True, transitions machine to UNDER_MAINTENANCE safely.
        """
        if not machine or machine.is_deleted or not machine.is_active:
            raise ValidationError("A valid active machine is required for maintenance.")

        if not problem_description or not problem_description.strip():
            raise ValidationError("Problem description is required.")

        # Meter validation
        if meter_reading is not None:
            meter_val = Decimal(str(meter_reading))
            if meter_val < Decimal('0.00'):
                raise ValidationError("Meter reading cannot be negative.")
        else:
            meter_val = machine.current_meter_reading

        # Costs validation
        labor = Decimal(str(labor_cost or '0.00')).quantize(Decimal('0.01'))
        external = Decimal(str(external_service_cost or '0.00')).quantize(Decimal('0.01'))
        other = Decimal(str(other_cost or '0.00')).quantize(Decimal('0.01'))

        if labor < Decimal('0.00') or external < Decimal('0.00') or other < Decimal('0.00'):
            raise ValidationError("Maintenance costs cannot be negative.")

        total_cost = (labor + external + other).quantize(Decimal('0.01'))

        rep_date = reported_date or timezone.now().date()
        if isinstance(rep_date, datetime.datetime):
            rep_date = rep_date.date()

        code = cls.generate_maintenance_code(rep_date)

        job = MaintenanceJob.objects.create(
            maintenance_code=code,
            machine=machine,
            maintenance_schedule=maintenance_schedule,
            maintenance_type=maintenance_type,
            status=MaintenanceJob.STATUS_OPEN,
            reported_date=rep_date,
            meter_reading=meter_val,
            problem_description=problem_description.strip(),
            diagnosis=diagnosis,
            breakdown_location=breakdown_location,
            breakdown_time=breakdown_time,
            machine_stopped=machine_stopped,
            severity=severity,
            supplier=supplier,
            external_workshop_name=external_workshop_name,
            parts_cost=Decimal('0.00'),
            labor_cost=labor,
            external_service_cost=external,
            other_cost=other,
            total_maintenance_cost=total_cost,
            notes=notes,
            created_by=created_by,
            is_deleted=False
        )

        # If machine is stopped or in breakdown, set machine to UNDER_MAINTENANCE (unless decommissioned)
        if machine_stopped and machine.status != Machine.STATUS_DECOMMISSIONED:
            machine.status = Machine.STATUS_UNDER_MAINTENANCE
            machine.save(update_fields=['status', 'updated_at'])

        log_audit_event(
            created_by,
            AuditLog.ACTION_CREATE,
            'MaintenanceJob',
            job.id,
            changes={
                'maintenance_code': job.maintenance_code,
                'machine': machine.name,
                'type': job.maintenance_type,
                'status': job.status,
                'machine_stopped': job.machine_stopped,
                'meter': str(job.meter_reading),
                'total_cost': str(job.total_maintenance_cost)
            },
            request=request
        )
        return job

    @classmethod
    @transaction.atomic
    def start_maintenance_job(
        cls,
        job: MaintenanceJob,
        user: User,
        started_date=None,
        diagnosis: Optional[str] = None,
        request=None
    ) -> MaintenanceJob:
        """
        Transitions job from OPEN / DIAGNOSING / WAITING_FOR_PARTS to IN_REPAIR.
        Sets machine to UNDER_MAINTENANCE if not DECOMMISSIONED.
        """
        if job.status in [MaintenanceJob.STATUS_COMPLETED, MaintenanceJob.STATUS_CANCELLED]:
            raise ValidationError(f"Cannot start maintenance job with status {job.get_status_display()}.")

        old_status = job.status
        job.status = MaintenanceJob.STATUS_IN_REPAIR
        job.started_date = started_date or timezone.now()
        if diagnosis:
            job.diagnosis = diagnosis.strip()
        job.save(update_fields=['status', 'started_date', 'diagnosis', 'updated_at'])

        machine = job.machine
        if machine.status != Machine.STATUS_DECOMMISSIONED:
            machine.status = Machine.STATUS_UNDER_MAINTENANCE
            machine.save(update_fields=['status', 'updated_at'])

        log_audit_event(
            user,
            AuditLog.ACTION_UPDATE,
            'MaintenanceJob',
            job.id,
            changes={
                'action': 'START_MAINTENANCE',
                'old_status': old_status,
                'new_status': job.status,
                'machine_status': machine.status,
                'started_date': str(job.started_date)
            },
            request=request
        )
        return job

    @classmethod
    @transaction.atomic
    def add_part_usage(
        cls,
        job: MaintenanceJob,
        part_name: str,
        quantity: Decimal,
        unit_cost: Decimal,
        part_number: Optional[str] = None,
        supplier: Optional[Supplier] = None,
        notes: Optional[str] = None,
        user: Optional[User] = None,
        request=None
    ) -> MaintenancePartUsage:
        """Adds a spare part item to an editable maintenance job and updates totals."""
        if job.status in [MaintenanceJob.STATUS_COMPLETED, MaintenanceJob.STATUS_CANCELLED]:
            raise ValidationError(f"Cannot add parts to a {job.get_status_display()} maintenance job.")

        if not part_name or not part_name.strip():
            raise ValidationError("Part name is required.")

        qty = Decimal(str(quantity))
        cost = Decimal(str(unit_cost))

        if qty <= Decimal('0.00'):
            raise ValidationError("Part quantity must be greater than zero.")
        if cost < Decimal('0.00'):
            raise ValidationError("Part unit cost cannot be negative.")

        total = cls.calculate_part_total(qty, cost)

        part = MaintenancePartUsage.objects.create(
            maintenance_job=job,
            part_name=part_name.strip(),
            part_number=part_number.strip() if part_number else None,
            quantity=qty,
            unit_cost=cost,
            total_cost=total,
            supplier=supplier,
            notes=notes
        )

        cls.recalculate_job_costs(job)

        log_audit_event(
            user,
            AuditLog.ACTION_CREATE,
            'MaintenancePartUsage',
            part.id,
            changes={
                'maintenance_code': job.maintenance_code,
                'part_name': part.part_name,
                'quantity': str(part.quantity),
                'unit_cost': str(part.unit_cost),
                'total_cost': str(part.total_cost)
            },
            request=request
        )
        return part

    @classmethod
    @transaction.atomic
    def update_part_usage(
        cls,
        part: MaintenancePartUsage,
        quantity: Decimal,
        unit_cost: Decimal,
        part_name: Optional[str] = None,
        part_number: Optional[str] = None,
        supplier: Optional[Supplier] = None,
        notes: Optional[str] = None,
        user: Optional[User] = None,
        request=None
    ) -> MaintenancePartUsage:
        """Updates a spare part usage item and recalculates parent job costs."""
        job = part.maintenance_job
        if job.status in [MaintenanceJob.STATUS_COMPLETED, MaintenanceJob.STATUS_CANCELLED]:
            raise ValidationError(f"Cannot edit parts on a {job.get_status_display()} maintenance job.")

        qty = Decimal(str(quantity))
        cost = Decimal(str(unit_cost))

        if qty <= Decimal('0.00'):
            raise ValidationError("Part quantity must be greater than zero.")
        if cost < Decimal('0.00'):
            raise ValidationError("Part unit cost cannot be negative.")

        if part_name:
            part.part_name = part_name.strip()
        if part_number is not None:
            part.part_number = part_number.strip() if part_number else None

        part.quantity = qty
        part.unit_cost = cost
        part.total_cost = cls.calculate_part_total(qty, cost)
        part.supplier = supplier
        part.notes = notes
        part.save()

        cls.recalculate_job_costs(job)

        log_audit_event(
            user,
            AuditLog.ACTION_UPDATE,
            'MaintenancePartUsage',
            part.id,
            changes={
                'maintenance_code': job.maintenance_code,
                'part_name': part.part_name,
                'quantity': str(part.quantity),
                'unit_cost': str(part.unit_cost),
                'total_cost': str(part.total_cost)
            },
            request=request
        )
        return part

    @classmethod
    @transaction.atomic
    def delete_part_usage(
        cls,
        part: MaintenancePartUsage,
        user: Optional[User] = None,
        request=None
    ):
        """Removes a spare part usage item and updates parent job totals."""
        job = part.maintenance_job
        if job.status in [MaintenanceJob.STATUS_COMPLETED, MaintenanceJob.STATUS_CANCELLED]:
            raise ValidationError(f"Cannot delete parts on a {job.get_status_display()} maintenance job.")

        part_id = part.id
        part_name = part.part_name
        part.delete()

        cls.recalculate_job_costs(job)

        log_audit_event(
            user,
            AuditLog.ACTION_SOFT_DELETE,
            'MaintenancePartUsage',
            part_id,
            changes={
                'maintenance_code': job.maintenance_code,
                'deleted_part': part_name
            },
            request=request
        )

    @classmethod
    @transaction.atomic
    def complete_maintenance_job(
        cls,
        job: MaintenanceJob,
        user: User,
        completed_date=None,
        meter_reading: Optional[Decimal] = None,
        work_performed: Optional[str] = None,
        labor_cost: Optional[Decimal] = None,
        external_service_cost: Optional[Decimal] = None,
        other_cost: Optional[Decimal] = None,
        request=None
    ) -> MaintenanceJob:
        """
        Completes a maintenance/breakdown job.
        Validates completion date, updates costs, updates schedule targets,
        and safely returns machine to ACTIVE if no other blocking jobs remain.
        """
        if job.status == MaintenanceJob.STATUS_COMPLETED:
            raise ValidationError("This maintenance job is already marked as COMPLETED.")
        if job.status == MaintenanceJob.STATUS_CANCELLED:
            raise ValidationError("Cannot complete a CANCELLED maintenance job.")

        work_text = work_performed or job.work_performed
        if not work_text or not work_text.strip():
            raise ValidationError("Work performed summary is required to complete maintenance.")

        comp_dt = completed_date or timezone.now()
        if isinstance(comp_dt, datetime.date) and not isinstance(comp_dt, datetime.datetime):
            comp_dt = timezone.make_aware(datetime.datetime.combine(comp_dt, datetime.time.min))

        if job.started_date and comp_dt < job.started_date:
            raise ValidationError("Completion date/time cannot be earlier than started date/time.")

        # Update meter reading if provided
        machine = job.machine
        if meter_reading is not None:
            m_val = Decimal(str(meter_reading))
            if m_val < Decimal('0.00'):
                raise ValidationError("Meter reading cannot be negative.")
            job.meter_reading = m_val
            # Update cumulative current meter reading on machine if higher
            if m_val > machine.current_meter_reading:
                machine.current_meter_reading = m_val
                machine.save(update_fields=['current_meter_reading', 'updated_at'])

        # Update optional costs
        if labor_cost is not None:
            l_cost = Decimal(str(labor_cost))
            if l_cost < Decimal('0.00'):
                raise ValidationError("Labor cost cannot be negative.")
            job.labor_cost = l_cost.quantize(Decimal('0.01'))

        if external_service_cost is not None:
            e_cost = Decimal(str(external_service_cost))
            if e_cost < Decimal('0.00'):
                raise ValidationError("External service cost cannot be negative.")
            job.external_service_cost = e_cost.quantize(Decimal('0.01'))

        if other_cost is not None:
            o_cost = Decimal(str(other_cost))
            if o_cost < Decimal('0.00'):
                raise ValidationError("Other cost cannot be negative.")
            job.other_cost = o_cost.quantize(Decimal('0.01'))

        job.work_performed = work_text.strip()
        job.completed_date = comp_dt
        job.status = MaintenanceJob.STATUS_COMPLETED
        job.machine_stopped = False

        # Recalculate full total
        cls.recalculate_job_costs(job)

        # Update attached preventive schedule if applicable
        schedule = job.maintenance_schedule
        if schedule and schedule.is_active:
            comp_date_val = comp_dt.date() if isinstance(comp_dt, datetime.datetime) else comp_dt
            schedule.last_service_date = comp_date_val
            effective_meter = job.meter_reading if job.meter_reading is not None else machine.current_meter_reading
            schedule.last_service_meter = effective_meter

            if schedule.service_interval_meter and effective_meter is not None:
                schedule.next_service_meter = (effective_meter + schedule.service_interval_meter).quantize(Decimal('0.01'))
                job.next_service_meter = schedule.next_service_meter

            if schedule.service_interval_days and schedule.last_service_date:
                schedule.next_service_date = schedule.last_service_date + datetime.timedelta(days=schedule.service_interval_days)
                job.next_service_date = schedule.next_service_date

            schedule.save()

        job.save()

        # Restore machine to ACTIVE if safe (no other active blocking repairs, and not decommissioned)
        other_blocking = MaintenanceJob.objects.filter(
            machine=machine,
            is_deleted=False,
            status__in=[
                MaintenanceJob.STATUS_OPEN,
                MaintenanceJob.STATUS_DIAGNOSING,
                MaintenanceJob.STATUS_WAITING_FOR_PARTS,
                MaintenanceJob.STATUS_IN_REPAIR
            ]
        ).exclude(id=job.id).filter(
            models.Q(machine_stopped=True) |
            models.Q(status__in=[
                MaintenanceJob.STATUS_IN_REPAIR,
                MaintenanceJob.STATUS_DIAGNOSING,
                MaintenanceJob.STATUS_WAITING_FOR_PARTS
            ])
        ).exists()

        if not other_blocking and machine.status != Machine.STATUS_DECOMMISSIONED:
            machine.status = Machine.STATUS_ACTIVE
            machine.save(update_fields=['status', 'updated_at'])

        log_audit_event(
            user,
            AuditLog.ACTION_UPDATE,
            'MaintenanceJob',
            job.id,
            changes={
                'action': 'COMPLETE_MAINTENANCE',
                'status': job.status,
                'completed_date': str(job.completed_date),
                'total_cost': str(job.total_maintenance_cost),
                'machine_status': machine.status
            },
            request=request
        )
        return job

    @classmethod
    @transaction.atomic
    def cancel_maintenance_job(
        cls,
        job: MaintenanceJob,
        user: User,
        cancellation_reason: Optional[str] = None,
        request=None
    ) -> MaintenanceJob:
        """Cancels a maintenance job and safely restores machine to ACTIVE if no other repairs remain."""
        if job.status == MaintenanceJob.STATUS_COMPLETED:
            raise ValidationError("Cannot cancel a completed maintenance job.")

        old_status = job.status
        job.status = MaintenanceJob.STATUS_CANCELLED
        job.machine_stopped = False
        if cancellation_reason:
            reason_note = f"\n[Cancelled on {timezone.now().strftime('%Y-%m-%d %H:%M')}: {cancellation_reason.strip()}]"
            job.notes = (job.notes or '') + reason_note
        job.save(update_fields=['status', 'machine_stopped', 'notes', 'updated_at'])

        machine = job.machine
        # Check if machine can be restored to ACTIVE
        other_blocking = MaintenanceJob.objects.filter(
            machine=machine,
            is_deleted=False,
            status__in=[
                MaintenanceJob.STATUS_OPEN,
                MaintenanceJob.STATUS_DIAGNOSING,
                MaintenanceJob.STATUS_WAITING_FOR_PARTS,
                MaintenanceJob.STATUS_IN_REPAIR
            ]
        ).exclude(id=job.id).filter(
            models.Q(machine_stopped=True) |
            models.Q(status__in=[
                MaintenanceJob.STATUS_IN_REPAIR,
                MaintenanceJob.STATUS_DIAGNOSING,
                MaintenanceJob.STATUS_WAITING_FOR_PARTS
            ])
        ).exists()

        if not other_blocking and machine.status != Machine.STATUS_DECOMMISSIONED:
            machine.status = Machine.STATUS_ACTIVE
            machine.save(update_fields=['status', 'updated_at'])

        log_audit_event(
            user,
            AuditLog.ACTION_UPDATE,
            'MaintenanceJob',
            job.id,
            changes={
                'action': 'CANCEL_MAINTENANCE',
                'old_status': old_status,
                'new_status': job.status,
                'cancellation_reason': cancellation_reason,
                'machine_status': machine.status
            },
            request=request
        )
        return job

    @classmethod
    @transaction.atomic
    def soft_delete_maintenance_job(
        cls,
        job: MaintenanceJob,
        user: User,
        request=None
    ):
        """Soft deletes a maintenance job."""
        job.is_deleted = True
        job.save(update_fields=['is_deleted', 'updated_at'])

        machine = job.machine
        other_blocking = MaintenanceJob.objects.filter(
            machine=machine,
            is_deleted=False,
            status__in=[
                MaintenanceJob.STATUS_OPEN,
                MaintenanceJob.STATUS_DIAGNOSING,
                MaintenanceJob.STATUS_WAITING_FOR_PARTS,
                MaintenanceJob.STATUS_IN_REPAIR
            ]
        ).exclude(id=job.id).filter(
            models.Q(machine_stopped=True) |
            models.Q(status__in=[
                MaintenanceJob.STATUS_IN_REPAIR,
                MaintenanceJob.STATUS_DIAGNOSING,
                MaintenanceJob.STATUS_WAITING_FOR_PARTS
            ])
        ).exists()

        if not other_blocking and machine.status != Machine.STATUS_DECOMMISSIONED:
            machine.status = Machine.STATUS_ACTIVE
            machine.save(update_fields=['status', 'updated_at'])

        log_audit_event(
            user,
            AuditLog.ACTION_SOFT_DELETE,
            'MaintenanceJob',
            job.id,
            changes={'maintenance_code': job.maintenance_code},
            request=request
        )

    # --------------------------------------------------------------------------
    # 3. Explicit Financial Integration (Owner / Accountant)
    # --------------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def post_maintenance_expense(
        cls,
        job: MaintenanceJob,
        account: Account,
        category: ExpenseCategory,
        user: User,
        payment_method: str = Expense.METHOD_CASH,
        request=None
    ) -> Expense:
        """
        Explicit action by Owner / Accountant to post a completed MaintenanceJob to Expenses.
        Guarantees single posting (prevents duplicate expense creation).
        """
        if job.status != MaintenanceJob.STATUS_COMPLETED:
            raise ValidationError("Only COMPLETED maintenance jobs can be posted to expenses.")

        if job.linked_expense is not None:
            raise ValidationError(f"This maintenance job has already been posted to Expense ({job.linked_expense.expense_code}). Duplicate posting is prevented.")

        if job.total_maintenance_cost <= Decimal('0.00'):
            raise ValidationError("Cannot post an expense for a maintenance job with ₹0.00 total cost.")

        desc = f"Maintenance & Repair [{job.maintenance_code}] for {job.machine.name}. Problem: {job.problem_description[:100]}"

        # Atomically create expense via authoritative ExpenseService
        expense, _ = ExpenseService.create_expense(
            user=user,
            amount=job.total_maintenance_cost,
            category=category,
            account=account,
            payment_method=payment_method,
            business_segment=Expense.SEGMENT_WORKSHOP_REPAIRS,
            expense_date=job.completed_date.date() if isinstance(job.completed_date, datetime.datetime) else (job.completed_date or timezone.now().date()),
            machine=job.machine,
            supplier=job.supplier,
            reference_no=job.maintenance_code,
            description=desc,
            request=request
        )

        job.linked_expense = expense
        job.save(update_fields=['linked_expense', 'updated_at'])

        log_audit_event(
            user,
            AuditLog.ACTION_PAYMENT,
            'MaintenanceJob',
            job.id,
            changes={
                'action': 'POST_EXPENSE',
                'expense_code': expense.expense_code,
                'amount': str(expense.amount),
                'account': account.account_name
            },
            request=request
        )
        return expense
