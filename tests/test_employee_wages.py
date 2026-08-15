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
from apps.employees.models import Employee, EmployeePayment, EmployeeCompensation
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


class EmployeeMultiRateCompensationTests(TestCase):
    """
    Comprehensive test suite for Multi-Rate Employee Compensation (EmployeeCompensation).
    Tests simultaneous multi-rates (Daily + Monthly), historical rates, effective-date overlaps,
    decimal precision, payment traceability, units calculation, and zero ledger mutation.
    """

    def setUp(self):
        self.client = Client()
        self.password = "SafePassword123!"

        self.owner = User.objects.create_user(username="comp_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.accountant = User.objects.create_user(username="comp_acc", password=self.password)
        self.accountant.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant.profile.save()

        self.manager = User.objects.create_user(username="comp_mgr", password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.account = Account.objects.create(
            account_name="Master Business Cash",
            account_type=Account.TYPE_CASH,
            opening_balance=Decimal('100000.00'),
            current_balance=Decimal('100000.00'),
            is_active=True
        )

        self.test_worker = Employee.objects.create(
            employee_code="EMP-TEST-01",
            full_name="Test Multi-Rate Worker",
            role=Employee.ROLE_TRACTOR_DRIVER,
            status=Employee.STATUS_ACTIVE
        )

    def test_multiple_active_compensation_types_simultaneously(self):
        """
        Verifies that an employee can have multiple active compensation structures simultaneously
        (e.g., Daily Wage ₹200.00 + Monthly Salary ₹10,000.00).
        """
        comp_daily = EmployeeFinancialService.add_compensation(
            user=self.owner,
            employee=self.test_worker,
            wage_type=EmployeeCompensation.WAGE_DAILY,
            rate=Decimal('200.00'),
            notes="Standard Daily Allowance"
        )
        comp_monthly = EmployeeFinancialService.add_compensation(
            user=self.owner,
            employee=self.test_worker,
            wage_type=EmployeeCompensation.WAGE_MONTHLY,
            rate=Decimal('10000.00'),
            notes="Base Monthly Retainer"
        )

        active_comps = list(self.test_worker.active_compensations)
        self.assertEqual(len(active_comps), 2)
        self.assertIn(comp_daily, active_comps)
        self.assertIn(comp_monthly, active_comps)

        # Helper lookups
        self.assertEqual(self.test_worker.get_active_rate(EmployeeCompensation.WAGE_DAILY).rate, Decimal('200.00'))
        self.assertEqual(self.test_worker.get_active_rate(EmployeeCompensation.WAGE_MONTHLY).rate, Decimal('10000.00'))

    def test_compensation_creation_does_not_affect_financial_ledger_or_balance(self):
        """
        Proof of Financial Safety:
        Creating compensation rates is pure configuration/master data.
        It must NOT create AccountTransactions or mutate Account balances.
        """
        initial_balance = self.account.current_balance
        initial_tx_count = AccountTransaction.objects.count()
        initial_payment_count = EmployeePayment.objects.count()

        EmployeeFinancialService.add_compensation(
            user=self.owner,
            employee=self.test_worker,
            wage_type=EmployeeCompensation.WAGE_DAILY,
            rate=Decimal('200.00')
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance)
        self.assertEqual(AccountTransaction.objects.count(), initial_tx_count)
        self.assertEqual(EmployeePayment.objects.count(), initial_payment_count)

    def test_effective_date_history_preservation(self):
        """
        Verifies historical rate preservation:
        Past rate of ₹200 (Jan to Aug) is updated to ₹250 (Sept onward) without mutating historical records.
        """
        jan_1 = timezone.datetime(2026, 1, 1).date()
        aug_31 = timezone.datetime(2026, 8, 31).date()
        sep_1 = timezone.datetime(2026, 9, 1).date()

        # Step 1: Initial rate for Jan-Aug
        c1 = EmployeeFinancialService.add_compensation(
            user=self.owner,
            employee=self.test_worker,
            wage_type=EmployeeCompensation.WAGE_DAILY,
            rate=Decimal('200.00'),
            effective_from=jan_1,
            effective_to=aug_31
        )

        # Step 2: Revised rate starting Sept 1
        c2 = EmployeeFinancialService.add_compensation(
            user=self.owner,
            employee=self.test_worker,
            wage_type=EmployeeCompensation.WAGE_DAILY,
            rate=Decimal('250.00'),
            effective_from=sep_1,
            effective_to=None
        )

        # Both records exist and history is intact
        self.assertEqual(self.test_worker.compensations.count(), 2)
        c1.refresh_from_db()
        self.assertEqual(c1.rate, Decimal('200.00'))
        self.assertEqual(c1.effective_to, aug_31)

        c2.refresh_from_db()
        self.assertEqual(c2.rate, Decimal('250.00'))
        self.assertIsNone(c2.effective_to)

    def test_same_wage_type_overlapping_period_prevention(self):
        """
        Verifies that adding an overlapping active period for the SAME wage_type raises ValidationError.
        """
        EmployeeFinancialService.add_compensation(
            user=self.owner,
            employee=self.test_worker,
            wage_type=EmployeeCompensation.WAGE_DAILY,
            rate=Decimal('200.00'),
            effective_from=timezone.datetime(2026, 1, 1).date(),
            effective_to=None
        )

        # Attempt to add another open-ended DAILY_WAGE starting 2026-06-01 without closing the previous
        with self.assertRaises(ValidationError):
            EmployeeFinancialService.add_compensation(
                user=self.owner,
                employee=self.test_worker,
                wage_type=EmployeeCompensation.WAGE_DAILY,
                rate=Decimal('300.00'),
                effective_from=timezone.datetime(2026, 6, 1).date(),
                effective_to=None
            )

    def test_payment_compensation_traceability_and_units_calculation(self):
        """
        Verifies units-based accrual calculation and full traceability:
        25 days × ₹200.00/day = ₹5,000.00 accrued wage liability.
        """
        comp = EmployeeFinancialService.add_compensation(
            user=self.owner,
            employee=self.test_worker,
            wage_type=EmployeeCompensation.WAGE_DAILY,
            rate=Decimal('200.00')
        )

        accrual = EmployeeFinancialService.record_salary_accrual(
            user=self.owner,
            employee=self.test_worker,
            compensation=comp,
            units_logged=Decimal('25.00'),
            notes="25 days field operation"
        )

        self.assertEqual(accrual.compensation, comp)
        self.assertEqual(accrual.units_logged, Decimal('25.00'))
        self.assertEqual(accrual.amount, Decimal('5000.00'))

        # Verify balance reflects exact accrued amount
        balances = EmployeeFinancialService.calculate_employee_balances(self.test_worker.id)
        self.assertEqual(balances['total_accruals'], Decimal('5000.00'))
        self.assertEqual(balances['net_outstanding'], Decimal('5000.00'))

    def test_decimal_precision_strictness(self):
        """Verifies Decimal precision on compensation rates and units calculations."""
        comp = EmployeeFinancialService.add_compensation(
            user=self.owner,
            employee=self.test_worker,
            wage_type=EmployeeCompensation.WAGE_PER_ACRE,
            rate=Decimal('333.33')
        )

        accrual = EmployeeFinancialService.record_salary_accrual(
            user=self.owner,
            employee=self.test_worker,
            compensation=comp,
            units_logged=Decimal('12.50')
        )

        # 333.33 * 12.50 = 4166.6250 -> quantized to Decimal('4166.62') with ROUND_HALF_EVEN
        self.assertEqual(accrual.amount, Decimal('4166.62'))
        self.assertIsInstance(accrual.amount, Decimal)

    def test_compensation_audit_logging(self):
        """Verifies creating, updating, and deactivating compensations generates AuditLog entries."""
        comp = EmployeeFinancialService.add_compensation(
            user=self.owner,
            employee=self.test_worker,
            wage_type=EmployeeCompensation.WAGE_DAILY,
            rate=Decimal('200.00')
        )
        audit_create = AuditLog.objects.filter(action=AuditLog.ACTION_CREATE, entity_type='EmployeeCompensation', entity_id=str(comp.id)).first()
        self.assertIsNotNone(audit_create)
        self.assertEqual(audit_create.changes_json['rate'], '200.00')

        # Update
        EmployeeFinancialService.update_compensation(
            user=self.owner,
            compensation_id=comp.id,
            rate=Decimal('220.00')
        )
        audit_update = AuditLog.objects.filter(action=AuditLog.ACTION_UPDATE, entity_type='EmployeeCompensation', entity_id=str(comp.id)).order_by('-id').first()
        self.assertIsNotNone(audit_update)
        self.assertEqual(audit_update.changes_json['rate']['new'], '220.00')

    def test_rbac_compensation_endpoints(self):
        """Verifies Manager is blocked (403) from managing compensation rates, Owner/Accountant allowed."""
        # Accountant allowed
        self.client.login(username='comp_acc', password=self.password)
        resp_acc = self.client.get(reverse('employees:compensation_create', args=[self.test_worker.id]))
        self.assertEqual(resp_acc.status_code, 200)

        # Manager forbidden (403)
        self.client.login(username='comp_mgr', password=self.password)
        resp_mgr = self.client.get(reverse('employees:compensation_create', args=[self.test_worker.id]))
        self.assertEqual(resp_mgr.status_code, 403)

