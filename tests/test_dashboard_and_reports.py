"""
Phase 10 Comprehensive Test Suite: Executive Dashboard & Business Analytics.
Validates:
- Dashboard KPI calculation integrity across Today's Money, 3 Obligation Silos,
  Operational Cost hierarchy, Budget controls, and Machine Operating Intelligence.
- Authoritative calculation services without UI-side derivation.
- Multi-dimensional reporting engine (Expenses, Fleet Costs, Fuel consumption).
- CSV export formatting and Decimal precision.
- Server-side RBAC access boundaries on reporting portals.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.finance.models import (
    Account, AccountTransaction,
    Customer, Supplier,
    Receivable, CustomerPayment,
    Payable, SupplierPayment,
    DailyClosing
)
from apps.expenses.models import Expense, ExpenseCategory
from apps.machines.models import Machine, MachineType
from apps.fuel.models import FuelEntry
from apps.employees.models import Employee, EmployeePayment
from apps.budgets.models import Budget, BudgetItem
from apps.dashboard.services.analytics_service import DashboardAnalyticsService
from apps.reports.services.report_service import ReportService


class ExecutiveDashboardAnalyticsTests(TestCase):
    """Verifies backend KPI aggregation and calculations on the executive dashboard."""

    def setUp(self):
        self.password = "SafePassword123!"
        self.owner = User.objects.create_user(username="dash_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.account = Account.objects.create(
            account_name="Main Operations Bank",
            account_type=Account.TYPE_BANK_CURRENT,
            opening_balance=Decimal('100000.00'),
            current_balance=Decimal('100000.00'),
            is_active=True
        )

        self.fuel_cat = ExpenseCategory.objects.create(name="Diesel & Fuel", code="CAT-FUEL")
        self.repair_cat = ExpenseCategory.objects.create(name="Repairs & Parts", code="CAT-REPAIRS")

        self.trac_type = MachineType.objects.create(name="Tractor", code="TRAC")
        self.tractor = Machine.objects.create(
            machine_code="TRAC-10",
            name="Mahindra 575 DI",
            machine_type=self.trac_type,
            current_meter_reading=Decimal('50.00'),
            meter_unit=Machine.METER_HOURS,
            status=Machine.STATUS_ACTIVE
        )

        self.customer = Customer.objects.create(customer_code="CUST-01", name="Suresh Patil")
        self.supplier = Supplier.objects.create(supplier_code="SUPP-01", name="HPCL Fuel Station")

        self.today = timezone.now().date()

    def test_dashboard_todays_money_and_obligations_kpis(self):
        """
        Proof of Executive KPI Synthesis:
        1. Today Inflow: ₹25,000 (Customer Payment)
        2. Today Outflow: ₹10,000 (Expense)
        3. Today Expected Closing: ₹115,000
        4. Customer Receivable outstanding: ₹15,000 (₹40k total - ₹25k paid)
        5. Supplier Payable outstanding: ₹20,000 (₹20k total - ₹0 paid)
        """
        # Create Receivable ₹40,000 and receive ₹25,000 today
        rcv = Receivable.objects.create(
            receivable_code="RCV-DASH-01",
            customer=self.customer,
            total_amount=Decimal('40000.00'),
            received_amount=Decimal('25000.00'),
            status=Receivable.STATUS_PARTIAL,
            created_by=self.owner
        )
        CustomerPayment.objects.create(
            payment_code="CPAY-DASH-01",
            receivable=rcv,
            account=self.account,
            payment_date=self.today,
            amount=Decimal('25000.00'),
            created_by=self.owner
        )
        AccountTransaction.objects.create(
            account=self.account,
            transaction_date=self.today,
            transaction_type=AccountTransaction.TYPE_RECEIVABLE_PAYMENT,
            direction=AccountTransaction.DIRECTION_CREDIT,
            amount=Decimal('25000.00'),
            created_by=self.owner
        )

        # Log Expense ₹10,000 today
        Expense.objects.create(
            expense_code="EXP-DASH-01",
            account=self.account,
            category=self.fuel_cat,
            machine=self.tractor,
            amount=Decimal('10000.00'),
            expense_date=self.today,
            created_by=self.owner
        )
        AccountTransaction.objects.create(
            account=self.account,
            transaction_date=self.today,
            transaction_type=AccountTransaction.TYPE_EXPENSE,
            direction=AccountTransaction.DIRECTION_DEBIT,
            amount=Decimal('10000.00'),
            created_by=self.owner
        )

        # Create Supplier Payable ₹20,000 (Unpaid)
        Payable.objects.create(
            payable_code="PAY-DASH-01",
            supplier=self.supplier,
            total_amount=Decimal('20000.00'),
            paid_amount=Decimal('0.00'),
            status=Payable.STATUS_UNPAID,
            created_by=self.owner
        )

        # Execute Analytics KPI aggregation
        kpis = DashboardAnalyticsService.get_executive_dashboard_kpis(target_date=self.today, user=self.owner)

        # Assert Today's Money
        self.assertEqual(kpis['opening_balance'], Decimal('100000.00'))
        self.assertEqual(kpis['money_received_today'], Decimal('25000.00'))
        self.assertEqual(kpis['money_spent_today'], Decimal('10000.00'))
        self.assertEqual(kpis['expected_closing_today'], Decimal('115000.00'))

        # Assert 3 Obligation Silos
        self.assertEqual(kpis['receivables_to_receive'], Decimal('15000.00'))
        self.assertEqual(kpis['payables_to_pay'], Decimal('20000.00'))

        # Assert Machine Cost Intelligence (TRAC-10: ₹10,000 / 50 hrs = ₹200.00/hr)
        m_cost = next(m for m in kpis['machine_costs'] if m['machine_code'] == 'TRAC-10')
        self.assertEqual(m_cost['fuel_cost'], Decimal('10000.00'))
        self.assertEqual(m_cost['total_cost'], Decimal('10000.00'))
        self.assertEqual(m_cost['cost_per_unit'], Decimal('200.00'))


class ReportingAndExportTests(TestCase):
    """Verifies report generation, operational metrics, and CSV export functionality."""

    def setUp(self):
        self.password = "SafePassword123!"
        self.owner = User.objects.create_user(username="rep_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.account = Account.objects.create(
            account_name="Main Bank",
            account_type=Account.TYPE_BANK_CURRENT,
            opening_balance=Decimal('50000.00'),
            current_balance=Decimal('50000.00'),
            is_active=True
        )

        self.cat1 = ExpenseCategory.objects.create(name="Diesel & Fuel", code="CAT-D")
        self.cat2 = ExpenseCategory.objects.create(name="Repairs", code="CAT-R")

        self.exp1 = Expense.objects.create(
            expense_code="EXP-REP-01",
            account=self.account,
            category=self.cat1,
            amount=Decimal('8000.00'),
            expense_date=timezone.datetime(2026, 8, 1).date(),
            created_by=self.owner
        )
        self.exp2 = Expense.objects.create(
            expense_code="EXP-REP-02",
            account=self.account,
            category=self.cat2,
            amount=Decimal('4000.00'),
            expense_date=timezone.datetime(2026, 8, 2).date(),
            created_by=self.owner
        )

    def test_expense_report_filtering_and_category_breakdown(self):
        """Verifies report service returns correct filtered totals and category grouping."""
        rep = ReportService.get_expense_report(category_id=self.cat1.id)
        self.assertEqual(rep['total_amount'], Decimal('8000.00'))
        self.assertEqual(rep['total_count'], 1)

        rep_all = ReportService.get_expense_report()
        self.assertEqual(rep_all['total_amount'], Decimal('12000.00'))
        self.assertEqual(rep_all['total_count'], 2)

    def test_csv_export_format_and_headers(self):
        """Verifies CSV export contains valid columns and formatted numbers."""
        response = ReportService.export_expenses_to_csv(Expense.objects.all())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8')
        self.assertIn("Expense Code,Date,Category,Description,Amount (INR)", content)
        self.assertIn("EXP-REP-01", content)
        self.assertIn("8000.00", content)


class DashboardAndReportsRBACTests(TestCase):
    """Verifies server-side RBAC on Dashboard and Reporting views."""

    def setUp(self):
        self.client = Client()
        self.password = "SafePass123!"

        self.owner = User.objects.create_user(username="u_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.manager = User.objects.create_user(username="u_mgr", password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.employee = User.objects.create_user(username="u_emp", password=self.password)
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

    def test_owner_can_access_all_dashboards_and_reports(self):
        """Verifies Owner has full access to all dashboards, reports, and financial exports."""
        self.client.login(username='u_owner', password=self.password)
        self.assertEqual(self.client.get(reverse('dashboard:index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('dashboard:api_summary')).status_code, 200)
        self.assertEqual(self.client.get(reverse('reports:index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('reports:expenses')).status_code, 200)
        self.assertEqual(self.client.get(reverse('reports:operational')).status_code, 200)
        self.assertEqual(self.client.get(reverse('reports:financial')).status_code, 200)

    def test_manager_can_access_operational_reports_but_forbidden_from_financial_reports(self):
        """Verifies Manager can view operational/expense reports but is blocked from financial statements."""
        self.client.login(username='u_mgr', password=self.password)
        self.assertEqual(self.client.get(reverse('dashboard:index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('reports:index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('reports:operational')).status_code, 200)
        self.assertEqual(self.client.get(reverse('reports:expenses')).status_code, 200)

        # Financial audits restricted to Owner & Accountant
        self.assertEqual(self.client.get(reverse('reports:financial')).status_code, 403)
        self.assertEqual(self.client.get(reverse('reports:export')).status_code, 403)
