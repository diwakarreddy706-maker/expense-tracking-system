"""
Authoritative Executive Dashboard Analytics Service Layer.
Connects directly to backend financial engines (DailyClosingService, BudgetService,
CustomerReceivableService, SupplierPayableService, EmployeeFinancialService).
Guarantees Decimal precision and strict separation between Liquid Cash, Profit, and Obligations.
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Sum, Q, F

from apps.finance.models import (
    Account, AccountTransaction,
    Customer, Supplier,
    Receivable, CustomerPayment,
    Payable, SupplierPayment,
    DailyClosing
)
from apps.finance.services.closing_service import DailyClosingService
from apps.finance.services.settlement_service import (
    CustomerReceivableService,
    SupplierPayableService
)
from apps.employees.models import Employee, EmployeePayment
from apps.expenses.models import Expense, ExpenseCategory
from apps.machines.models import Machine
from apps.budgets.models import Budget
from apps.budgets.services.budget_service import BudgetService


class DashboardAnalyticsService:
    """
    Authoritative backend engine for the Executive Business Dashboard.
    Every KPI is derived directly from underlying database models & services.
    """

    @classmethod
    def get_executive_dashboard_kpis(cls, target_date=None, user=None) -> Dict[str, Any]:
        """
        Gathers comprehensive business metrics for the executive dashboard:
        1. Today's Money (Authoritative Liquid Cash/Bank Inflow/Outflow/Expected vs Counted)
        2. Outstanding Money (Receivables to receive, Payables to pay, Employee dues)
        3. Operational Cost Breakdown (Current Month)
        4. Budget Control Status (Current Month)
        5. Machine Operating Costs (Fleet comparison)
        6. Recent Activity Streams
        """
        zero = Decimal('0.00')
        today = target_date or timezone.now().date()
        now = timezone.now()

        # ====================================================================
        # 1. TODAY'S MONEY (Liquid Cash & Bank Position)
        # ====================================================================
        daily_reconciliation = DailyClosingService.calculate_daily_reconciliation(
            closing_date=today,
            scope=DailyClosing.SCOPE_CONSOLIDATED
        )

        opening_balance = daily_reconciliation['opening_balance']
        money_received_today = daily_reconciliation['total_inflow']
        money_spent_today = daily_reconciliation['total_outflow']
        expected_closing_today = daily_reconciliation['expected_closing']

        # Check if today is closed & locked
        closed_snapshot = DailyClosing.objects.filter(
            closing_date=today,
            scope=DailyClosing.SCOPE_CONSOLIDATED,
            account=None
        ).first()

        if closed_snapshot:
            actual_closing_today = closed_snapshot.actual_closing
            closing_difference = closed_snapshot.discrepancy
            closing_status = closed_snapshot.status
            is_day_closed = True
            closed_by_user = closed_snapshot.closed_by.username
        else:
            actual_closing_today = None
            closing_difference = zero
            closing_status = 'PENDING_CLOSING'
            is_day_closed = False
            closed_by_user = None

        # Total Current Cached Liquid Balance across active accounts
        total_current_liquid = Account.objects.filter(
            is_deleted=False, is_active=True
        ).aggregate(s=Sum('current_balance'))['s'] or zero
        total_current_liquid = total_current_liquid.quantize(Decimal('0.01'))

        # ====================================================================
        # 2. OUTSTANDING MONEY STATES (3 Separate Obligation Silos)
        # ====================================================================
        # Customer Receivables (Money to Receive)
        rcv_data = Receivable.objects.filter(
            is_deleted=False, is_reversed=False
        ).aggregate(t=Sum('total_amount'), r=Sum('received_amount'))
        receivables_to_receive = ((rcv_data['t'] or zero) - (rcv_data['r'] or zero)).quantize(Decimal('0.01'))

        # Supplier Payables (Money to Pay)
        pay_data = Payable.objects.filter(
            is_deleted=False, is_reversed=False
        ).aggregate(t=Sum('total_amount'), p=Sum('paid_amount'))
        payables_to_pay = ((pay_data['t'] or zero) - (pay_data['p'] or zero)).quantize(Decimal('0.01'))

        # Employee Wages & Liabilities Outstanding
        emp_p = EmployeePayment.objects.filter(is_deleted=False, is_reversed=False)
        emp_accruals = emp_p.filter(payment_type=EmployeePayment.TYPE_SALARY_ACCRUAL).aggregate(s=Sum('amount'))['s'] or zero
        emp_bonuses = emp_p.filter(payment_type=EmployeePayment.TYPE_BONUS).aggregate(s=Sum('amount'))['s'] or zero
        emp_advances = emp_p.filter(payment_type=EmployeePayment.TYPE_ADVANCE_PAYOUT).aggregate(s=Sum('amount'))['s'] or zero
        emp_settlements = emp_p.filter(payment_type=EmployeePayment.TYPE_SALARY_SETTLEMENT).aggregate(s=Sum('amount'))['s'] or zero
        employee_wages_due = ((emp_accruals + emp_bonuses) - (emp_advances + emp_settlements)).quantize(Decimal('0.01'))

        # ====================================================================
        # 3. OPERATIONAL SPENDING BREAKDOWN (Current Month)
        # ====================================================================
        month_expenses = Expense.objects.filter(
            expense_date__year=now.year,
            expense_date__month=now.month,
            is_deleted=False,
            is_reversed=False
        )

        fuel_cost_month = month_expenses.filter(
            Q(category__name__icontains='fuel') | Q(category__name__icontains='diesel') | Q(category__code__icontains='fuel')
        ).aggregate(s=Sum('amount'))['s'] or zero

        maintenance_cost_month = month_expenses.filter(
            Q(category__name__icontains='repair') | Q(category__name__icontains='maintenance') | Q(category__name__icontains='spare')
        ).aggregate(s=Sum('amount'))['s'] or zero

        # Employee wage payouts disbursed this month
        emp_payouts_month = emp_p.filter(
            date__year=now.year,
            date__month=now.month,
            payment_type__in=[EmployeePayment.TYPE_ADVANCE_PAYOUT, EmployeePayment.TYPE_SALARY_SETTLEMENT]
        ).aggregate(s=Sum('amount'))['s'] or zero

        total_expenses_month = month_expenses.aggregate(s=Sum('amount'))['s'] or zero
        other_expenses_month = (total_expenses_month - fuel_cost_month - maintenance_cost_month)
        if other_expenses_month < zero:
            other_expenses_month = zero

        # ====================================================================
        # 4. BUDGET CONTROL SUMMARY (Current Month)
        # ====================================================================
        budget_summary = BudgetService.get_budget_dashboard_summary(
            period_month=now.month,
            period_year=now.year
        )

        # ====================================================================
        # 5. MACHINE OPERATING COSTS INTELLIGENCE (Fleet Comparison)
        # ====================================================================
        machines = Machine.objects.filter(is_deleted=False).select_related('machine_type')
        machine_cost_list = []

        for m in machines:
            m_expenses = Expense.objects.filter(
                machine=m,
                is_deleted=False,
                is_reversed=False
            )
            m_fuel = m_expenses.filter(
                Q(category__name__icontains='fuel') | Q(category__name__icontains='diesel') | Q(category__code__icontains='fuel')
            ).aggregate(s=Sum('amount'))['s'] or zero

            m_maint = m_expenses.exclude(
                Q(category__name__icontains='fuel') | Q(category__name__icontains='diesel') | Q(category__code__icontains='fuel')
            ).aggregate(s=Sum('amount'))['s'] or zero

            m_total_cost = (m_fuel + m_maint).quantize(Decimal('0.01'))
            meter = m.current_meter_reading or zero

            cost_per_unit = (m_total_cost / meter).quantize(Decimal('0.01')) if meter > zero else zero

            machine_cost_list.append({
                'machine_id': m.id,
                'machine_code': m.machine_code,
                'name': m.name,
                'machine_type': m.machine_type.name if m.machine_type else '--',
                'fuel_cost': m_fuel.quantize(Decimal('0.01')),
                'maintenance_cost': m_maint.quantize(Decimal('0.01')),
                'total_cost': m_total_cost,
                'current_meter': meter,
                'meter_unit': m.get_meter_unit_display(),
                'cost_per_unit': cost_per_unit,
                'status': m.status,
            })

        # ====================================================================
        # 6. RECENT ACTIVITY STREAMS
        # ====================================================================
        recent_expenses = Expense.objects.filter(
            is_deleted=False, is_reversed=False
        ).select_related('category', 'account', 'machine', 'created_by').order_by('-expense_date', '-id')[:5]

        recent_customer_payments = CustomerPayment.objects.filter(
            is_deleted=False, is_reversed=False
        ).select_related('receivable__customer', 'account').order_by('-payment_date', '-id')[:5]

        recent_supplier_payments = SupplierPayment.objects.filter(
            is_deleted=False, is_reversed=False
        ).select_related('payable__supplier', 'account').order_by('-payment_date', '-id')[:5]

        return {
            'today': today,
            'today_formatted': today.strftime('%d %B %Y'),
            # 1. Today's Money
            'opening_balance': opening_balance,
            'money_received_today': money_received_today,
            'money_spent_today': money_spent_today,
            'expected_closing_today': expected_closing_today,
            'actual_closing_today': actual_closing_today,
            'closing_difference': closing_difference,
            'closing_status': closing_status,
            'is_day_closed': is_day_closed,
            'closed_by_user': closed_by_user,
            'total_current_liquid': total_current_liquid,
            # 2. Outstanding Money
            'receivables_to_receive': receivables_to_receive,
            'payables_to_pay': payables_to_pay,
            'employee_wages_due': employee_wages_due,
            # 3. Operational Costs (Month)
            'fuel_cost_month': fuel_cost_month.quantize(Decimal('0.01')),
            'maintenance_cost_month': maintenance_cost_month.quantize(Decimal('0.01')),
            'emp_payouts_month': emp_payouts_month.quantize(Decimal('0.01')),
            'other_expenses_month': other_expenses_month.quantize(Decimal('0.01')),
            'total_expenses_month': total_expenses_month.quantize(Decimal('0.01')),
            # 4. Budget Controls (Month)
            'budget_summary': budget_summary,
            # 5. Machine Cost Intelligence
            'machine_costs': machine_cost_list,
            # 6. Recent Activity
            'recent_expenses': recent_expenses,
            'recent_customer_payments': recent_customer_payments,
            'recent_supplier_payments': recent_supplier_payments,
        }
