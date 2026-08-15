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

from apps.employees.models import Employee, EmployeePayment
from apps.finance.models import Account, AccountTransaction
from apps.finance.services.balance_service import FinancialCalculationService
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog


class EmployeeFinancialService:
    """
    Central service for managing employee wage accruals, advance payouts,
    salary settlements, bonus rewards, and employee ledger balances.
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
    def record_salary_accrual(
        cls,
        user: User,
        employee: Employee,
        amount: Decimal,
        date_val = None,
        reference_no: Optional[str] = None,
        notes: Optional[str] = None,
        request = None
    ) -> EmployeePayment:
        """
        Records wage/salary liability earned by staff.
        RULE 4: Does NOT move cash/bank money. No AccountTransaction is created.
        """
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except Exception:
                raise ValidationError({"amount": "Invalid monetary amount."})

        amount = amount.quantize(Decimal('0.01'))
        if amount <= Decimal('0.00'):
            raise ValidationError({"amount": "Accrual amount must be strictly greater than zero."})

        if not employee or employee.is_deleted:
            raise ValidationError({"employee": "A valid and active employee record is required."})

        entry_date = date_val or timezone.now().date()

        with transaction.atomic():
            code = cls.generate_payment_code(entry_date)

            payment = EmployeePayment.objects.create(
                payment_code=code,
                employee=employee,
                payment_type=EmployeePayment.TYPE_SALARY_ACCRUAL,
                amount=amount,
                date=entry_date,
                account=None,
                linked_ledger_transaction=None,
                reference_no=reference_no,
                notes=notes,
                created_by=user
            )

            log_audit_event(
                user,
                AuditLog.ACTION_CREATE,
                'EmployeePayment',
                payment.id,
                changes={
                    'payment_code': payment.payment_code,
                    'type': 'SALARY_ACCRUAL',
                    'employee': employee.full_name,
                    'amount': str(amount)
                },
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
        if not user.profile.is_owner and not user.is_superuser:
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
