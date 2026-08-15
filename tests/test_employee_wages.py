"""
Phase 6 Comprehensive Test Suite: Employee & Wage Management.
Validates wage accruals vs payouts (Rule 4), advance disbursements, salary settlements,
net outstanding payable calculations, central financial ledger debits, privacy & RBAC barriers.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.finance.models import Account, AccountTransaction
from apps.employees.models import Employee, EmployeePayment
from apps.employees.services.employee_service import EmployeeFinancialService


class EmployeeFinancialWorkflowTests(TestCase):
    """Verifies core accounting rules: Accrual vs Payout, Advances, Settlements, and Balance calculations."""

    def setUp(self):
        self.password = "SafePassword123!"
        self.owner = User.objects.create_user(username="wage_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.account = Account.objects.create(
            account_name="Wage Disbursement Cash Box",
            account_type=Account.TYPE_CASH,
            opening_balance=Decimal('50000.00'),
            current_balance=Decimal('50000.00'),
            is_active=True
        )

        self.driver = Employee.objects.create(
            employee_code="EMP-TRAC-01",
            full_name="Babu Rao",
            role=Employee.ROLE_TRACTOR_DRIVER,
            wage_type=Employee.WAGE_MONTHLY,
            base_rate=Decimal('25000.00'),
            status=Employee.STATUS_ACTIVE
        )

        self.harvester_op = Employee.objects.create(
            employee_code="EMP-HARV-01",
            full_name="Ganesh Jadhav",
            role=Employee.ROLE_HARVESTER_OPERATOR,
            wage_type=Employee.WAGE_PER_ACRE,
            base_rate=Decimal('400.00'),
            status=Employee.STATUS_ACTIVE
        )

    def test_salary_accrual_does_not_deduct_account_balance(self):
        """
        Proof of RULE 4 (Accrual vs Payment distinction):
        Accruing salary increases employee liability but does NOT create an AccountTransaction
        or deduct from business cash/bank accounts.
        """
        initial_balance = self.account.current_balance
        accrual_amount = Decimal('25000.00')

        accrual = EmployeeFinancialService.record_salary_accrual(
            user=self.owner,
            employee=self.driver,
            amount=accrual_amount,
            notes="August 2026 Monthly Salary Accrual"
        )

        # 1. Verify EmployeePayment record
        self.assertIsNotNone(accrual.id)
        self.assertEqual(accrual.payment_type, EmployeePayment.TYPE_SALARY_ACCRUAL)
        self.assertEqual(accrual.amount, accrual_amount)
        self.assertIsNone(accrual.account)
        self.assertIsNone(accrual.linked_ledger_transaction)

        # 2. Verify NO AccountTransaction was created
        tx_count = AccountTransaction.objects.filter(reference_type='EmployeePayment', reference_id=accrual.id).count()
        self.assertEqual(tx_count, 0)

        # 3. Verify Account balance remains completely unchanged
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance)

        # 4. Verify Employee net outstanding increases
        balances = EmployeeFinancialService.calculate_employee_balances(self.driver.id)
        self.assertEqual(balances['total_accruals'], accrual_amount)
        self.assertEqual(balances['net_outstanding'], accrual_amount)

    def test_advance_payout_debits_ledger_and_updates_advance_balance(self):
        """
        Proof of Advance Payout:
        Disbursing advance creates an AccountTransaction, debits account balance,
        and increases employee advance obligation.
        """
        initial_balance = self.account.current_balance
        advance_amount = Decimal('5000.00')

        advance = EmployeeFinancialService.record_payout(
            user=self.owner,
            employee=self.driver,
            payment_type=EmployeePayment.TYPE_ADVANCE_PAYOUT,
            amount=advance_amount,
            account=self.account,
            payment_method=EmployeePayment.METHOD_CASH,
            notes="Festival advance"
        )

        # 1. Verify EmployeePayment
        self.assertIsNotNone(advance.id)
        self.assertEqual(advance.payment_type, EmployeePayment.TYPE_ADVANCE_PAYOUT)
        self.assertEqual(advance.account, self.account)

        # 2. Verify AccountTransaction created
        self.assertIsNotNone(advance.linked_ledger_transaction)
        tx = advance.linked_ledger_transaction
        self.assertEqual(tx.account, self.account)
        self.assertEqual(tx.amount, advance_amount)
        self.assertEqual(tx.direction, AccountTransaction.DIRECTION_DEBIT)
        self.assertEqual(tx.transaction_type, AccountTransaction.TYPE_EMPLOYEE_PAYMENT)

        # 3. Verify Account balance deducted
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance - advance_amount)

        # 4. Verify Employee advance balance
        balances = EmployeeFinancialService.calculate_employee_balances(self.driver.id)
        self.assertEqual(balances['total_advances'], advance_amount)

    def test_salary_settlement_and_net_outstanding_calculation(self):
        """
        Comprehensive Lifecycle:
        1. Salary Accrued: ₹25,000
        2. Advance Paid: ₹5,000
        3. Remaining Payable: ₹20,000
        4. Salary Settlement Paid: ₹20,000
        5. Net Outstanding: ₹0.00
        """
        initial_balance = self.account.current_balance

        # Step 1: Accrual
        EmployeeFinancialService.record_salary_accrual(
            user=self.owner,
            employee=self.driver,
            amount=Decimal('25000.00')
        )

        # Step 2: Advance
        EmployeeFinancialService.record_payout(
            user=self.owner,
            employee=self.driver,
            payment_type=EmployeePayment.TYPE_ADVANCE_PAYOUT,
            amount=Decimal('5000.00'),
            account=self.account
        )

        # Assert mid-state
        mid_balances = EmployeeFinancialService.calculate_employee_balances(self.driver.id)
        self.assertEqual(mid_balances['total_accruals'], Decimal('25000.00'))
        self.assertEqual(mid_balances['total_advances'], Decimal('5000.00'))
        self.assertEqual(mid_balances['net_outstanding'], Decimal('20000.00'))

        # Step 3: Settlement of remaining ₹20,000
        EmployeeFinancialService.record_payout(
            user=self.owner,
            employee=self.driver,
            payment_type=EmployeePayment.TYPE_SALARY_SETTLEMENT,
            amount=Decimal('20000.00'),
            account=self.account
        )

        # Step 4: Final ledger assertions
        final_balances = EmployeeFinancialService.calculate_employee_balances(self.driver.id)
        self.assertEqual(final_balances['total_accruals'], Decimal('25000.00'))
        self.assertEqual(final_balances['total_advances'], Decimal('5000.00'))
        self.assertEqual(final_balances['total_settlements'], Decimal('20000.00'))
        self.assertEqual(final_balances['net_outstanding'], Decimal('0.00'))

        # Cash balance decreased by exactly total disbursed (₹5,000 + ₹20,000 = ₹25,000)
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance - Decimal('25000.00'))

    def test_bonus_payout_workflow(self):
        """Verifies performance bonus reward increases total earned and debits ledger."""
        initial_balance = self.account.current_balance
        bonus_amt = Decimal('3000.00')

        bonus = EmployeeFinancialService.record_payout(
            user=self.owner,
            employee=self.driver,
            payment_type=EmployeePayment.TYPE_BONUS,
            amount=bonus_amt,
            account=self.account,
            notes="Diwali Performance Bonus"
        )

        self.assertEqual(bonus.amount, bonus_amt)
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance - bonus_amt)

        balances = EmployeeFinancialService.calculate_employee_balances(self.driver.id)
        self.assertEqual(balances['total_bonuses'], bonus_amt)

    def test_reversal_creates_compensatory_credit_transaction(self):
        """Verifies reversing a payout restores the business account balance via credit reversal."""
        initial_balance = self.account.current_balance
        advance_amt = Decimal('4000.00')

        advance = EmployeeFinancialService.record_payout(
            user=self.owner,
            employee=self.driver,
            payment_type=EmployeePayment.TYPE_ADVANCE_PAYOUT,
            amount=advance_amt,
            account=self.account
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance - advance_amt)

        # Reverse advance
        EmployeeFinancialService.reverse_payment(
            payment_id=advance.id,
            user=self.owner,
            reason="Advance entered against wrong staff member"
        )

        advance.refresh_from_db()
        self.assertTrue(advance.is_reversed)

        # Authoritative balance restored
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance)

        # Audit log entry for reversal
        rev_audit = AuditLog.objects.filter(action=AuditLog.ACTION_REVERSAL, entity_type='EmployeePayment', entity_id=str(advance.id)).first()
        self.assertIsNotNone(rev_audit)


class EmployeeSalaryPrivacyAndRBACTests(TestCase):
    """
    Verifies Section 9 & 10 (Strict Server-Side Wage Privacy & RBAC Barriers).
    Manager sees operational directory; financial wage/settlement endpoints are 403 Forbidden.
    """

    def setUp(self):
        self.client = Client()
        self.password = "SecretPass123!"

        self.owner = User.objects.create_user(username="w_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.accountant = User.objects.create_user(username="w_acc", password=self.password)
        self.accountant.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant.profile.save()

        self.manager = User.objects.create_user(username="w_mgr", password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.employee_user = User.objects.create_user(username="w_emp", password=self.password)
        self.employee_user.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee_user.profile.save()

        self.employee_record = Employee.objects.create(
            employee_code="EMP-001",
            full_name="Kisan Staff",
            role=Employee.ROLE_TRACTOR_DRIVER,
            wage_type=Employee.WAGE_DAILY,
            base_rate=Decimal('600.00'),
            status=Employee.STATUS_ACTIVE
        )

    def test_owner_and_accountant_can_access_wage_modules(self):
        """Verifies Owner and Accountant have full access to wage listings and financial profiles."""
        self.client.login(username='w_owner', password=self.password)
        self.assertEqual(self.client.get(reverse('employees:wages')).status_code, 200)
        self.assertEqual(self.client.get(reverse('employees:financial_profile', args=[self.employee_record.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('employees:accrual_create')).status_code, 200)
        self.assertEqual(self.client.get(reverse('employees:payout_create')).status_code, 200)

        self.client.login(username='w_acc', password=self.password)
        self.assertEqual(self.client.get(reverse('employees:wages')).status_code, 200)
        self.assertEqual(self.client.get(reverse('employees:financial_profile', args=[self.employee_record.id])).status_code, 200)

    def test_manager_has_operational_access_but_strictly_forbidden_from_wages(self):
        """
        Proof of Server-Side Salary Privacy:
        Manager CAN access operational roster `/employees/`,
        but is strictly FORBIDDEN (403) from `/employees/wages/*` and financial profiles.
        """
        self.client.login(username='w_mgr', password=self.password)

        # Operational directory allowed
        self.assertEqual(self.client.get(reverse('employees:list')).status_code, 200)

        # Financial wage endpoints strictly forbidden (403)
        self.assertEqual(self.client.get(reverse('employees:wages')).status_code, 403)
        self.assertEqual(self.client.get(reverse('employees:financial_profile', args=[self.employee_record.id])).status_code, 403)
        self.assertEqual(self.client.get(reverse('employees:accrual_create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('employees:payout_create')).status_code, 403)

    def test_employee_role_forbidden_from_all_wage_endpoints(self):
        """Verifies Employee is strictly blocked (403) from accessing all wage management endpoints."""
        self.client.login(username='w_emp', password=self.password)

        self.assertEqual(self.client.get(reverse('employees:wages')).status_code, 403)
        self.assertEqual(self.client.get(reverse('employees:financial_profile', args=[self.employee_record.id])).status_code, 403)
        self.assertEqual(self.client.get(reverse('employees:accrual_create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('employees:payout_create')).status_code, 403)
