"""
Authoritative Financial Calculation Service.
Enforces Rule 1 (Fixed-point Decimal math) and Rule 10 (Single Authoritative Source: account_transactions).
"""

from decimal import Decimal
from typing import Dict, Any, Optional
from django.db import transaction
from django.db.models import Sum, Q


class FinancialCalculationService:
    """
    Central calculation engine for all account balances, daily closings,
    and financial metrics across the application.
    """

    @staticmethod
    def get_zero_amount() -> Decimal:
        """Returns standard zero decimal with fixed 2-place precision."""
        return Decimal('0.00')

    @classmethod
    def recalculate_account_balance(cls, account_id: int) -> Decimal:
        """
        Authoritative Account Balance Calculation:
        Balance = Opening Balance + Ledger Credits (Inflows) - Ledger Debits (Outflows)
        Updates the cached `accounts.current_balance` within a select_for_update transaction.
        """
        from apps.finance.models import Account, AccountTransaction

        with transaction.atomic():
            account = Account.objects.select_for_update().get(id=account_id)

            aggregates = AccountTransaction.objects.filter(
                account_id=account.id,
                is_deleted=False
            ).aggregate(
                total_credits=Sum('amount', filter=Q(direction=AccountTransaction.DIRECTION_CREDIT)),
                total_debits=Sum('amount', filter=Q(direction=AccountTransaction.DIRECTION_DEBIT))
            )

            credits = aggregates['total_credits'] or cls.get_zero_amount()
            debits = aggregates['total_debits'] or cls.get_zero_amount()

            authoritative_balance = account.opening_balance + credits - debits
            account.current_balance = authoritative_balance
            account.save(update_fields=['current_balance', 'updated_at'])

            return authoritative_balance

    @staticmethod
    def calculate_scoped_closing(
        opening_balance: Decimal,
        inflow: Decimal,
        outflow: Decimal,
        transfer_in: Decimal = Decimal('0.00'),
        transfer_out: Decimal = Decimal('0.00'),
    ) -> Decimal:
        """
        Calculates expected closing balance:
        Opening + Inflow + Transfer In - Outflow - Transfer Out
        """
        return opening_balance + inflow + transfer_in - outflow - transfer_out

    @staticmethod
    def calculate_discrepancy(actual_closing: Decimal, expected_closing: Decimal) -> Decimal:
        """Calculates discrepancy: Actual - Expected."""
        return actual_closing - expected_closing
