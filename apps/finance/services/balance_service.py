"""
Authoritative Financial Calculation Service.
Enforces Rule 1 (Fixed-point Decimal math) and Rule 10 (Single Authoritative Source).
"""

from decimal import Decimal
from typing import Dict, Any


class FinancialCalculationService:
    """
    Central calculation engine for all account balances, daily closings,
    and financial metrics across the application.
    """

    @staticmethod
    def get_zero_amount() -> Decimal:
        """Returns standard zero decimal with fixed 2-place precision."""
        return Decimal('0.00')

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
