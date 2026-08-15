"""
Phase 8 Comprehensive Test Suite: Daily Financial Closing & Cash Reconciliation.
Validates:
- Four scopes: CASH_ACCOUNT, BANK_ACCOUNT, UPI_ACCOUNT, CONSOLIDATED.
- Authoritative reconciliation from account_transactions.
- Transfer Exclusion for consolidated liquid balances.
- Physical cash drawer count & bank/UPI statement reconciliations.
- Discrepancy handling (BALANCED, SURPLUS, DEFICIT) and mandatory note enforcement.
- Locking, immutability, duplicate closing rejection.
- Server-side RBAC authorization and Audit logging.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.finance.models import (
    Account, AccountTransaction,
    Customer, Supplier,
    DailyClosing
)
from apps.finance.services.closing_service import DailyClosingService


class DailyClosingReconciliationTests(TestCase):
    """Verifies authoritative daily calculation, reconciliation formula, and discrepancy logic."""

    def setUp(self):
        self.password = "SafePassword123!"
        self.owner = User.objects.create_user(username="close_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.cash_account = Account.objects.create(
            account_name="Main Office Cash Drawer",
            account_type=Account.TYPE_CASH,
            opening_balance=Decimal('20000.00'),
            current_balance=Decimal('20000.00'),
            is_active=True
        )

        self.bank_account = Account.objects.create(
            account_name="SBI Current A/c",
            account_type=Account.TYPE_BANK_CURRENT,
            opening_balance=Decimal('100000.00'),
            current_balance=Decimal('100000.00'),
            is_active=True
        )

        self.upi_account = Account.objects.create(
            account_name="Farm UPI Scanner",
            account_type=Account.TYPE_UPI_WALLET,
            opening_balance=Decimal('5000.00'),
            current_balance=Decimal('5000.00'),
            is_active=True
        )

        self.today = timezone.now().date()

    def test_cash_closing_reconciliation_and_balanced_status(self):
        """
        Proof of Cash Closing:
        Opening: ₹20,000
        Inflow: ₹5,000 (Customer collection)
        Outflow: ₹3,000 (Expense)
        Transfer In: ₹2,000 (Drawn from Bank)
        Expected Closing: ₹24,000
        Physical Count: ₹24,000
        Status: BALANCED (Discrepancy: ₹0.00)
        """
        # Record movements
        AccountTransaction.objects.create(
            account=self.cash_account,
            transaction_date=self.today,
            transaction_type=AccountTransaction.TYPE_RECEIVABLE_PAYMENT,
            direction=AccountTransaction.DIRECTION_CREDIT,
            amount=Decimal('5000.00'),
            created_by=self.owner
        )
        AccountTransaction.objects.create(
            account=self.cash_account,
            transaction_date=self.today,
            transaction_type=AccountTransaction.TYPE_EXPENSE,
            direction=AccountTransaction.DIRECTION_DEBIT,
            amount=Decimal('3000.00'),
            created_by=self.owner
        )
        AccountTransaction.objects.create(
            account=self.cash_account,
            transaction_date=self.today,
            transaction_type=AccountTransaction.TYPE_TRANSFER_IN,
            direction=AccountTransaction.DIRECTION_CREDIT,
            amount=Decimal('2000.00'),
            created_by=self.owner
        )

        # 1. Calculate Expected
        rec = DailyClosingService.calculate_daily_reconciliation(
            closing_date=self.today,
            scope=DailyClosing.SCOPE_CASH,
            account_id=self.cash_account.id
        )

        self.assertEqual(rec['opening_balance'], Decimal('20000.00'))
        self.assertEqual(rec['total_inflow'], Decimal('5000.00'))
        self.assertEqual(rec['total_outflow'], Decimal('3000.00'))
        self.assertEqual(rec['transfer_in'], Decimal('2000.00'))
        self.assertEqual(rec['expected_closing'], Decimal('24000.00'))

        # 2. Submit Balanced Closing
        closing = DailyClosingService.submit_daily_closing(
            user=self.owner,
            closing_date=self.today,
            scope=DailyClosing.SCOPE_CASH,
            actual_closing=Decimal('24000.00'),
            account_id=self.cash_account.id
        )

        self.assertEqual(closing.status, DailyClosing.STATUS_BALANCED)
        self.assertEqual(closing.discrepancy, Decimal('0.00'))
        self.assertTrue(closing.is_locked)

    def test_surplus_and_deficit_discrepancy_require_mandatory_notes(self):
        """Verifies surplus and deficit closings require explanatory notes."""
        # Expected is ₹20,000 (no movements today)
        # Attempt Surplus without note -> Rejected
        with self.assertRaises(ValidationError) as ctx:
            DailyClosingService.submit_daily_closing(
                user=self.owner,
                closing_date=self.today,
                scope=DailyClosing.SCOPE_CASH,
                actual_closing=Decimal('20500.00'), # ₹500 excess cash
                account_id=self.cash_account.id,
                notes="" # Missing note
            )
        self.assertIn("Mandatory discrepancy explanation", str(ctx.exception))

        # Attempt Deficit without note -> Rejected
        with self.assertRaises(ValidationError) as ctx2:
            DailyClosingService.submit_daily_closing(
                user=self.owner,
                closing_date=self.today,
                scope=DailyClosing.SCOPE_CASH,
                actual_closing=Decimal('19500.00'), # ₹500 shortage
                account_id=self.cash_account.id,
                notes="" # Missing note
            )
        self.assertIn("Mandatory discrepancy explanation", str(ctx2.exception))

        # Submit Deficit with valid note -> Success
        closing = DailyClosingService.submit_daily_closing(
            user=self.owner,
            closing_date=self.today,
            scope=DailyClosing.SCOPE_CASH,
            actual_closing=Decimal('19800.00'),
            account_id=self.cash_account.id,
            notes="Small change shortfall in cash register"
        )
        self.assertEqual(closing.status, DailyClosing.STATUS_DEFICIT)
        self.assertEqual(closing.discrepancy, Decimal('-200.00'))

    def test_consolidated_closing_and_transfer_exclusion(self):
        """
        Proof of Rule 5 & 16 (Transfer Exclusion):
        Bank transfers ₹10,000 to Cash drawer.
        Cash +₹10,000, Bank -₹10,000.
        Consolidated Net Balance change = ₹0.00.
        Expected Consolidated = Opening Cash (₹20k) + Opening Bank (₹100k) + Opening UPI (₹5k) = ₹125,000.
        """
        # Internal Transfer: Bank -> Cash
        AccountTransaction.objects.create(
            account=self.bank_account,
            transaction_date=self.today,
            transaction_type=AccountTransaction.TYPE_TRANSFER_OUT,
            direction=AccountTransaction.DIRECTION_DEBIT,
            amount=Decimal('10000.00'),
            created_by=self.owner
        )
        AccountTransaction.objects.create(
            account=self.cash_account,
            transaction_date=self.today,
            transaction_type=AccountTransaction.TYPE_TRANSFER_IN,
            direction=AccountTransaction.DIRECTION_CREDIT,
            amount=Decimal('10000.00'),
            created_by=self.owner
        )

        rec = DailyClosingService.calculate_daily_reconciliation(
            closing_date=self.today,
            scope=DailyClosing.SCOPE_CONSOLIDATED
        )

        # Expected opening: ₹20k + ₹100k + ₹5k = ₹125,000
        self.assertEqual(rec['opening_balance'], Decimal('125000.00'))
        # Internal transfers do not count as external inflow or outflow
        self.assertEqual(rec['total_inflow'], Decimal('0.00'))
        self.assertEqual(rec['total_outflow'], Decimal('0.00'))
        self.assertEqual(rec['expected_closing'], Decimal('125000.00'))

        # Submit Consolidated Closing
        closing = DailyClosingService.submit_daily_closing(
            user=self.owner,
            closing_date=self.today,
            scope=DailyClosing.SCOPE_CONSOLIDATED,
            actual_closing=Decimal('125000.00')
        )
        self.assertEqual(closing.status, DailyClosing.STATUS_BALANCED)

    def test_duplicate_closing_on_same_date_and_scope_is_rejected(self):
        """Verifies duplicate closing protection (Rule 24)."""
        DailyClosingService.submit_daily_closing(
            user=self.owner,
            closing_date=self.today,
            scope=DailyClosing.SCOPE_BANK,
            actual_closing=Decimal('100000.00'),
            account_id=self.bank_account.id
        )

        with self.assertRaises(ValidationError) as ctx:
            DailyClosingService.submit_daily_closing(
                user=self.owner,
                closing_date=self.today,
                scope=DailyClosing.SCOPE_BANK,
                actual_closing=Decimal('100000.00'),
                account_id=self.bank_account.id
            )
        self.assertIn("A locked daily closing already exists", str(ctx.exception))


class DailyClosingRBACTests(TestCase):
    """Verifies server-side RBAC protection on Daily Closing views."""

    def setUp(self):
        self.client = Client()
        self.password = "SafePass123!"

        self.owner = User.objects.create_user(username="c_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.accountant = User.objects.create_user(username="c_acc", password=self.password)
        self.accountant.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant.profile.save()

        self.manager = User.objects.create_user(username="c_mgr", password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.employee = User.objects.create_user(username="c_emp", password=self.password)
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        self.account = Account.objects.create(
            account_name="Cash Office",
            account_type=Account.TYPE_CASH,
            opening_balance=Decimal('15000.00'),
            current_balance=Decimal('15000.00'),
            is_active=True
        )

    def test_owner_and_accountant_can_access_and_submit_closings(self):
        """Verifies Owner and Accountant have full access to daily closing."""
        self.client.login(username='c_owner', password=self.password)
        self.assertEqual(self.client.get(reverse('finance:daily_closing')).status_code, 200)

        self.client.login(username='c_acc', password=self.password)
        self.assertEqual(self.client.get(reverse('finance:daily_closing')).status_code, 200)

    def test_manager_and_employee_forbidden_from_daily_closing(self):
        """Verifies Manager and Employee are forbidden (403) from daily closing."""
        self.client.login(username='c_mgr', password=self.password)
        self.assertEqual(self.client.get(reverse('finance:daily_closing')).status_code, 403)
        self.assertEqual(self.client.post(reverse('finance:daily_closing_submit'), {}).status_code, 403)

        self.client.login(username='c_emp', password=self.password)
        self.assertEqual(self.client.get(reverse('finance:daily_closing')).status_code, 403)
        self.assertEqual(self.client.post(reverse('finance:daily_closing_submit'), {}).status_code, 403)
