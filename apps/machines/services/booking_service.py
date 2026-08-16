import logging
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth.models import User

from apps.machines.models import Machine, MachineType, MachineBooking
from apps.employees.models import Employee
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog

logger = logging.getLogger('expense_tracking.financial')


class BookingService:
    """
    Central Service for Machine Booking, Scheduling, Operator Assignment,
    and Dispatch Lifecycle (Phase 12.5).
    Operates strictly as an operational coordination layer.
    """

    @classmethod
    def generate_booking_code(cls, date_val=None) -> str:
        """Generates unique sequential booking code e.g. BKG-20260816-0001."""
        target_date = date_val or timezone.now().date()
        date_str = target_date.strftime('%Y%m%d')
        prefix = f"BKG-{date_str}-"

        last_entry = MachineBooking.objects.filter(booking_code__startswith=prefix).order_by('-id').first()
        if last_entry:
            try:
                seq = int(last_entry.booking_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def get_available_machines(cls, machine_type, work_date, exclude_booking_id=None):
        """
        Returns QuerySet of machines of given type available on the requested work_date.
        Excludes:
        1. Inactive or deleted machines.
        2. Machines with status UNDER_MAINTENANCE or DECOMMISSIONED.
        3. Machines already committed to active bookings (CONFIRMED, DISPATCHED, IN_PROGRESS) on work_date.
        """
        base_qs = Machine.objects.filter(
            machine_type=machine_type,
            is_active=True,
            is_deleted=False
        ).exclude(
            status__in=[Machine.STATUS_UNDER_MAINTENANCE, Machine.STATUS_DECOMMISSIONED]
        )

        conflicting_booking_qs = MachineBooking.objects.filter(
            work_date=work_date,
            is_deleted=False,
            status__in=[
                MachineBooking.STATUS_CONFIRMED,
                MachineBooking.STATUS_DISPATCHED,
                MachineBooking.STATUS_IN_PROGRESS
            ],
            machine__isnull=False
        )

        if exclude_booking_id:
            conflicting_booking_qs = conflicting_booking_qs.exclude(id=exclude_booking_id)

        booked_machine_ids = conflicting_booking_qs.values_list('machine_id', flat=True)
        return base_qs.exclude(id__in=booked_machine_ids)

    @classmethod
    def validate_machine_availability(cls, machine: Machine, work_date, exclude_booking_id=None):
        """
        Validates that a machine is ready and not conflicted on work_date.
        """
        if not machine or machine.is_deleted or not machine.is_active:
            raise ValidationError(f"Machine {machine.name if machine else ''} is not active in the system.")

        if machine.status == Machine.STATUS_UNDER_MAINTENANCE:
            raise ValidationError(f"Machine '{machine.name}' ({machine.machine_code}) is currently UNDER MAINTENANCE and cannot be assigned or dispatched.")

        if machine.status == Machine.STATUS_DECOMMISSIONED:
            raise ValidationError(f"Machine '{machine.name}' ({machine.machine_code}) is DECOMMISSIONED and cannot be used.")

        # Check conflicting bookings on same date
        conflicts = MachineBooking.objects.filter(
            machine=machine,
            work_date=work_date,
            is_deleted=False,
            status__in=[
                MachineBooking.STATUS_CONFIRMED,
                MachineBooking.STATUS_DISPATCHED,
                MachineBooking.STATUS_IN_PROGRESS
            ]
        )
        if exclude_booking_id:
            conflicts = conflicts.exclude(id=exclude_booking_id)

        if conflicts.exists():
            conflict = conflicts.first()
            raise ValidationError(
                f"Machine '{machine.name}' is already assigned to active booking {conflict.booking_code} "
                f"({conflict.customer.name}) on {work_date}."
            )

    @classmethod
    def validate_operator(cls, operator: Employee, machine_type: MachineType = None):
        """
        Validates operator active status, leave status, and role compatibility.
        """
        if not operator or operator.is_deleted:
            raise ValidationError("A valid operator must be selected.")

        if operator.status == Employee.STATUS_INACTIVE:
            raise ValidationError(f"Operator '{operator.full_name}' is INACTIVE and cannot be assigned.")

        if operator.status == Employee.STATUS_ON_LEAVE:
            raise ValidationError(f"Operator '{operator.full_name}' is currently ON LEAVE and cannot be assigned.")

        # Incompatible non-operational roles
        disallowed_roles = [
            Employee.ROLE_SHOP_STAFF,
            Employee.ROLE_ACCOUNTANT,
            Employee.ROLE_WORKSHOP_MECHANIC,
            Employee.ROLE_DAILY_LABOR
        ]
        if operator.role in disallowed_roles:
            raise ValidationError(
                f"Operator '{operator.full_name}' has role '{operator.get_role_display()}', "
                f"which is not authorized for machine operations."
            )

        if machine_type:
            type_code_upper = (machine_type.code or '').upper()
            type_name_upper = (machine_type.name or '').upper()

            is_harvester = 'HARVESTER' in type_code_upper or 'HARVESTER' in type_name_upper or 'COMBINE' in type_name_upper
            is_tractor = 'TRACTOR' in type_code_upper or 'TRACTOR' in type_name_upper

            if is_harvester and operator.role not in [Employee.ROLE_HARVESTER_OPERATOR, Employee.ROLE_MANAGER]:
                raise ValidationError(
                    f"Harvester operations require a Harvester Specialist. '{operator.full_name}' has role '{operator.get_role_display()}'."
                )

            if is_tractor and operator.role not in [Employee.ROLE_TRACTOR_DRIVER, Employee.ROLE_HARVESTER_OPERATOR, Employee.ROLE_MANAGER]:
                raise ValidationError(
                    f"Tractor operations require a Tractor Driver. '{operator.full_name}' has role '{operator.get_role_display()}'."
                )

    @classmethod
    @transaction.atomic
    def create_booking(cls, customer, machine_type, work_date, billing_type, created_by: User,
                       machine=None, operator=None, requested_start_time=None,
                       expected_quantity=Decimal('0.00'), expected_duration_hours=Decimal('0.00'),
                       work_location=None, village=None, crop_description=None,
                       notes=None, request=None) -> MachineBooking:
        """Creates a new MachineBooking in PENDING status."""
        booking_code = cls.generate_booking_code(work_date)

        if machine:
            cls.validate_machine_availability(machine, work_date)
            if machine.machine_type != machine_type:
                raise ValidationError(f"Machine '{machine.name}' does not match requested type '{machine_type.name}'.")

        if operator:
            cls.validate_operator(operator, machine_type)

        booking = MachineBooking.objects.create(
            booking_code=booking_code,
            customer=customer,
            machine_type=machine_type,
            machine=machine,
            operator=operator,
            work_date=work_date,
            requested_start_time=requested_start_time,
            expected_quantity=expected_quantity or Decimal('0.00'),
            expected_duration_hours=expected_duration_hours or Decimal('0.00'),
            billing_type=billing_type,
            work_location=work_location,
            village=village,
            crop_description=crop_description,
            status=MachineBooking.STATUS_PENDING,
            notes=notes,
            created_by=created_by,
        )

        log_audit_event(
            user=created_by,
            action=AuditLog.ACTION_CREATE,
            entity_type='MachineBooking',
            entity_id=booking.id,
            changes={
                'booking_code': booking.booking_code,
                'customer': customer.name,
                'machine_type': machine_type.name,
                'machine': machine.name if machine else None,
                'operator': operator.full_name if operator else None,
                'work_date': str(work_date),
                'billing_type': billing_type,
                'status': booking.status,
            },
            request=request
        )
        return booking

    @classmethod
    @transaction.atomic
    def update_booking(cls, booking: MachineBooking, user: User, data: dict, request=None) -> MachineBooking:
        """Updates an existing booking."""
        if booking.status in [MachineBooking.STATUS_COMPLETED, MachineBooking.STATUS_CANCELLED]:
            raise ValidationError(f"Cannot edit booking in '{booking.get_status_display()}' status.")

        machine = data.get('machine', booking.machine)
        operator = data.get('operator', booking.operator)
        work_date = data.get('work_date', booking.work_date)
        machine_type = data.get('machine_type', booking.machine_type)

        if machine:
            cls.validate_machine_availability(machine, work_date, exclude_booking_id=booking.id)
            if machine.machine_type != machine_type:
                raise ValidationError(f"Machine '{machine.name}' does not match requested type '{machine_type.name}'.")

        if operator:
            cls.validate_operator(operator, machine_type)

        for field, val in data.items():
            setattr(booking, field, val)

        booking.save()

        log_audit_event(
            user=user,
            action=AuditLog.ACTION_UPDATE,
            entity_type='MachineBooking',
            entity_id=booking.id,
            changes={
                'booking_code': booking.booking_code,
                'customer': booking.customer.name,
                'machine': booking.machine.name if booking.machine else None,
                'operator': booking.operator.full_name if booking.operator else None,
                'status': booking.status,
            },
            request=request
        )
        return booking

    @classmethod
    @transaction.atomic
    def confirm_booking(cls, booking: MachineBooking, user: User, machine=None, operator=None, request=None) -> MachineBooking:
        """
        Transitions booking from PENDING to CONFIRMED.
        Assigns and validates machine and operator.
        """
        if booking.status not in [MachineBooking.STATUS_PENDING, MachineBooking.STATUS_CONFIRMED]:
            raise ValidationError(f"Cannot confirm booking from status '{booking.get_status_display()}'.")

        target_machine = machine or booking.machine
        target_operator = operator or booking.operator

        if not target_machine:
            raise ValidationError("A specific machine must be assigned to confirm this booking.")

        if not target_operator:
            raise ValidationError("An operator must be assigned to confirm this booking.")

        cls.validate_machine_availability(target_machine, booking.work_date, exclude_booking_id=booking.id)
        if target_machine.machine_type != booking.machine_type:
            raise ValidationError(f"Machine '{target_machine.name}' does not match requested type '{booking.machine_type.name}'.")

        cls.validate_operator(target_operator, booking.machine_type)

        old_status = booking.status
        booking.machine = target_machine
        booking.operator = target_operator
        booking.status = MachineBooking.STATUS_CONFIRMED
        booking.save()

        log_audit_event(
            user=user,
            action=AuditLog.ACTION_UPDATE,
            entity_type='MachineBooking',
            entity_id=booking.id,
            changes={
                'action': 'CONFIRM',
                'booking_code': booking.booking_code,
                'old_status': old_status,
                'new_status': MachineBooking.STATUS_CONFIRMED,
                'machine': target_machine.name,
                'operator': target_operator.full_name,
            },
            request=request
        )
        return booking

    @classmethod
    @transaction.atomic
    def dispatch_booking(cls, booking: MachineBooking, user: User, dispatch_notes=None, request=None) -> MachineBooking:
        """
        Transitions booking from CONFIRMED to DISPATCHED.
        Records dispatch time and notes.
        """
        if booking.status != MachineBooking.STATUS_CONFIRMED:
            raise ValidationError(f"Booking must be in CONFIRMED status to dispatch. Current status: '{booking.get_status_display()}'.")

        if not booking.machine:
            raise ValidationError("Cannot dispatch: No machine assigned.")

        if not booking.operator:
            raise ValidationError("Cannot dispatch: No operator assigned.")

        # Re-validate machine and operator availability right before dispatch
        cls.validate_machine_availability(booking.machine, booking.work_date, exclude_booking_id=booking.id)
        cls.validate_operator(booking.operator, booking.machine_type)

        old_status = booking.status
        booking.status = MachineBooking.STATUS_DISPATCHED
        booking.dispatched_at = timezone.now()
        if dispatch_notes:
            booking.dispatch_notes = dispatch_notes
        booking.save()

        log_audit_event(
            user=user,
            action=AuditLog.ACTION_UPDATE,
            entity_type='MachineBooking',
            entity_id=booking.id,
            changes={
                'action': 'DISPATCH',
                'booking_code': booking.booking_code,
                'old_status': old_status,
                'new_status': MachineBooking.STATUS_DISPATCHED,
                'dispatched_at': booking.dispatched_at.isoformat(),
                'dispatch_notes': dispatch_notes,
                'machine': booking.machine.name,
                'operator': booking.operator.full_name,
            },
            request=request
        )
        return booking

    @classmethod
    @transaction.atomic
    def start_work(cls, booking: MachineBooking, user: User, request=None) -> MachineBooking:
        """Transitions booking from DISPATCHED to IN_PROGRESS."""
        if booking.status != MachineBooking.STATUS_DISPATCHED:
            raise ValidationError(f"Booking must be in DISPATCHED status to start work. Current status: '{booking.get_status_display()}'.")

        old_status = booking.status
        booking.status = MachineBooking.STATUS_IN_PROGRESS
        booking.started_at = timezone.now()
        booking.save()

        log_audit_event(
            user=user,
            action=AuditLog.ACTION_UPDATE,
            entity_type='MachineBooking',
            entity_id=booking.id,
            changes={
                'action': 'START_WORK',
                'booking_code': booking.booking_code,
                'old_status': old_status,
                'new_status': MachineBooking.STATUS_IN_PROGRESS,
                'started_at': booking.started_at.isoformat(),
            },
            request=request
        )
        return booking

    @classmethod
    @transaction.atomic
    def complete_work(cls, booking: MachineBooking, user: User, request=None) -> MachineBooking:
        """Transitions booking from IN_PROGRESS to COMPLETED."""
        if booking.status != MachineBooking.STATUS_IN_PROGRESS:
            raise ValidationError(f"Booking must be in IN_PROGRESS status to complete work. Current status: '{booking.get_status_display()}'.")

        old_status = booking.status
        booking.status = MachineBooking.STATUS_COMPLETED
        booking.completed_at = timezone.now()
        booking.save()

        log_audit_event(
            user=user,
            action=AuditLog.ACTION_UPDATE,
            entity_type='MachineBooking',
            entity_id=booking.id,
            changes={
                'action': 'COMPLETE_WORK',
                'booking_code': booking.booking_code,
                'old_status': old_status,
                'new_status': MachineBooking.STATUS_COMPLETED,
                'completed_at': booking.completed_at.isoformat(),
            },
            request=request
        )
        return booking

    @classmethod
    @transaction.atomic
    def cancel_booking(cls, booking: MachineBooking, user: User, cancellation_reason=None, request=None) -> MachineBooking:
        """Cancels a booking if it is not completed."""
        if booking.status == MachineBooking.STATUS_COMPLETED:
            raise ValidationError("Cannot cancel a completed booking.")

        if booking.status == MachineBooking.STATUS_CANCELLED:
            raise ValidationError("Booking is already cancelled.")

        old_status = booking.status
        booking.status = MachineBooking.STATUS_CANCELLED
        booking.cancelled_at = timezone.now()
        if cancellation_reason:
            booking.cancellation_reason = cancellation_reason
        booking.save()

        log_audit_event(
            user=user,
            action=AuditLog.ACTION_UPDATE,
            entity_type='MachineBooking',
            entity_id=booking.id,
            changes={
                'action': 'CANCEL_BOOKING',
                'booking_code': booking.booking_code,
                'old_status': old_status,
                'new_status': MachineBooking.STATUS_CANCELLED,
                'cancelled_at': booking.cancelled_at.isoformat(),
                'cancellation_reason': cancellation_reason,
            },
            request=request
        )
        return booking

    @classmethod
    @transaction.atomic
    def soft_delete_booking(cls, booking: MachineBooking, user: User, request=None) -> bool:
        """Soft deletes a booking."""
        booking.is_deleted = True
        booking.save()

        log_audit_event(
            user=user,
            action=AuditLog.ACTION_SOFT_DELETE,
            entity_type='MachineBooking',
            entity_id=booking.id,
            changes={'booking_code': booking.booking_code, 'is_deleted': True},
            request=request
        )
        return True
