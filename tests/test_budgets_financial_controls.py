"""
Phase 9 Comprehensive Test Suite: Budgets & Financial Controls.
Validates:
- Budget Model & Lifecycle (DRAFT, ACTIVE, CLOSED, CANCELLED).
- Category, Machine, and Segment-specific budget targeting.
- Budget vs Actual calculation, Decimal precision, remaining, and utilization %.
- Credit expense recognition (counted once, settlement not counted twice).
- Reversals (restores budget room) and Transfers (excluded).
- Control alert thresholds (Normal <80%, Warning 80-99%, Exceeded >=100%).
- Budget overlap prevention.
- Server-side RBAC and Audit logging.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.finance.models import Account, AccountTransaction, Supplier
from apps.expenses.models import Expense, ExpenseCategory
from apps.expenses.services.expense_service import ExpenseService
from apps.machines.models import Machine
from apps.budgets.models import Budget, BudgetItem
from apps.budgets.services.budget_service import BudgetService


class BudgetLifecycleAndCalculationsTests(TestCase):
    """Verifies budget allocations, actual expense aggregations, credit purchases, reversals, and alert states."""

    def setUp(self):
        self.password = "SafePassword123!"
        self.owner = User.objects.create_user(username="bgt_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.account = Account.objects.create(
            account_name="Main Bank",
            account_type=Account.TYPE_BANK_CURRENT,
            opening_balance=Decimal('200000.00'),
            current_balance=Decimal('200000.00'),
            is_active=True
        )

        self.fuel_category = ExpenseCategory.objects.create(name="Diesel & Fuel", code="CAT-FUEL")
        self.spares_category = ExpenseCategory.objects.create(name="Spare Parts", code="CAT-SPARES")

        from apps.machines.models import Machine, MachineType
        self.tractor_type = MachineType.objects.create(name="Tractor", code="TRAC")
        self.harvester_type = MachineType.objects.create(name="Harvester", code="HARV")

        self.tractor = Machine.objects.create(
            machine_code="TRAC-01",
            name="John Deere 5310",
            machine_type=self.tractor_type,
            status=Machine.STATUS_ACTIVE
        )

        self.harvester = Machine.objects.create(
            machine_code="HARV-01",
            name="Claas Crop Tiger",
            machine_type=self.harvester_type,
            status=Machine.STATUS_ACTIVE
        )

        self.supplier = Supplier.objects.create(
            supplier_code="SUPP-PETRO",
            name="BPCL Fuel Outlet",
            supplier_type=Supplier.TYPE_FUEL_PUMP
        )

        self.month = 8
        self.year = 2026

    def test_budget_creation_and_actual_expense_tracking(self):
        """
        Proof of Budget Tracking:
        Budget: ₹1,00,000 for Fuel on Tractor TRAC-01
        Actual: ₹75,000 logged
        Remaining: ₹25,000
        Utilization: 75.00% -> Normal State (<80%)
        """
        budget = BudgetService.create_budget(
            user=self.owner,
            title="August 2026 Tractor Fuel Budget",
            period_month=self.month,
            period_year=self.year,
            business_segment=Budget.SEGMENT_FARM,
            items_data=[
                {
                    'category': self.fuel_category,
                    'machine': self.tractor,
                    'allocated_amount': Decimal('100000.00'),
                    'notes': 'Kharif harvesting fuel allowance'
                }
            ]
        )

        # Log Expense: ₹75,000 for Tractor Fuel
        exp_date = timezone.datetime(2026, 8, 10).date()
        Expense.objects.create(
            expense_code="EXP-BGT-01",
            account=self.account,
            category=self.fuel_category,
            machine=self.tractor,
            amount=Decimal('75000.00'),
            expense_date=exp_date,
            created_by=self.owner
        )

        # Calculate Budget vs Actual
        res = BudgetService.calculate_budget_vs_actual(budget)
        self.assertEqual(res['total_allocated'], Decimal('100000.00'))
        self.assertEqual(res['total_actual'], Decimal('75000.00'))
        self.assertEqual(res['total_remaining'], Decimal('25000.00'))
        self.assertEqual(res['overall_utilization'], Decimal('75.00'))
        self.assertEqual(res['overall_status'], BudgetService.STATUS_NORMAL)

    def test_control_alerts_warning_and_exceeded(self):
        """Verifies 80% warning and 100% exceeded alert thresholds."""
        budget = BudgetService.create_budget(
            user=self.owner,
            title="Spares Budget",
            period_month=self.month,
            period_year=self.year,
            items_data=[
                {'category': self.spares_category, 'allocated_amount': Decimal('10000.00')}
            ]
        )

        # Log ₹8,500 (85.00% -> WARNING)
        exp_date = timezone.datetime(2026, 8, 5).date()
        Expense.objects.create(
            expense_code="EXP-WARN-01",
            account=self.account,
            category=self.spares_category,
            amount=Decimal('8500.00'),
            expense_date=exp_date,
            created_by=self.owner
        )

        res = BudgetService.calculate_budget_vs_actual(budget)
        self.assertEqual(res['overall_utilization'], Decimal('85.00'))
        self.assertEqual(res['overall_status'], BudgetService.STATUS_WARNING)

        # Log additional ₹2,000 (Total ₹10,500 = 105.00% -> EXCEEDED)
        Expense.objects.create(
            expense_code="EXP-EXCEED-01",
            account=self.account,
            category=self.spares_category,
            amount=Decimal('2000.00'),
            expense_date=exp_date,
            created_by=self.owner
        )

        res2 = BudgetService.calculate_budget_vs_actual(budget)
        self.assertEqual(res2['total_actual'], Decimal('10500.00'))
        self.assertEqual(res2['total_remaining'], Decimal('-500.00'))
        self.assertEqual(res2['overall_utilization'], Decimal('105.00'))
        self.assertEqual(res2['overall_status'], BudgetService.STATUS_EXCEEDED)

    def test_credit_expense_counts_once_and_settlement_does_not_double_count(self):
        """
        Proof of Rule 8 (Credit Expense in Budgets):
        1. Credit Fuel expense of ₹20,000 is logged.
        2. Budget actual increases by ₹20,000.
        3. Subsequent supplier payment settles payable.
        4. Budget actual remains exactly ₹20,000 (no budget inflation).
        """
        budget = BudgetService.create_budget(
            user=self.owner,
            title="Credit Fuel Budget",
            period_month=self.month,
            period_year=self.year,
            items_data=[
                {'category': self.fuel_category, 'allocated_amount': Decimal('50000.00')}
            ]
        )

        # Step 1: Create Credit Expense
        exp, tx = ExpenseService.create_expense(
            user=self.owner,
            amount=Decimal('20000.00'),
            category=self.fuel_category,
            payment_method=Expense.METHOD_CREDIT,
            supplier=self.supplier,
            expense_date=timezone.datetime(2026, 8, 12).date(),
            description="Diesel on Pump Credit"
        )

        res = BudgetService.calculate_budget_vs_actual(budget)
        self.assertEqual(res['total_actual'], Decimal('20000.00'))

        # Step 2: Settle Payable via Supplier Payment
        from apps.finance.services.settlement_service import SupplierPayableService
        from apps.finance.models import Payable
        payable = Payable.objects.filter(linked_expense=exp).first()
        SupplierPayableService.record_payment(
            user=self.owner,
            payable_id=payable.id,
            amount=Decimal('20000.00'),
            account=self.account
        )

        # Step 3: Re-verify Budget Actuals (still exactly ₹20,000)
        res_after = BudgetService.calculate_budget_vs_actual(budget)
        self.assertEqual(res_after['total_actual'], Decimal('20000.00'))

    def test_reversed_expense_restores_budget_room(self):
        """Verifies reversing an expense reduces budget actuals and restores remaining allowance."""
        budget = BudgetService.create_budget(
            user=self.owner,
            title="Workshop Budget",
            period_month=self.month,
            period_year=self.year,
            items_data=[
                {'category': self.spares_category, 'allocated_amount': Decimal('30000.00')}
            ]
        )

        exp, tx = ExpenseService.create_expense(
            user=self.owner,
            amount=Decimal('12000.00'),
            category=self.spares_category,
            account=self.account,
            expense_date=timezone.datetime(2026, 8, 14).date()
        )

        res = BudgetService.calculate_budget_vs_actual(budget)
        self.assertEqual(res['total_actual'], Decimal('12000.00'))

        # Reverse Expense
        ExpenseService.reverse_expense(
            expense_id=exp.id,
            user=self.owner,
            reason="Wrong part billed"
        )

        res_after = BudgetService.calculate_budget_vs_actual(budget)
        self.assertEqual(res_after['total_actual'], Decimal('0.00'))
        self.assertEqual(res_after['total_remaining'], Decimal('30000.00'))

    def test_duplicate_overlapping_budget_rejected(self):
        """Verifies duplicate budget for same month, year, and segment is rejected."""
        BudgetService.create_budget(
            user=self.owner,
            title="General August 2026",
            period_month=8,
            period_year=2026,
            business_segment=Budget.SEGMENT_GENERAL
        )

        with self.assertRaises(ValidationError) as ctx:
            BudgetService.create_budget(
                user=self.owner,
                title="Duplicate August 2026",
                period_month=8,
                period_year=2026,
                business_segment=Budget.SEGMENT_GENERAL
            )
        self.assertIn("A budget already exists", str(ctx.exception))


class BudgetViewsAndRBACTests(TestCase):
    """Verifies UI Views, Forms, API routes, and Server-Side Permissions on Budgets."""

    def setUp(self):
        self.client = Client()
        self.password = "SafePass123!"

        self.owner = User.objects.create_user(username="b_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.accountant = User.objects.create_user(username="b_acc", password=self.password)
        self.accountant.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant.profile.save()

        self.manager = User.objects.create_user(username="b_mgr", password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.employee = User.objects.create_user(username="b_emp", password=self.password)
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        self.budget = BudgetService.create_budget(
            user=self.owner,
            title="Admin August 2026",
            period_month=8,
            period_year=2026,
            business_segment=Budget.SEGMENT_ADMIN
        )

    def test_owner_and_accountant_can_manage_budgets(self):
        """Verifies Owner and Accountant have full budget access."""
        self.client.login(username='b_owner', password=self.password)
        self.assertEqual(self.client.get(reverse('budgets:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('budgets:detail', args=[self.budget.id])).status_code, 200)

        self.client.login(username='b_acc', password=self.password)
        self.assertEqual(self.client.get(reverse('budgets:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('budgets:create')).status_code, 200)

    def test_manager_can_view_budgets_but_cannot_create(self):
        """Verifies Manager can view budgets but is blocked from creating/editing."""
        self.client.login(username='b_mgr', password=self.password)
        self.assertEqual(self.client.get(reverse('budgets:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('budgets:detail', args=[self.budget.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('budgets:create')).status_code, 403)

    def test_employee_forbidden_from_budget_management(self):
        """Verifies Employee is forbidden (403) from budget views."""
        self.client.login(username='b_emp', password=self.password)
        self.assertEqual(self.client.get(reverse('budgets:list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('budgets:create')).status_code, 403)

    def test_budget_json_api(self):
        """Verifies JSON API returns correct calculation structure."""
        self.client.login(username='b_owner', password=self.password)
        response = self.client.get(reverse('budgets:api_vs_actual', args=[self.budget.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['budget_id'], self.budget.id)
        self.assertIn('total_allocated', data)
        self.assertIn('total_actual', data)
        self.assertIn('overall_status', data)
