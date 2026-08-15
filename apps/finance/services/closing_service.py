"""
Authoritative Daily Financial Closing & Reconciliation Service Layer.
Enforces Rule 1 (Decimal precision), Rule 6 (account_transactions as authoritative source),
Transfer Exclusion for Consolidated Closing, Discrepancy enforcement, and historical immutability.
"""

from decimal import Decimal
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from apps.finance.models import (
    Account, AccountTransaction,
    DailyClosing, Receivable, Payable
)
from apps.employees.models import EmployeePayment
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog


class DailyClosingService:
    """
    Service for calculating daily account reconciliation, cash drawer physical counts,
    bank/UPI statement reconciliations, and consolidated liquid closing snapshots.
    """

    @classmethod
    def get_account_opening_balance_on_date(cls, account: Account, target_date) -> Decimal:
        """
        Authoritatively calculates the opening balance of an account as of target_date 00:00:00.
        Uses historical ledger transactions prior to target_date.
        """
        zero = Decimal('0.00')
        prior_txs = AccountTransaction.objects.filter(
            account=account,
            transaction_date__lt=target_date,
            is_deleted=False
        )

        prior_credits = prior_txs.filter(direction=AccountTransaction.DIRECTION_CREDIT).aggregate(s=Sum('amount'))['s'] or zero
        prior_debits = prior_txs.filter(direction=AccountTransaction.DIRECTION_DEBIT).aggregate(s=Sum('amount'))['s'] or zero

        # Base starting point
        if account.opening_balance_date and account.opening_balance_date > target_date:
            # If account opening date is strictly in future, balance is zero
            return zero

        return (account.opening_balance + prior_credits - prior_debits).quantize(Decimal('0.01'))

    @classmethod
    def calculate_daily_reconciliation(
        cls,
        closing_date,
        scope: str,
        account_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Authoritatively calculates expected opening, inflows, outflows, transfers,
        and expected closing for the given scope and date.
        """
        zero = Decimal('0.00')
        today = timezone.now().date()

        if closing_date > today:
            raise ValidationError({"closing_date": "Daily closing cannot be calculated for future dates."})

        if scope not in dict(DailyClosing.SCOPE_CHOICES):
            raise ValidationError({"scope": "Invalid daily closing scope."})

        # 1. Scope resolution
        target_account = None
        accounts_queryset = Account.objects.filter(is_deleted=False, is_active=True)

        if scope == DailyClosing.SCOPE_CONSOLIDATED:
            # Consolidated encompasses all active business accounts
            active_accounts = list(accounts_queryset)
        elif scope == DailyClosing.SCOPE_CASH:
            if account_id:
                target_account = get_object_or_404_account(account_id, Account.TYPE_CASH, Account.TYPE_PETTY_CASH)
            else:
                target_account = accounts_queryset.filter(account_type__in=[Account.TYPE_CASH, Account.TYPE_PETTY_CASH]).first()
            active_accounts = [target_account] if target_account else []
        elif scope == DailyClosing.SCOPE_BANK:
            if account_id:
                target_account = get_object_or_404_account(account_id, Account.TYPE_BANK_SAVINGS, Account.TYPE_BANK_CURRENT)
            else:
                target_account = accounts_queryset.filter(account_type__in=[Account.TYPE_BANK_SAVINGS, Account.TYPE_BANK_CURRENT]).first()
            active_accounts = [target_account] if target_account else []
        elif scope == DailyClosing.SCOPE_UPI:
            if account_id:
                target_account = get_object_or_404_account(account_id, Account.TYPE_UPI_WALLET)
            else:
                target_account = accounts_queryset.filter(account_type=Account.TYPE_UPI_WALLET).first()
            active_accounts = [target_account] if target_account else []
        else:
            active_accounts = []

        if not active_accounts and scope != DailyClosing.SCOPE_CONSOLIDATED:
            raise ValidationError({"account": f"No active account found for scope '{scope}'."})

        # 2. Opening Balance Calculation
        total_opening = sum(
            cls.get_account_opening_balance_on_date(acc, closing_date)
            for acc in active_accounts
        ) if active_accounts else zero
        total_opening = total_opening.quantize(Decimal('0.01'))

        # 3. Daily Transactions Querying on closing_date
        account_ids = [acc.id for acc in active_accounts]
        txs = AccountTransaction.objects.filter(
            account_id__in=account_ids,
            transaction_date=closing_date,
            is_deleted=False
        )

        # Inflows (External Money In)
        inflow_types = [
            AccountTransaction.TYPE_INCOME,
            AccountTransaction.TYPE_RECEIVABLE_PAYMENT,
            AccountTransaction.TYPE_OPENING_BALANCE,
            AccountTransaction.TYPE_ADJUSTMENT,
        ]
        inflows = txs.filter(
            direction=AccountTransaction.DIRECTION_CREDIT,
            transaction_type__in=inflow_types
        ).aggregate(s=Sum('amount'))['s'] or zero

        # Outflows (External Money Out)
        outflow_types = [
            AccountTransaction.TYPE_EXPENSE,
            AccountTransaction.TYPE_EMPLOYEE_PAYMENT,
            AccountTransaction.TYPE_PAYABLE_PAYMENT,
        ]
        outflows = txs.filter(
            direction=AccountTransaction.DIRECTION_DEBIT,
            transaction_type__in=outflow_types
        ).aggregate(s=Sum('amount'))['s'] or zero

        # Transfers (Rule 5 & 16: For Consolidated, internal transfers net out to 0.00)
        if scope == DailyClosing.SCOPE_CONSOLIDATED:
            transfer_in = zero
            transfer_out = zero
        else:
            transfer_in = txs.filter(
                direction=AccountTransaction.DIRECTION_CREDIT,
                transaction_type=AccountTransaction.TYPE_TRANSFER_IN
            ).aggregate(s=Sum('amount'))['s'] or zero

            transfer_out = txs.filter(
                direction=AccountTransaction.DIRECTION_DEBIT,
                transaction_type=AccountTransaction.TYPE_TRANSFER_OUT
            ).aggregate(s=Sum('amount'))['s'] or zero

        # Expected Closing
        expected_closing = (total_opening + inflows - outflows + transfer_in - transfer_out).quantize(Decimal('0.01'))

        # 4. Contextual Supporting Metrics (Rule 18 & 19: Kept separate from liquid cash)
        receivables_out = (
            Receivable.objects.filter(is_deleted=False, is_reversed=False)
            .aggregate(t=Sum('total_amount'), r=Sum('received_amount'))
        )
        rcv_out_total = ((receivables_out['t'] or zero) - (receivables_out['r'] or zero)).quantize(Decimal('0.01'))

        payables_out = (
            Payable.objects.filter(is_deleted=False, is_reversed=False)
            .aggregate(t=Sum('total_amount'), p=Sum('paid_amount'))
        )
        pay_out_total = ((payables_out['t'] or zero) - (payables_out['p'] or zero)).quantize(Decimal('0.01'))

        emp_payments = EmployeePayment.objects.filter(is_deleted=False, is_reversed=False)
        emp_accruals = emp_payments.filter(payment_type=EmployeePayment.TYPE_SALARY_ACCRUAL).aggregate(s=Sum('amount'))['s'] or zero
        emp_bonuses = emp_payments.filter(payment_type=EmployeePayment.TYPE_BONUS).aggregate(s=Sum('amount'))['s'] or zero
        emp_advances = emp_payments.filter(payment_type=EmployeePayment.TYPE_ADVANCE_PAYOUT).aggregate(s=Sum('amount'))['s'] or zero
        emp_settlements = emp_payments.filter(payment_type=EmployeePayment.TYPE_SALARY_SETTLEMENT).aggregate(s=Sum('amount'))['s'] or zero
        emp_out_total = ((emp_accruals + emp_bonuses) - (emp_advances + emp_settlements)).quantize(Decimal('0.01'))

        return {
            'closing_date': closing_date,
            'scope': scope,
            'target_account': target_account,
            'active_accounts': active_accounts,
            'opening_balance': total_opening,
            'total_inflow': inflows.quantize(Decimal('0.01')),
            'total_outflow': outflows.quantize(Decimal('0.01')),
            'transfer_in': transfer_in.quantize(Decimal('0.01')),
            'transfer_out': transfer_out.quantize(Decimal('0.01')),
            'expected_closing': expected_closing,
            'receivables_outstanding': rcv_out_total,
            'payables_outstanding': pay_out_total,
            'employee_wages_outstanding': emp_out_total,
        }

    @classmethod
    def submit_daily_closing(
        cls,
        user: User,
        closing_date,
        scope: str,
        actual_closing: Decimal,
        account_id: Optional[int] = None,
        notes: Optional[str] = None,
        request = None
    ) -> DailyClosing:
        """
        Atomically submits and locks a Daily Financial Closing snapshot.
        Enforces discrepancy notes and duplicate closing protection.
        """
        if not user.profile.is_owner and not user.profile.is_accountant and not user.is_superuser:
            raise ValidationError("Submitting daily financial closings is restricted to Owners and Accountants.")

        if not isinstance(actual_closing, Decimal):
            try:
                actual_closing = Decimal(str(actual_closing))
            except Exception:
                raise ValidationError({"actual_closing": "Invalid actual closing amount."})

        actual_closing = actual_closing.quantize(Decimal('0.01'))

        with transaction.atomic():
            # 1. Calculate authoritative figures
            reconciliation = cls.calculate_daily_reconciliation(closing_date, scope, account_id)
            target_account = reconciliation['target_account']
            expected = reconciliation['expected_closing']

            # 2. Check for duplicate closing
            existing = DailyClosing.objects.filter(
                closing_date=closing_date,
                scope=scope,
                account=target_account
            ).first()

            if existing and existing.is_locked:
                raise ValidationError(f"A locked daily closing already exists for {closing_date} ({dict(DailyClosing.SCOPE_CHOICES).get(scope)}).")

            # 3. Discrepancy & Status
            discrepancy = (actual_closing - expected).quantize(Decimal('0.01'))

            if discrepancy == Decimal('0.00'):
                status = DailyClosing.STATUS_BALANCED
            elif discrepancy > Decimal('0.00'):
                status = DailyClosing.STATUS_SURPLUS
            else:
                status = DailyClosing.STATUS_DEFICIT

            # Discrepancy Note Enforcement (Section 10)
            if status != DailyClosing.STATUS_BALANCED:
                if not notes or len(notes.strip()) < 5:
                    raise ValidationError({
                        "notes": f"Mandatory discrepancy explanation (minimum 5 characters) is required for {status} of ₹{abs(discrepancy)}."
                    })

            # 4. Save or Update DailyClosing record
            if existing:
                closing = existing
                closing.opening_balance = reconciliation['opening_balance']
                closing.total_inflow = reconciliation['total_inflow']
                closing.total_outflow = reconciliation['total_outflow']
                closing.transfer_in = reconciliation['transfer_in']
                closing.transfer_out = reconciliation['transfer_out']
                closing.expected_closing = expected
                closing.actual_closing = actual_closing
                closing.discrepancy = discrepancy
                closing.status = status
                closing.notes = notes
                closing.is_locked = True
                closing.closed_by = user
                closing.save()
            else:
                closing = DailyClosing.objects.create(
                    closing_date=closing_date,
                    scope=scope,
                    account=target_account,
                    opening_balance=reconciliation['opening_balance'],
                    total_inflow=reconciliation['total_inflow'],
                    total_outflow=reconciliation['total_outflow'],
                    transfer_in=reconciliation['transfer_in'],
                    transfer_out=reconciliation['transfer_out'],
                    expected_closing=expected,
                    actual_closing=actual_closing,
                    discrepancy=discrepancy,
                    status=status,
                    notes=notes,
                    is_locked=True,
                    closed_by=user
                )

            # 5. Audit Logging
            log_audit_event(
                user,
                AuditLog.ACTION_DAILY_CLOSE,
                'DailyClosing',
                closing.id,
                changes={
                    'date': str(closing_date),
                    'scope': scope,
                    'account': target_account.account_name if target_account else 'CONSOLIDATED',
                    'expected': str(expected),
                    'actual': str(actual_closing),
                    'discrepancy': str(discrepancy),
                    'status': status
                },
                request=request
            )

            return closing


def get_object_or_404_account(account_id: int, *types) -> Account:
    """Helper to get and validate account type."""
    account = Account.objects.filter(id=account_id, is_deleted=False, is_active=True).first()
    if not account:
        raise ValidationError(f"Account ID {account_id} not found or inactive.")
    if types and account.account_type not in types:
        raise ValidationError(f"Account '{account.account_name}' ({account.get_account_type_display()}) is not valid for this scope.")
    return account
