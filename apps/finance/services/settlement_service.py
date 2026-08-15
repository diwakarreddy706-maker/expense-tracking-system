"""
Authoritative Customer Receivables & Supplier Payables Service Layer.
Enforces Rule 1 (Decimal precision), Rule 10 (Single Authoritative Source: account_transactions),
Overpayment protection, concurrency safety with select_for_update, atomic settlements, and reversals.
"""

from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from apps.finance.models import (
    Account, AccountTransaction,
    Customer, Supplier,
    Receivable, CustomerPayment,
    Payable, SupplierPayment
)
from apps.finance.services.balance_service import FinancialCalculationService
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog


class CustomerReceivableService:
    """
    Service managing Customer Receivables (Money owed to business)
    and Customer Payment Settlements (Account Inflow / RECEIVABLE_PAYMENT).
    """

    @classmethod
    def generate_receivable_code(cls, date_val=None) -> str:
        """Generates unique sequential receivable code e.g. RCV-20260815-0001."""
        target_date = date_val or timezone.now().date()
        date_str = target_date.strftime('%Y%m%d')
        prefix = f"RCV-{date_str}-"

        last_entry = Receivable.objects.filter(receivable_code__startswith=prefix).order_by('-id').first()
        if last_entry:
            try:
                seq = int(last_entry.receivable_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def generate_payment_code(cls, date_val=None) -> str:
        """Generates unique sequential payment code e.g. CPAY-20260815-0001."""
        target_date = date_val or timezone.now().date()
        date_str = target_date.strftime('%Y%m%d')
        prefix = f"CPAY-{date_str}-"

        last_entry = CustomerPayment.objects.filter(payment_code__startswith=prefix).order_by('-id').first()
        if last_entry:
            try:
                seq = int(last_entry.payment_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def create_receivable(
        cls,
        user: User,
        customer: Customer,
        total_amount: Decimal,
        bill_date = None,
        due_date = None,
        invoice_no: Optional[str] = None,
        notes: Optional[str] = None,
        request = None
    ) -> Receivable:
        """Creates a new Customer Receivable (Billed Inflow obligation)."""
        if not isinstance(total_amount, Decimal):
            try:
                total_amount = Decimal(str(total_amount))
            except Exception:
                raise ValidationError({"total_amount": "Invalid monetary amount."})

        total_amount = total_amount.quantize(Decimal('0.01'))
        if total_amount <= Decimal('0.00'):
            raise ValidationError({"total_amount": "Receivable total amount must be strictly greater than 0.00."})

        if not customer or customer.is_deleted or customer.status != Customer.STATUS_ACTIVE:
            raise ValidationError({"customer": "A valid and active customer is required."})

        entry_date = bill_date or timezone.now().date()

        if due_date and due_date < entry_date:
            raise ValidationError({"due_date": "Due date cannot be before bill date."})

        with transaction.atomic():
            code = cls.generate_receivable_code(entry_date)

            receivable = Receivable.objects.create(
                receivable_code=code,
                customer=customer,
                invoice_no=invoice_no,
                bill_date=entry_date,
                due_date=due_date,
                total_amount=total_amount,
                received_amount=Decimal('0.00'),
                status=Receivable.STATUS_UNPAID,
                notes=notes,
                created_by=user
            )

            log_audit_event(
                user,
                AuditLog.ACTION_CREATE,
                'Receivable',
                receivable.id,
                changes={
                    'receivable_code': receivable.receivable_code,
                    'customer': customer.name,
                    'total_amount': str(total_amount)
                },
                request=request
            )

            return receivable

    @classmethod
    def record_payment(
        cls,
        user: User,
        receivable_id: int,
        amount: Decimal,
        account: Account,
        payment_method: str = CustomerPayment.METHOD_CASH,
        payment_date = None,
        reference_no: Optional[str] = None,
        notes: Optional[str] = None,
        request = None
    ) -> CustomerPayment:
        """
        Atomically records a customer payment settlement.
        Locks receivable row with select_for_update to prevent concurrent overpayment.
        Creates an AccountTransaction (CREDIT / RECEIVABLE_PAYMENT) and updates account balance.
        """
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except Exception:
                raise ValidationError({"amount": "Invalid monetary amount."})

        amount = amount.quantize(Decimal('0.01'))
        if amount <= Decimal('0.00'):
            raise ValidationError({"amount": "Payment amount must be strictly greater than 0.00."})

        if not account or account.is_deleted or not account.is_active:
            raise ValidationError({"account": "A valid and active account is required to deposit funds."})

        if payment_method not in dict(CustomerPayment.PAYMENT_METHOD_CHOICES):
            raise ValidationError({"payment_method": "Invalid payment method."})

        entry_date = payment_date or timezone.now().date()

        with transaction.atomic():
            # Concurrency protection: Lock receivable and account rows
            receivable = Receivable.objects.select_for_update().get(id=receivable_id, is_deleted=False)
            locked_account = Account.objects.select_for_update().get(id=account.id)

            if receivable.is_reversed:
                raise ValidationError("Cannot settle a reversed receivable.")

            outstanding = (receivable.total_amount - receivable.received_amount).quantize(Decimal('0.01'))

            # Overpayment protection (Server-Side)
            if amount > outstanding:
                raise ValidationError({
                    "amount": f"Payment amount (₹{amount}) exceeds outstanding balance (₹{outstanding}). Overpayment is rejected."
                })

            new_received = (receivable.received_amount + amount).quantize(Decimal('0.01'))
            receivable.received_amount = new_received

            if new_received >= receivable.total_amount:
                receivable.status = Receivable.STATUS_PAID
            else:
                receivable.status = Receivable.STATUS_PARTIAL

            receivable.save(update_fields=['received_amount', 'status', 'updated_at'])

            code = cls.generate_payment_code(entry_date)

            # 1. Create central ledger CREDIT transaction (Inflow into account)
            desc = f"Customer Receipt ({receivable.customer.name}): {receivable.receivable_code} ({code})"
            if notes:
                desc += f" - {notes}"

            ledger_tx = AccountTransaction.objects.create(
                account=locked_account,
                transaction_date=entry_date,
                transaction_type=AccountTransaction.TYPE_RECEIVABLE_PAYMENT,
                direction=AccountTransaction.DIRECTION_CREDIT,
                amount=amount,
                reference_type='CustomerPayment',
                description=desc,
                created_by=user
            )

            # 2. Recalculate authoritative account balance
            FinancialCalculationService.recalculate_account_balance(locked_account.id)

            # 3. Create CustomerPayment record
            payment = CustomerPayment.objects.create(
                payment_code=code,
                receivable=receivable,
                account=locked_account,
                payment_date=entry_date,
                amount=amount,
                payment_method=payment_method,
                linked_ledger_transaction=ledger_tx,
                reference_no=reference_no,
                notes=notes,
                created_by=user
            )

            # Link reference_id on ledger transaction
            ledger_tx.reference_id = payment.id
            ledger_tx.save(update_fields=['reference_id'])

            # 4. Audit Log
            log_audit_event(
                user,
                AuditLog.ACTION_PAYMENT,
                'CustomerPayment',
                payment.id,
                changes={
                    'payment_code': payment.payment_code,
                    'receivable': receivable.receivable_code,
                    'amount': str(amount),
                    'account': locked_account.account_name,
                    'remaining_outstanding': str(receivable.outstanding_amount)
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
    ) -> CustomerPayment:
        """
        Reverses a customer payment (Owner only).
        Restores receivable outstanding amount and posts a compensatory DEBIT reversal ledger transaction.
        """
        if not user.profile.is_owner and not user.is_superuser:
            raise ValidationError("Reversing customer payments is restricted to system Owners.")

        if not reason or len(reason.strip()) < 5:
            raise ValidationError({"reason": "A valid explanation (minimum 5 characters) is required for financial reversals."})

        with transaction.atomic():
            payment = CustomerPayment.objects.select_for_update().get(id=payment_id, is_deleted=False)

            if payment.is_reversed:
                raise ValidationError("This customer payment has already been reversed.")

            receivable = Receivable.objects.select_for_update().get(id=payment.receivable_id)
            locked_account = Account.objects.select_for_update().get(id=payment.account_id)

            payment.is_reversed = True
            payment.save(update_fields=['is_reversed'])

            # Restore receivable balance
            new_received = max(Decimal('0.00'), receivable.received_amount - payment.amount)
            receivable.received_amount = new_received
            if new_received == Decimal('0.00'):
                receivable.status = Receivable.STATUS_UNPAID
            else:
                receivable.status = Receivable.STATUS_PARTIAL
            receivable.save(update_fields=['received_amount', 'status', 'updated_at'])

            # Compensatory DEBIT reversal transaction
            AccountTransaction.objects.create(
                account=locked_account,
                transaction_date=timezone.now().date(),
                transaction_type=AccountTransaction.TYPE_REVERSAL,
                direction=AccountTransaction.DIRECTION_DEBIT,
                amount=payment.amount,
                reference_type='CustomerPayment',
                reference_id=payment.id,
                description=f"Reversal of Customer Payment {payment.payment_code} ({receivable.customer.name}): {reason.strip()}",
                created_by=user
            )

            FinancialCalculationService.recalculate_account_balance(locked_account.id)

            log_audit_event(
                user,
                AuditLog.ACTION_REVERSAL,
                'CustomerPayment',
                payment.id,
                changes={'payment_code': payment.payment_code, 'reason': reason.strip(), 'amount': str(payment.amount)},
                request=request
            )

            return payment

    @classmethod
    def get_receivable_metrics(cls) -> Dict[str, Decimal]:
        """Calculates dashboard/reporting aggregation for Customer Receivables."""
        zero = Decimal('0.00')
        today = timezone.now().date()

        receivables = Receivable.objects.filter(is_deleted=False, is_reversed=False)

        total_rcv = receivables.aggregate(s=Sum('total_amount'))['s'] or zero
        total_recv = receivables.aggregate(s=Sum('received_amount'))['s'] or zero
        outstanding = total_rcv - total_recv

        overdue_rcv = receivables.filter(
            status__in=[Receivable.STATUS_UNPAID, Receivable.STATUS_PARTIAL],
            due_date__lt=today
        )
        overdue_total = overdue_rcv.aggregate(s=Sum('total_amount'))['s'] or zero
        overdue_received = overdue_rcv.aggregate(s=Sum('received_amount'))['s'] or zero
        overdue_outstanding = overdue_total - overdue_received

        return {
            'total_receivables': total_rcv,
            'total_received': total_recv,
            'outstanding_receivables': outstanding,
            'overdue_receivables': overdue_outstanding,
        }


class SupplierPayableService:
    """
    Service managing Supplier Payables (Vendor obligations)
    and Supplier Payment Disbursements (Account Outflow / PAYABLE_PAYMENT).
    """

    @classmethod
    def generate_payable_code(cls, date_val=None) -> str:
        """Generates unique sequential payable code e.g. PAY-20260815-0001."""
        target_date = date_val or timezone.now().date()
        date_str = target_date.strftime('%Y%m%d')
        prefix = f"PAY-{date_str}-"

        last_entry = Payable.objects.filter(payable_code__startswith=prefix).order_by('-id').first()
        if last_entry:
            try:
                seq = int(last_entry.payable_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def generate_payment_code(cls, date_val=None) -> str:
        """Generates unique sequential payment code e.g. SPAY-20260815-0001."""
        target_date = date_val or timezone.now().date()
        date_str = target_date.strftime('%Y%m%d')
        prefix = f"SPAY-{date_str}-"

        last_entry = SupplierPayment.objects.filter(payment_code__startswith=prefix).order_by('-id').first()
        if last_entry:
            try:
                seq = int(last_entry.payment_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def create_payable(
        cls,
        user: User,
        supplier: Supplier,
        total_amount: Decimal,
        bill_date = None,
        due_date = None,
        bill_no: Optional[str] = None,
        linked_expense = None,
        notes: Optional[str] = None,
        request = None
    ) -> Payable:
        """Creates a new Supplier Payable (Vendor obligation)."""
        if not isinstance(total_amount, Decimal):
            try:
                total_amount = Decimal(str(total_amount))
            except Exception:
                raise ValidationError({"total_amount": "Invalid monetary amount."})

        total_amount = total_amount.quantize(Decimal('0.01'))
        if total_amount <= Decimal('0.00'):
            raise ValidationError({"total_amount": "Payable total amount must be strictly greater than 0.00."})

        if not supplier or supplier.is_deleted or supplier.status != Supplier.STATUS_ACTIVE:
            raise ValidationError({"supplier": "A valid and active supplier is required."})

        entry_date = bill_date or timezone.now().date()

        if due_date and due_date < entry_date:
            raise ValidationError({"due_date": "Due date cannot be before bill date."})

        with transaction.atomic():
            code = cls.generate_payable_code(entry_date)

            payable = Payable.objects.create(
                payable_code=code,
                supplier=supplier,
                bill_no=bill_no,
                bill_date=entry_date,
                due_date=due_date,
                total_amount=total_amount,
                paid_amount=Decimal('0.00'),
                status=Payable.STATUS_UNPAID,
                linked_expense=linked_expense,
                notes=notes,
                created_by=user
            )

            log_audit_event(
                user,
                AuditLog.ACTION_CREATE,
                'Payable',
                payable.id,
                changes={
                    'payable_code': payable.payable_code,
                    'supplier': supplier.name,
                    'total_amount': str(total_amount),
                    'linked_expense': linked_expense.expense_code if linked_expense else None
                },
                request=request
            )

            return payable

    @classmethod
    def record_payment(
        cls,
        user: User,
        payable_id: int,
        amount: Decimal,
        account: Account,
        payment_method: str = SupplierPayment.METHOD_BANK_TRANSFER,
        payment_date = None,
        reference_no: Optional[str] = None,
        notes: Optional[str] = None,
        request = None
    ) -> SupplierPayment:
        """
        Atomically records a supplier payment settlement.
        Locks payable row with select_for_update to prevent concurrent overpayment.
        Creates an AccountTransaction (DEBIT / PAYABLE_PAYMENT) and updates account balance.
        RULE 9: Does NOT create a duplicate expense!
        """
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except Exception:
                raise ValidationError({"amount": "Invalid monetary amount."})

        amount = amount.quantize(Decimal('0.01'))
        if amount <= Decimal('0.00'):
            raise ValidationError({"amount": "Payment amount must be strictly greater than 0.00."})

        if not account or account.is_deleted or not account.is_active:
            raise ValidationError({"account": "A valid and active business account is required to disburse funds."})

        if payment_method not in dict(SupplierPayment.PAYMENT_METHOD_CHOICES):
            raise ValidationError({"payment_method": "Invalid payment method."})

        entry_date = payment_date or timezone.now().date()

        with transaction.atomic():
            # Concurrency protection: Lock payable and account rows
            payable = Payable.objects.select_for_update().get(id=payable_id, is_deleted=False)
            locked_account = Account.objects.select_for_update().get(id=account.id)

            if payable.is_reversed:
                raise ValidationError("Cannot settle a reversed payable.")

            outstanding = (payable.total_amount - payable.paid_amount).quantize(Decimal('0.01'))

            # Overpayment protection (Server-Side)
            if amount > outstanding:
                raise ValidationError({
                    "amount": f"Payment amount (₹{amount}) exceeds outstanding payable balance (₹{outstanding}). Overpayment is rejected."
                })

            new_paid = (payable.paid_amount + amount).quantize(Decimal('0.01'))
            payable.paid_amount = new_paid

            if new_paid >= payable.total_amount:
                payable.status = Payable.STATUS_PAID
            else:
                payable.status = Payable.STATUS_PARTIAL

            payable.save(update_fields=['paid_amount', 'status', 'updated_at'])

            code = cls.generate_payment_code(entry_date)

            # 1. Create central ledger DEBIT transaction (Outflow from account)
            desc = f"Supplier Disbursement ({payable.supplier.name}): {payable.payable_code} ({code})"
            if notes:
                desc += f" - {notes}"

            ledger_tx = AccountTransaction.objects.create(
                account=locked_account,
                transaction_date=entry_date,
                transaction_type=AccountTransaction.TYPE_PAYABLE_PAYMENT,
                direction=AccountTransaction.DIRECTION_DEBIT,
                amount=amount,
                reference_type='SupplierPayment',
                description=desc,
                created_by=user
            )

            # 2. Recalculate authoritative account balance
            FinancialCalculationService.recalculate_account_balance(locked_account.id)

            # 3. Create SupplierPayment record
            payment = SupplierPayment.objects.create(
                payment_code=code,
                payable=payable,
                account=locked_account,
                payment_date=entry_date,
                amount=amount,
                payment_method=payment_method,
                linked_ledger_transaction=ledger_tx,
                reference_no=reference_no,
                notes=notes,
                created_by=user
            )

            # Link reference_id on ledger transaction
            ledger_tx.reference_id = payment.id
            ledger_tx.save(update_fields=['reference_id'])

            # 4. Audit Log
            log_audit_event(
                user,
                AuditLog.ACTION_PAYMENT,
                'SupplierPayment',
                payment.id,
                changes={
                    'payment_code': payment.payment_code,
                    'payable': payable.payable_code,
                    'amount': str(amount),
                    'account': locked_account.account_name,
                    'remaining_outstanding': str(payable.outstanding_amount)
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
    ) -> SupplierPayment:
        """
        Reverses a supplier payment (Owner only).
        Restores payable outstanding balance and posts a compensatory CREDIT reversal ledger transaction.
        """
        if not user.profile.is_owner and not user.is_superuser:
            raise ValidationError("Reversing supplier payments is restricted to system Owners.")

        if not reason or len(reason.strip()) < 5:
            raise ValidationError({"reason": "A valid explanation (minimum 5 characters) is required for financial reversals."})

        with transaction.atomic():
            payment = SupplierPayment.objects.select_for_update().get(id=payment_id, is_deleted=False)

            if payment.is_reversed:
                raise ValidationError("This supplier payment has already been reversed.")

            payable = Payable.objects.select_for_update().get(id=payment.payable_id)
            locked_account = Account.objects.select_for_update().get(id=payment.account_id)

            payment.is_reversed = True
            payment.save(update_fields=['is_reversed'])

            # Restore payable balance
            new_paid = max(Decimal('0.00'), payable.paid_amount - payment.amount)
            payable.paid_amount = new_paid
            if new_paid == Decimal('0.00'):
                payable.status = Payable.STATUS_UNPAID
            else:
                payable.status = Payable.STATUS_PARTIAL
            payable.save(update_fields=['paid_amount', 'status', 'updated_at'])

            # Compensatory CREDIT reversal transaction (Money back into account)
            AccountTransaction.objects.create(
                account=locked_account,
                transaction_date=timezone.now().date(),
                transaction_type=AccountTransaction.TYPE_REVERSAL,
                direction=AccountTransaction.DIRECTION_CREDIT,
                amount=payment.amount,
                reference_type='SupplierPayment',
                reference_id=payment.id,
                description=f"Reversal of Supplier Payment {payment.payment_code} ({payable.supplier.name}): {reason.strip()}",
                created_by=user
            )

            FinancialCalculationService.recalculate_account_balance(locked_account.id)

            log_audit_event(
                user,
                AuditLog.ACTION_REVERSAL,
                'SupplierPayment',
                payment.id,
                changes={'payment_code': payment.payment_code, 'reason': reason.strip(), 'amount': str(payment.amount)},
                request=request
            )

            return payment

    @classmethod
    def get_payable_metrics(cls) -> Dict[str, Decimal]:
        """Calculates dashboard/reporting aggregation for Supplier Payables."""
        zero = Decimal('0.00')
        today = timezone.now().date()

        payables = Payable.objects.filter(is_deleted=False, is_reversed=False)

        total_pay = payables.aggregate(s=Sum('total_amount'))['s'] or zero
        total_paid = payables.aggregate(s=Sum('paid_amount'))['s'] or zero
        outstanding = total_pay - total_paid

        overdue_pay = payables.filter(
            status__in=[Payable.STATUS_UNPAID, Payable.STATUS_PARTIAL],
            due_date__lt=today
        )
        overdue_total = overdue_pay.aggregate(s=Sum('total_amount'))['s'] or zero
        overdue_paid = overdue_pay.aggregate(s=Sum('paid_amount'))['s'] or zero
        overdue_outstanding = overdue_total - overdue_paid

        return {
            'total_payables': total_pay,
            'total_paid': total_paid,
            'outstanding_payables': outstanding,
            'overdue_payables': overdue_outstanding,
        }
