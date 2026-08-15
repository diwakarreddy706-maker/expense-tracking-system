"""
Authoritative Employee Financial & Wage Service Layer.
Enforces Rule 1 (Decimal precision), Rule 4 (Accrual vs Payment distinction),
Rule 10 (Single Authoritative Source: account_transactions for money movements),
and atomic financial settlements.
"""

from decimal import Decimal
from typing import Optional, Dict, Any
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from apps.employees.models import Employee, EmployeePayment, EmployeeCompensation
from apps.finance.models import Account, AccountTransaction
from apps.finance.services.balance_service import FinancialCalculationService
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog


class EmployeeFinancialService:
    """
    Central service for managing employee wage accruals, advance payouts,
    salary settlements, bonus rewards, compensation rates, and employee ledger balances.
    """

    @classmethod
    def generate_payment_code(cls, date_val=None) -> str:
        """Generates unique sequential payment code e.g. EMP-PAY-20260815-0001."""
        target_date = date_val or timezone.now().date()
        date_str = target_date.strftime('%Y%m%d')
        prefix = f"EMP-PAY-{date_str}-"

        last_entry = EmployeePayment.objects.filter(payment_code__startswith=prefix).order_by('-id').first()
        if last_entry:
            try:
                seq = int(last_entry.payment_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def calculate_employee_balances(cls, employee_id: int) -> Dict[str, Decimal]:
        """
        Authoritative calculation of an employee's accrued wages, paid advances,
        settlements, bonuses, and net outstanding payable balance.
        """
        zero = Decimal('0.00')

        payments = EmployeePayment.objects.filter(
            employee_id=employee_id,
            is_reversed=False,
            is_deleted=False
        )

        accruals = payments.filter(payment_type=EmployeePayment.TYPE_SALARY_ACCRUAL).aggregate(s=Sum('amount'))['s'] or zero
        advances = payments.filter(payment_type=EmployeePayment.TYPE_ADVANCE_PAYOUT).aggregate(s=Sum('amount'))['s'] or zero
        settlements = payments.filter(payment_type=EmployeePayment.TYPE_SALARY_SETTLEMENT).aggregate(s=Sum('amount'))['s'] or zero
        bonuses = payments.filter(payment_type=EmployeePayment.TYPE_BONUS).aggregate(s=Sum('amount'))['s'] or zero

        total_earned = accruals + bonuses
        total_disbursed = advances + settlements + bonuses
        net_outstanding = (accruals + bonuses) - (advances + settlements)

        return {
            'total_accruals': accruals,
            'total_advances': advances,
            'total_settlements': settlements,
            'total_bonuses': bonuses,
            'total_earned': total_earned,
            'total_disbursed': total_disbursed,
            'net_outstanding': net_outstanding,
        }

    @classmethod
    def validate_compensation_dates(
        cls,
        employee_id: int,
        wage_type: str,
        effective_from,
        effective_to=None,
        exclude_id: Optional[int] = None
    ):
        """
        Validates that there are no overlapping active date ranges for the same (employee, wage_type).
        """
        if effective_to and effective_to < effective_from:
            raise ValidationError({"effective_to": "Effective end date cannot be earlier than start date."})

        existing_qs = EmployeeCompensation.objects.filter(
            employee_id=employee_id,
            wage_type=wage_type,
            is_active=True
        )
        if exclude_id:
            existing_qs = existing_qs.exclude(id=exclude_id)

        for comp in existing_qs:
            comp_start = comp.effective_from
            comp_end = comp.effective_to

            # Overlap condition: (StartA <= EndB) and (EndA >= StartB)
            a_starts_before_b_ends = (comp_end is None) or (effective_from <= comp_end)
            a_ends_after_b_starts = (effective_to is None) or (effective_to >= comp_start)

            if a_starts_before_b_ends and a_ends_after_b_starts:
                raise ValidationError({
                    "effective_from": f"An active compensation structure for '{comp.get_wage_type_display()}' already exists for period ({comp_start} to {comp_end or 'Present'}). Close or deactivate it before adding an overlapping rate."
                })

    @classmethod
    def add_compensation(
        cls,
        user: User,
        employee: Employee,
        wage_type: str,
        rate: Decimal,
        effective_from = None,
        effective_to = None,
        notes: Optional[str] = None,
        request = None
    ) -> EmployeeCompensation:
        """
        Creates a new EmployeeCompensation record.
        Enforces Decimal precision, validity, and overlap prevention.
        Does NOT move money or create AccountTransactions.
        """
        profile = getattr(user, 'profile', None)
        is_owner = getattr(profile, 'is_owner', False) if profile else False
        is_accountant = getattr(profile, 'is_accountant', False) if profile else False
        if not is_owner and not is_accountant and not getattr(user, 'is_superuser', False):
            raise ValidationError("Managing employee compensation rates is restricted to Owners and Accountants.")

        if not employee or employee.is_deleted:
            raise ValidationError({"employee": "A valid and active employee record is required."})

        if wage_type not in dict(EmployeeCompensation.WAGE_TYPE_CHOICES):
            raise ValidationError({"wage_type": "Invalid compensation wage type."})

        if not isinstance(rate, Decimal):
            try:
                rate = Decimal(str(rate))
            except Exception:
                raise ValidationError({"rate": "Invalid monetary amount."})

        rate = rate.quantize(Decimal('0.01'))
        if rate <= Decimal('0.00'):
            raise ValidationError({"rate": "Compensation rate must be strictly greater than zero."})

        start_date = effective_from or timezone.now().date()
        cls.validate_compensation_dates(
            employee_id=employee.id,
            wage_type=wage_type,
            effective_from=start_date,
            effective_to=effective_to
        )

        with transaction.atomic():
            comp = EmployeeCompensation.objects.create(
                employee=employee,
                wage_type=wage_type,
                rate=rate,
                effective_from=start_date,
                effective_to=effective_to,
                is_active=True,
                notes=notes
            )

            log_audit_event(
                user,
                AuditLog.ACTION_CREATE,
                'EmployeeCompensation',
                comp.id,
                changes={
                    'employee': employee.full_name,
                    'wage_type': wage_type,
                    'rate': str(rate),
                    'effective_from': str(start_date),
                    'effective_to': str(effective_to) if effective_to else None
                },
                request=request
            )

            return comp

    @classmethod
    def update_compensation(
        cls,
        user: User,
        compensation_id: int,
        rate: Decimal,
        effective_from = None,
        effective_to = None,
        is_active: bool = True,
        notes: Optional[str] = None,
        request = None
    ) -> EmployeeCompensation:
        """
        Updates an existing compensation record.
        Logs audit changes with old vs new rate.
        """
        profile = getattr(user, 'profile', None)
        is_owner = getattr(profile, 'is_owner', False) if profile else False
        is_accountant = getattr(profile, 'is_accountant', False) if profile else False
        if not is_owner and not is_accountant and not getattr(user, 'is_superuser', False):
            raise ValidationError("Managing employee compensation rates is restricted to Owners and Accountants.")

        comp = EmployeeCompensation.objects.get(id=compensation_id)
        old_rate = comp.rate
        old_status = comp.is_active

        if not isinstance(rate, Decimal):
            try:
                rate = Decimal(str(rate))
            except Exception:
                raise ValidationError({"rate": "Invalid monetary amount."})

        rate = rate.quantize(Decimal('0.01'))
        if rate <= Decimal('0.00'):
            raise ValidationError({"rate": "Compensation rate must be strictly greater than zero."})

        start_date = effective_from or comp.effective_from
        if is_active:
            cls.validate_compensation_dates(
                employee_id=comp.employee_id,
                wage_type=comp.wage_type,
                effective_from=start_date,
                effective_to=effective_to,
                exclude_id=comp.id
            )

        with transaction.atomic():
            comp.rate = rate
            comp.effective_from = start_date
            comp.effective_to = effective_to
            comp.is_active = is_active
            comp.notes = notes
            comp.save()

            log_audit_event(
                user,
                AuditLog.ACTION_UPDATE,
                'EmployeeCompensation',
                comp.id,
                changes={
                    'employee': comp.employee.full_name,
                    'wage_type': comp.wage_type,
                    'rate': {'old': str(old_rate), 'new': str(rate)},
                    'is_active': {'old': old_status, 'new': is_active},
                    'effective_from': str(start_date),
                    'effective_to': str(effective_to) if effective_to else None
                },
                request=request
            )

            return comp

    @classmethod
    def deactivate_compensation(
        cls,
        user: User,
        compensation_id: int,
        effective_to = None,
        request = None
    ) -> EmployeeCompensation:
        """
        Deactivates a compensation record without deleting historical data.
        """
        profile = getattr(user, 'profile', None)
        is_owner = getattr(profile, 'is_owner', False) if profile else False
        is_accountant = getattr(profile, 'is_accountant', False) if profile else False
        if not is_owner and not is_accountant and not getattr(user, 'is_superuser', False):
            raise ValidationError("Managing employee compensation rates is restricted to Owners and Accountants.")

        comp = EmployeeCompensation.objects.get(id=compensation_id)
        end_date = effective_to or timezone.now().date()

        with transaction.atomic():
            comp.is_active = False
            if not comp.effective_to:
                comp.effective_to = end_date
            comp.save()

            log_audit_event(
                user,
                AuditLog.ACTION_UPDATE,
                'EmployeeCompensation',
                comp.id,
                changes={
                    'action': 'DEACTIVATE',
                    'employee': comp.employee.full_name,
                    'wage_type': comp.wage_type,
                    'effective_to': str(comp.effective_to)
                },
                request=request
            )

            return comp

    @classmethod
    def record_salary_accrual(
        cls,
        user: User,
        employee: Employee,
        amount: Optional[Decimal] = None,
        compensation: Optional[EmployeeCompensation] = None,
        units_logged: Optional[Decimal] = None,
        date_val = None,
        reference_no: Optional[str] = None,
        notes: Optional[str] = None,
        request = None
    ) -> EmployeePayment:
        """
        Records wage/salary liability earned by staff.
        Supports linking to an authoritative EmployeeCompensation rate and units_logged
        (e.g., 25 days * ₹200.00/day = ₹5,000.00).
        RULE 4: Does NOT move cash/bank money. No AccountTransaction is created.
        """
        if not employee or employee.is_deleted:
            raise ValidationError({"employee": "A valid and active employee record is required."})

        # If compensation is specified, validate it belongs to this employee
        if compensation:
            if compensation.employee_id != employee.id:
                raise ValidationError({"compensation": "Selected compensation structure does not belong to this employee."})
            if not compensation.is_active:
                raise ValidationError({"compensation": "Selected compensation structure is inactive."})

        # Calculate amount if units_logged and compensation are provided
        if units_logged is not None and compensation is not None:
            if not isinstance(units_logged, Decimal):
                try:
                    units_logged = Decimal(str(units_logged))
                except Exception:
                    raise ValidationError({"units_logged": "Invalid units logged."})
            units_logged = units_logged.quantize(Decimal('0.01'))
            if units_logged <= Decimal('0.00'):
                raise ValidationError({"units_logged": "Units logged must be strictly greater than zero."})

            calculated_amount = (compensation.rate * units_logged).quantize(Decimal('0.01'))
            if amount is None:
                amount = calculated_amount

        if amount is None:
            raise ValidationError({"amount": "An accrual amount or valid compensation with units is required."})

        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except Exception:
                raise ValidationError({"amount": "Invalid monetary amount."})

        amount = amount.quantize(Decimal('0.01'))
        if amount <= Decimal('0.00'):
            raise ValidationError({"amount": "Accrual amount must be strictly greater than zero."})

        entry_date = date_val or timezone.now().date()

        with transaction.atomic():
            code = cls.generate_payment_code(entry_date)

            payment = EmployeePayment.objects.create(
                payment_code=code,
                employee=employee,
                compensation=compensation,
                units_logged=units_logged,
                payment_type=EmployeePayment.TYPE_SALARY_ACCRUAL,
                amount=amount,
                date=entry_date,
                account=None,
                linked_ledger_transaction=None,
                reference_no=reference_no,
                notes=notes,
                created_by=user
            )

            audit_changes: Dict[str, Any] = {
                'payment_code': payment.payment_code,
                'type': 'SALARY_ACCRUAL',
                'employee': employee.full_name,
                'amount': str(amount)
            }
            if compensation:
                audit_changes['compensation'] = f"{compensation.get_wage_type_display()} (₹{compensation.rate})"
            if units_logged:
                audit_changes['units_logged'] = str(units_logged)

            log_audit_event(
                user,
                AuditLog.ACTION_CREATE,
                'EmployeePayment',
                payment.id,
                changes=audit_changes,
                request=request
            )

            return payment

    @classmethod
    def record_payout(
        cls,
        user: User,
        employee: Employee,
        payment_type: str,
        amount: Decimal,
        account: Account,
        payment_method: str = EmployeePayment.METHOD_CASH,
        date_val = None,
        reference_no: Optional[str] = None,
        notes: Optional[str] = None,
        request = None
    ) -> EmployeePayment:
        """
        Atomically records an actual money payout (ADVANCE_PAYOUT, SALARY_SETTLEMENT, BONUS).
        Creates an authoritative AccountTransaction and updates account balance.
        """
        if payment_type not in [
            EmployeePayment.TYPE_ADVANCE_PAYOUT,
            EmployeePayment.TYPE_SALARY_SETTLEMENT,
            EmployeePayment.TYPE_BONUS
        ]:
            raise ValidationError({"payment_type": "Invalid payout payment type."})

        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except Exception:
                raise ValidationError({"amount": "Invalid monetary amount."})

        amount = amount.quantize(Decimal('0.01'))
        if amount <= Decimal('0.00'):
            raise ValidationError({"amount": "Payout amount must be strictly greater than zero."})

        if not employee or employee.is_deleted:
            raise ValidationError({"employee": "A valid employee record is required."})

        if not account or account.is_deleted or not account.is_active:
            raise ValidationError({"account": "A valid and active business account is required for payouts."})

        if payment_method not in dict(EmployeePayment.PAYMENT_METHOD_CHOICES):
            raise ValidationError({"payment_method": "Invalid payment method."})

        entry_date = date_val or timezone.now().date()

        with transaction.atomic():
            locked_account = Account.objects.select_for_update().get(id=account.id)
            code = cls.generate_payment_code(entry_date)

            # 1. Create central ledger debit transaction
            desc = f"Staff Payout ({dict(EmployeePayment.PAYMENT_TYPE_CHOICES).get(payment_type)}): {employee.full_name} ({code})"
            if notes:
                desc += f" - {notes}"

            ledger_tx = AccountTransaction.objects.create(
                account=locked_account,
                transaction_date=entry_date,
                transaction_type=AccountTransaction.TYPE_EMPLOYEE_PAYMENT,
                direction=AccountTransaction.DIRECTION_DEBIT,
                amount=amount,
                reference_type='EmployeePayment',
                description=desc,
                created_by=user
            )

            # 2. Recalculate authoritative account balance
            FinancialCalculationService.recalculate_account_balance(locked_account.id)

            # 3. Create EmployeePayment record linked 1:1 to the ledger transaction
            payment = EmployeePayment.objects.create(
                payment_code=code,
                employee=employee,
                payment_type=payment_type,
                amount=amount,
                date=entry_date,
                account=locked_account,
                payment_method=payment_method,
                linked_ledger_transaction=ledger_tx,
                reference_no=reference_no,
                notes=notes,
                created_by=user
            )

            # Set reference_id on ledger transaction
            ledger_tx.reference_id = payment.id
            ledger_tx.save(update_fields=['reference_id'])

            # 4. Log Audit Event
            log_audit_event(
                user,
                AuditLog.ACTION_PAYMENT,
                'EmployeePayment',
                payment.id,
                changes={
                    'payment_code': payment.payment_code,
                    'type': payment_type,
                    'employee': employee.full_name,
                    'amount': str(amount),
                    'account': locked_account.account_name,
                    'ledger_tx': ledger_tx.id
                },
                request=request
            )

            return payment

    @classmethod
    def reverse_payment(
        cls,
        payment_id: int,
        user: User,
        reason: str,
        request = None
    ) -> EmployeePayment:
        """
        Reverses an employee payment or wage accrual under Rule 10 (preserving history).
        """
        profile = getattr(user, 'profile', None)
        is_owner = getattr(profile, 'is_owner', False) if profile else False
        if not is_owner and not getattr(user, 'is_superuser', False):
            raise ValidationError("Reversing employee financial transactions is restricted to system Owners.")

        if not reason or len(reason.strip()) < 5:
            raise ValidationError({"reason": "A valid explanation (minimum 5 characters) is required for financial reversals."})

        with transaction.atomic():
            payment = EmployeePayment.objects.select_for_update().get(id=payment_id, is_deleted=False)

            if payment.is_reversed:
                raise ValidationError("This employee payment has already been reversed.")

            payment.is_reversed = True
            payment.save(update_fields=['is_reversed', 'updated_at'])

            # If money moved (linked to an AccountTransaction), post a compensatory credit reversal
            if payment.linked_ledger_transaction and payment.account:
                locked_account = Account.objects.select_for_update().get(id=payment.account.id)

                AccountTransaction.objects.create(
                    account=locked_account,
                    transaction_date=timezone.now().date(),
                    transaction_type=AccountTransaction.TYPE_REVERSAL,
                    direction=AccountTransaction.DIRECTION_CREDIT,
                    amount=payment.amount,
                    reference_type='EmployeePayment',
                    reference_id=payment.id,
                    description=f"Reversal of Employee Payment {payment.payment_code} ({payment.employee.full_name}): {reason.strip()}",
                    created_by=user
                )

                FinancialCalculationService.recalculate_account_balance(locked_account.id)

            log_audit_event(
                user,
                AuditLog.ACTION_REVERSAL,
                'EmployeePayment',
                payment.id,
                changes={'payment_code': payment.payment_code, 'reason': reason.strip(), 'amount': str(payment.amount)},
                request=request
            )

            return payment
