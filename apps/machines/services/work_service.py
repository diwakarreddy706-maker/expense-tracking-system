import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth.models import User

from apps.machines.models import Machine, MachineWorkEntry, RentedHarvesterSettlement
from apps.finance.models import CustomerPayment
from apps.finance.services.settlement_service import CustomerReceivableService
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog

logger = logging.getLogger('expense_tracking.financial')


class WorkService:
    """
    Central Service for Machine Work Entry & Billing Calculations (Phase 12.4).
    Enforces strict mathematical isolation between commercial billing time
    and machine hour-meter tracking.
    """

    @classmethod
    def generate_work_code(cls, date_val=None) -> str:
        """Generates unique sequential work code e.g. WRK-20260816-0001."""
        target_date = date_val or timezone.now().date()
        date_str = target_date.strftime('%Y%m%d')
        prefix = f"WRK-{date_str}-"

        last_entry = MachineWorkEntry.objects.filter(work_code__startswith=prefix).order_by('-id').first()
        if last_entry:
            try:
                seq = int(last_entry.work_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def calculate_harvester_billing(cls, start_time, end_time, break_hours=Decimal('0.00'), hourly_rate=Decimal('0.00')) -> dict:
        """
        Authoritative calculation for Harvester Time-Based Billing.
        Formula:
            elapsed_hours = end_time - start_time
            net_working_hours = elapsed_hours - break_hours
            total_amount = net_working_hours * hourly_rate
        """
        if not start_time or not end_time:
            raise ValidationError("Start time and End time are required for Harvester billing.")

        if end_time <= start_time:
            raise ValidationError("End time must be strictly greater than start time (same-day operation).")

        # Convert to datetime on arbitrary reference day to calculate precise elapsed hours
        start_dt = datetime.combine(datetime.min, start_time)
        end_dt = datetime.combine(datetime.min, end_time)
        elapsed_seconds = (end_dt - start_dt).total_seconds()
        elapsed_hours = (Decimal(str(elapsed_seconds)) / Decimal('3600')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        break_h = Decimal(str(break_hours or '0.00'))
        if break_h < Decimal('0.00'):
            raise ValidationError("Break hours cannot be negative.")

        if break_h >= elapsed_hours:
            raise ValidationError(f"Break hours ({break_h}h) cannot be greater than or equal to elapsed time ({elapsed_hours}h).")

        net_working_hours = (elapsed_hours - break_h).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        rate_h = Decimal(str(hourly_rate or '0.00'))
        if rate_h < Decimal('0.00'):
            raise ValidationError("Hourly rate cannot be negative.")

        total_amount = (net_working_hours * rate_h).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return {
            'elapsed_hours': elapsed_hours,
            'net_working_hours': net_working_hours,
            'hourly_rate': rate_h,
            'total_amount': total_amount,
        }

    @classmethod
    def calculate_tractor_billing(cls, quantity, unit_rate) -> dict:
        """
        Authoritative calculation for Tractor Quantity-Based Billing (Acre/Piece).
        Formula:
            total_amount = quantity * unit_rate
        """
        qty = Decimal(str(quantity or '0.00'))
        rate = Decimal(str(unit_rate or '0.00'))

        if qty <= Decimal('0.00'):
            raise ValidationError("Quantity must be strictly greater than zero.")

        if rate < Decimal('0.00'):
            raise ValidationError("Unit rate cannot be negative.")

        total_amount = (qty * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return {
            'quantity': qty,
            'unit_rate': rate,
            'total_amount': total_amount,
        }

    @classmethod
    def calculate_meter_difference(cls, start_meter, end_meter) -> Decimal:
        """
        Authoritative calculation for machine hour-meter equipment tracking.
        Independent of billing time.
        """
        if start_meter is not None and end_meter is not None:
            sm = Decimal(str(start_meter))
            em = Decimal(str(end_meter))
            if em < sm:
                raise ValidationError(f"End meter ({em}) cannot be lower than start meter ({sm}).")
            return (em - sm).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')

    @classmethod
    @transaction.atomic
    def create_work_entry(
        cls,
        *,
        work_date,
        machine: Machine,
        customer,
        operator=None,
        booking=None,
        billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
        start_time=None,
        end_time=None,
        break_hours=Decimal('0.00'),
        hourly_rate=Decimal('0.00'),
        quantity=Decimal('0.00'),
        unit_rate=Decimal('0.00'),
        start_meter=None,
        end_meter=None,
        manual_bill_no=None,
        advance_amount=Decimal('0.00'),
        udhar_amount=Decimal('0.00'),
        payment_mode='UDHAR',
        payment_account=None,
        fuel_liters=Decimal('0.00'),
        fuel_rate=Decimal('95.00'),
        notes=None,
        created_by: User,
        request=None
    ) -> MachineWorkEntry:
        """
        Creates and authoritatively validates a MachineWorkEntry.
        Strictly isolated from financial ledger transactions.
        """
        work_code = cls.generate_work_code(work_date)
        meter_diff = cls.calculate_meter_difference(start_meter, end_meter)

        if billing_type == MachineWorkEntry.BILLING_TIME_HOURLY:
            calc = cls.calculate_harvester_billing(
                start_time=start_time,
                end_time=end_time,
                break_hours=break_hours,
                hourly_rate=hourly_rate
            )
            net_working_hours = calc['net_working_hours']
            hourly_rate = calc['hourly_rate']
            total_amount = calc['total_amount']
            quantity = Decimal('0.00')
            unit_rate = Decimal('0.00')
        elif billing_type in [MachineWorkEntry.BILLING_ACRE, MachineWorkEntry.BILLING_PIECE]:
            calc = cls.calculate_tractor_billing(
                quantity=quantity,
                unit_rate=unit_rate
            )
            total_amount = calc['total_amount']
            quantity = calc['quantity']
            unit_rate = calc['unit_rate']
            start_time = None
            end_time = None
            break_hours = Decimal('0.00')
            net_working_hours = Decimal('0.00')
            hourly_rate = Decimal('0.00')
        else:
            raise ValidationError(f"Invalid billing type: {billing_type}")

        # Instantiate model
        # Save work entry with billing and advance metadata
        entry = MachineWorkEntry(
            booking=booking,
            work_code=work_code,
            work_date=work_date,
            machine=machine,
            customer=customer,
            operator=operator,
            billing_type=billing_type,
            start_time=start_time,
            end_time=end_time,
            break_hours=break_hours,
            net_working_hours=net_working_hours,
            hourly_rate=hourly_rate,
            quantity=quantity,
            unit_rate=unit_rate,
            total_amount=total_amount,
            start_meter=start_meter,
            end_meter=end_meter,
            meter_difference=meter_diff,
            manual_bill_no=manual_bill_no,
            advance_amount=advance_amount,
            udhar_amount=udhar_amount,
            payment_mode=payment_mode,
            notes=notes,
            created_by=created_by
        )
        entry.save()

        # Step 4: Farmer Credit Ledger (Udhar) Integration
        if total_amount > Decimal('0.00'):
            try:
                rcv = CustomerReceivableService.create_receivable(
                    user=created_by,
                    customer=customer,
                    total_amount=total_amount,
                    bill_date=work_date,
                    invoice_no=manual_bill_no or work_code,
                    notes=f"Harvesting Work: {work_code} ({machine.name})",
                    request=request
                )
                entry.receivable = rcv
                entry.save(update_fields=['receivable'])

                # If Advance was collected on site, record receipt into selected Account
                if advance_amount > Decimal('0.00') and payment_account:
                    pay_method = CustomerPayment.METHOD_CASH if payment_mode == 'CASH' else (
                        CustomerPayment.METHOD_UPI if payment_mode == 'UPI' else CustomerPayment.METHOD_CASH
                    )
                    CustomerReceivableService.record_payment(
                        user=created_by,
                        receivable_id=rcv.id,
                        amount=advance_amount,
                        account=payment_account,
                        payment_method=pay_method,
                        payment_date=work_date,
                        reference_no=f"ADV-{work_code}",
                        notes=f"Advance collected on-site for harvesting bill {work_code}",
                        request=request
                    )
            except Exception as e:
                logger.warning(f"Receivable creation warning for {work_code}: {e}")

        # Step 5: Automated Rented Harvester Settlement
        if machine.ownership_type == Machine.OWNERSHIP_RENTED and machine.rented_owner:
            owner = machine.rented_owner
            comm_pct = owner.commission_percentage or Decimal('10.00')
            comm_amt = (total_amount * comm_pct / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            f_liters = Decimal(str(fuel_liters or '0.00'))
            f_rate = Decimal(str(fuel_rate or '95.00'))
            diesel_amt = (f_liters * f_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            net_pay = (total_amount - comm_amt - diesel_amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            settle_code = f"SETTLE-{work_code.replace('WRK-', '')}"
            RentedHarvesterSettlement.objects.create(
                settlement_code=settle_code,
                work_entry=entry,
                owner=owner,
                gross_earnings=total_amount,
                commission_percentage=comm_pct,
                commission_amount=comm_amt,
                diesel_liters=f_liters,
                diesel_amount=diesel_amt,
                net_payable=net_pay,
                notes=f"Auto-generated for harvesting session {work_code}"
            )

        # Update machine's current meter reading if end_meter is higher
        if end_meter is not None and end_meter > machine.current_meter_reading:
            machine.current_meter_reading = end_meter
            machine.save(update_fields=['current_meter_reading', 'updated_at'])

        # Audit Trail
        log_audit_event(
            user=created_by,
            action=AuditLog.ACTION_CREATE,
            entity_type='MachineWorkEntry',
            entity_id=entry.id,
            changes={
                'work_code': entry.work_code,
                'booking_id': booking.id if booking else None,
                'machine': machine.name,
                'customer': customer.name,
                'operator': operator.full_name if operator else None,
                'billing_type': billing_type,
                'net_working_hours': str(net_working_hours),
                'quantity': str(quantity),
                'total_amount': str(total_amount),
                'advance_amount': str(advance_amount),
                'udhar_amount': str(udhar_amount),
                'meter_difference': str(meter_diff)
            },
            request=request
        )
        return entry

    @classmethod
    @transaction.atomic
    def update_work_entry(
        cls,
        entry: MachineWorkEntry,
        *,
        work_date,
        machine: Machine,
        customer,
        operator=None,
        booking=None,
        billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
        start_time=None,
        end_time=None,
        break_hours=Decimal('0.00'),
        hourly_rate=Decimal('0.00'),
        quantity=Decimal('0.00'),
        unit_rate=Decimal('0.00'),
        start_meter=None,
        end_meter=None,
        notes=None,
        user: User,
        request=None
    ) -> MachineWorkEntry:
        """
        Updates and recalculates an existing MachineWorkEntry.
        """
        meter_diff = cls.calculate_meter_difference(start_meter, end_meter)

        if billing_type == MachineWorkEntry.BILLING_TIME_HOURLY:
            calc = cls.calculate_harvester_billing(
                start_time=start_time,
                end_time=end_time,
                break_hours=break_hours,
                hourly_rate=hourly_rate
            )
            net_working_hours = calc['net_working_hours']
            hourly_rate = calc['hourly_rate']
            total_amount = calc['total_amount']
            quantity = Decimal('0.00')
            unit_rate = Decimal('0.00')
        elif billing_type in [MachineWorkEntry.BILLING_ACRE, MachineWorkEntry.BILLING_PIECE]:
            calc = cls.calculate_tractor_billing(
                quantity=quantity,
                unit_rate=unit_rate
            )
            total_amount = calc['total_amount']
            quantity = calc['quantity']
            unit_rate = calc['unit_rate']
            start_time = None
            end_time = None
            break_hours = Decimal('0.00')
            net_working_hours = Decimal('0.00')
            hourly_rate = Decimal('0.00')
        else:
            raise ValidationError(f"Invalid billing type: {billing_type}")

        if booking is not None:
            entry.booking = booking
        entry.work_date = work_date
        entry.machine = machine
        entry.customer = customer
        entry.operator = operator
        entry.billing_type = billing_type
        entry.start_time = start_time
        entry.end_time = end_time
        entry.break_hours = break_hours
        entry.net_working_hours = net_working_hours
        entry.hourly_rate = hourly_rate
        entry.quantity = quantity
        entry.unit_rate = unit_rate
        entry.total_amount = total_amount
        entry.start_meter = start_meter
        entry.end_meter = end_meter
        entry.meter_difference = meter_diff
        entry.notes = notes
        entry.save()

        # Update machine meter if end_meter is higher
        if end_meter is not None:
            em = Decimal(str(end_meter))
            locked_machine = Machine.objects.select_for_update().get(id=machine.id)
            if em > locked_machine.current_meter_reading:
                locked_machine.current_meter_reading = em
                locked_machine.save(update_fields=['current_meter_reading', 'updated_at'])

        # Audit Logging
        log_audit_event(
            user=user,
            action=AuditLog.ACTION_UPDATE,
            entity_type='MachineWorkEntry',
            entity_id=entry.id,
            changes={
                'work_code': entry.work_code,
                'total_amount': str(total_amount),
                'net_working_hours': str(net_working_hours),
                'meter_difference': str(meter_diff),
            },
            request=request
        )

        return entry

    @classmethod
    @transaction.atomic
    def soft_delete_work_entry(cls, entry: MachineWorkEntry, user: User, request=None) -> None:
        """Soft deletes a MachineWorkEntry with audit logging."""
        entry.is_deleted = True
        entry.save(update_fields=['is_deleted', 'updated_at'])

        log_audit_event(
            user=user,
            action=AuditLog.ACTION_SOFT_DELETE,
            entity_type='MachineWorkEntry',
            entity_id=entry.id,
            changes={'work_code': entry.work_code, 'is_deleted': True},
            request=request
        )
