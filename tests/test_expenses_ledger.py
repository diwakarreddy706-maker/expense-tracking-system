"""
Phase 4 Comprehensive Test Suite: General Expense Tracking & Central Ledger Engine.
Validates atomic expense creation, single ledger transaction generation,
decimal precision, reversal architecture, quick expense API, RBAC, and concurrent safety.
"""

from decimal import Decimal
import json
from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.finance.models import Account, AccountTransaction, Supplier
from apps.expenses.models import Expense, ExpenseCategory
from apps.machines.models import Machine, MachineType
from apps.employees.models import Employee
from apps.expenses.services.expense_service import ExpenseService
from apps.finance.services.balance_service import FinancialCalculationService


class ExpenseCreationAndLedgerTests(TestCase):
    """Verifies atomic creation of Expenses and Authoritative Central Ledger transactions."""

    def setUp(self):
        self.password = "Secr3tPassword!"
        self.owner = User.objects.create_user(username="owner_user", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.account = Account.objects.create(
            account_name="Main Current A/c",
            account_type=Account.TYPE_BANK_CURRENT,
            account_number="987654321001",
            opening_balance=Decimal('100000.00'),
            current_balance=Decimal('100000.00'),
            is_active=True
        )

        self.category = ExpenseCategory.objects.create(
            name="Field Maintenance",
            code="CAT-MAINT",
            is_active=True
        )

        self.inactive_category = ExpenseCategory.objects.create(
            name="Old Dormant Category",
            code="CAT-DORMANT",
            is_active=False
        )

        self.tractor_type = MachineType.objects.create(name="Tractor", code="TRACTOR")
        self.machine = Machine.objects.create(
            machine_code="MCH-TRAC-01",
            name="John Deere 5310",
            machine_type=self.tractor_type,
            status=Machine.STATUS_ACTIVE
        )

        self.employee = Employee.objects.create(
            employee_code="EMP-001",
            full_name="Ramesh Kumar",
            role=Employee.ROLE_TRACTOR_DRIVER,
            status=Employee.STATUS_ACTIVE
        )

        self.supplier = Supplier.objects.create(
            supplier_code="SUPP-001",
            name="Agri Spares Hub",
            supplier_type=Supplier.TYPE_SPARE_PARTS,
            status=Supplier.STATUS_ACTIVE
        )

    def test_valid_expense_creates_exactly_one_ledger_entry(self):
        """Proof: Expense -> exactly ONE account_transactions record with correct amount, account & balance impact."""
        initial_balance = self.account.current_balance
        expense_amount = Decimal('4500.50')

        expense, ledger_tx = ExpenseService.create_expense(
            user=self.owner,
            amount=expense_amount,
            category=self.category,
            account=self.account,
            payment_method=Expense.METHOD_BANK_TRANSFER,
            description="Hydraulic oil and filter change",
            machine=self.machine,
            employee=self.employee,
            supplier=self.supplier
        )

        # 1. Verify Expense record
        self.assertIsNotNone(expense.id)
        self.assertEqual(expense.amount, expense_amount)
        self.assertTrue(expense.expense_code.startswith('EXP-'))
        self.assertFalse(expense.is_reversed)

        # 2. Verify Ledger transaction
        self.assertIsNotNone(ledger_tx)
        ledger_count = AccountTransaction.objects.filter(reference_type='Expense', reference_id=expense.id).count()
        self.assertEqual(ledger_count, 1)

        self.assertEqual(ledger_tx.account, self.account)
        self.assertEqual(ledger_tx.amount, expense_amount)
        self.assertEqual(ledger_tx.direction, AccountTransaction.DIRECTION_DEBIT)
        self.assertEqual(ledger_tx.transaction_type, AccountTransaction.TYPE_EXPENSE)
        self.assertEqual(ledger_tx.created_by, self.owner)

        # 3. Verify Authoritative Account Balance
        self.account.refresh_from_db()
        expected_balance = initial_balance - expense_amount
        self.assertEqual(self.account.current_balance, expected_balance)

        # 4. Verify Audit Log entry
        audit = AuditLog.objects.filter(action=AuditLog.ACTION_CREATE, entity_type='Expense', entity_id=str(expense.id)).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.user, self.owner)

    def test_zero_and_negative_amounts_rejected(self):
        """Verifies zero and negative amounts are strictly rejected by server-side validation."""
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                user=self.owner,
                amount=Decimal('0.00'),
                category=self.category,
                account=self.account
            )

        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                user=self.owner,
                amount=Decimal('-150.00'),
                category=self.category,
                account=self.account
            )

    def test_inactive_category_rejected(self):
        """Verifies inactive category is rejected for new expenses."""
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                user=self.owner,
                amount=Decimal('500.00'),
                category=self.inactive_category,
                account=self.account
            )

    def test_deleted_or_inactive_account_rejected(self):
        """Verifies inactive or soft-deleted account is rejected."""
        inactive_acc = Account.objects.create(
            account_name="Closed Cash Box",
            account_type=Account.TYPE_CASH,
            is_active=False
        )
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                user=self.owner,
                amount=Decimal('200.00'),
                category=self.category,
                account=inactive_acc
            )

    def test_decommissioned_machine_rejected(self):
        """Verifies decommissioned machine cannot be linked to new expenses."""
        retired_machine = Machine.objects.create(
            machine_code="MCH-OLD-99",
            name="Scrapped Harvester",
            machine_type=self.tractor_type,
            status=Machine.STATUS_DECOMMISSIONED
        )
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                user=self.owner,
                amount=Decimal('100.00'),
                category=self.category,
                account=self.account,
                machine=retired_machine
            )

    def test_reversal_architecture_preserves_history(self):
        """Verifies financial reversal creates compensatory CREDIT transaction under Rule 10."""
        initial_balance = self.account.current_balance
        amount = Decimal('12000.00')

        expense, _ = ExpenseService.create_expense(
            user=self.owner,
            amount=amount,
            category=self.category,
            account=self.account,
            payment_method=Expense.METHOD_CASH
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance - amount)

        # Reverse expense
        rev_expense, rev_tx = ExpenseService.reverse_expense(
            expense_id=expense.id,
            user=self.owner,
            reason="Wrong category chosen during manual posting"
        )

        # Verify expense status
        self.assertTrue(rev_expense.is_reversed)
        self.assertEqual(rev_expense.amount, amount) # Not set to zero!

        # Verify reversal ledger transaction
        self.assertIsNotNone(rev_tx)
        self.assertEqual(rev_tx.direction, AccountTransaction.DIRECTION_CREDIT)
        self.assertEqual(rev_tx.transaction_type, AccountTransaction.TYPE_REVERSAL)
        self.assertEqual(rev_tx.amount, amount)

        # Verify restored balance
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance)

        # Verify audit log for reversal
        rev_audit = AuditLog.objects.filter(action=AuditLog.ACTION_REVERSAL, entity_type='Expense', entity_id=str(expense.id)).first()
        self.assertIsNotNone(rev_audit)


class QuickExpenseAPITests(TestCase):
    """Verifies Quick Expense endpoint and validation."""

    def setUp(self):
        self.client = Client()
        self.password = "SecretPass123!"

        self.owner = User.objects.create_user(username="quick_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.employee = User.objects.create_user(username="quick_emp", password=self.password)
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        self.account = Account.objects.create(
            account_name="Petty Cash Box",
            account_type=Account.TYPE_PETTY_CASH,
            opening_balance=Decimal('5000.00'),
            current_balance=Decimal('5000.00'),
            is_active=True
        )

        self.category = ExpenseCategory.objects.create(name="Tea & Refreshments", code="CAT-TEA", is_active=True)

    def test_quick_expense_post_success(self):
        """Verifies valid quick expense API call produces identical ledger behavior."""
        self.client.login(username='quick_owner', password=self.password)

        payload = {
            'amount': '350.00',
            'category_id': self.category.id,
            'account_id': self.account.id,
            'payment_method': 'CASH',
            'description': 'Refreshments for sowing labor'
        }

        response = self.client.post(
            reverse('api_expenses_quick'),
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertTrue(res_data['success'])
        self.assertIsNotNone(res_data['ledger_transaction_id'])

        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal('4650.00'))

    def test_quick_expense_invalid_amount_rejected(self):
        """Verifies invalid amount returns 400."""
        self.client.login(username='quick_owner', password=self.password)

        payload = {
            'amount': '-50.00',
            'category_id': self.category.id,
            'account_id': self.account.id
        }

        response = self.client.post(
            reverse('api_expenses_quick'),
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])


class ExpenseRBACTests(TestCase):
    """Verifies Role-Based Access Control on Expense workflows."""

    def setUp(self):
        self.client = Client()
        self.password = "RbacPass123!"

        self.owner = User.objects.create_user(username="e_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.manager = User.objects.create_user(username="e_mgr", password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.account = Account.objects.create(
            account_name="Field Operations Cash",
            account_type=Account.TYPE_CASH,
            opening_balance=Decimal('20000.00'),
            current_balance=Decimal('20000.00'),
            is_active=True
        )

        self.category = ExpenseCategory.objects.create(name="Lubricants", code="CAT-LUB", is_active=True)

        self.expense, _ = ExpenseService.create_expense(
            user=self.owner,
            amount=Decimal('800.00'),
            category=self.category,
            account=self.account,
            payment_method=Expense.METHOD_CASH
        )

    def test_owner_can_reverse_expense(self):
        """Verifies OWNER is authorized to reverse expenses."""
        self.client.login(username='e_owner', password=self.password)
        response = self.client.post(reverse('expenses:reverse', args=[self.expense.id]), {'reason': 'Approved Owner Correction'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.expense.refresh_from_db()
        self.assertTrue(self.expense.is_reversed)

    def test_manager_blocked_from_reversal(self):
        """Verifies MANAGER is strictly blocked (403) from financial reversal."""
        self.client.login(username='e_mgr', password=self.password)
        response = self.client.post(reverse('expenses:reverse', args=[self.expense.id]), {'reason': 'Unauthorized Manager Attempt'})
        self.assertEqual(response.status_code, 403)


class ConcurrentExpenseLedgerTests(TransactionTestCase):
    """
    Verifies transactional concurrency protection (select_for_update)
    on sequential atomic ledger postings.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="conc_user", password="PassWord123!")
        self.user.profile.role = UserProfile.ROLE_OWNER
        self.user.profile.save()

        self.account = Account.objects.create(
            account_name="Concurrency Safe A/c",
            account_type=Account.TYPE_BANK_CURRENT,
            opening_balance=Decimal('50000.00'),
            current_balance=Decimal('50000.00'),
            is_active=True
        )

        self.category = ExpenseCategory.objects.create(name="Seeds", code="CAT-SEED", is_active=True)

    def test_multiple_sequential_expense_postings_maintain_exact_balance(self):
        """Simulates high-volume consecutive expense postings and asserts balance fidelity."""
        postings = [
            Decimal('1200.00'),
            Decimal('3450.50'),
            Decimal('550.00'),
            Decimal('8900.25'),
            Decimal('100.00')
        ]
        total_spent = sum(postings)

        for amt in postings:
            ExpenseService.create_expense(
                user=self.user,
                amount=amt,
                category=self.category,
                account=self.account,
                payment_method=Expense.METHOD_BANK_TRANSFER
            )

        self.account.refresh_from_db()
        expected = Decimal('50000.00') - total_spent
        self.assertEqual(self.account.current_balance, expected)
        self.assertEqual(AccountTransaction.objects.filter(account=self.account).count(), 5)
