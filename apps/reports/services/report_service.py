"""
Authoritative Business Reports & Financial Export Engine.
Handles Multi-parameter expense filtering, machine operating cost sheets,
fuel consumption & mileage tables, financial ledger extracts, and CSV generators.
"""

import csv
import io
from decimal import Decimal
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Sum, Q, Count
from django.http import HttpResponse

from apps.expenses.models import Expense, ExpenseCategory
from apps.machines.models import Machine
from apps.fuel.models import FuelEntry
from apps.finance.models import (
    Account, AccountTransaction,
    Receivable, CustomerPayment,
    Payable, SupplierPayment,
    DailyClosing
)
from apps.employees.models import Employee, EmployeePayment
from apps.budgets.models import Budget
from apps.budgets.services.budget_service import BudgetService


class ReportService:
    """
    Reporting engine generating structured datasets and CSV downloads.
    """

    @classmethod
    def get_expense_report(
        cls,
        start_date=None,
        end_date=None,
        category_id=None,
        machine_id=None,
        account_id=None,
        payment_method=None
    ) -> Dict[str, Any]:
        """Generates comprehensive expense report with category breakdown."""
        zero = Decimal('0.00')
        qs = Expense.objects.filter(is_deleted=False, is_reversed=False).select_related(
            'category', 'account', 'machine', 'supplier', 'created_by'
        ).order_by('-expense_date', '-id')

        if start_date:
            qs = qs.filter(expense_date__gte=start_date)
        if end_date:
            qs = qs.filter(expense_date__lte=end_date)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if machine_id:
            qs = qs.filter(machine_id=machine_id)
        if account_id:
            qs = qs.filter(account_id=account_id)
        if payment_method:
            qs = qs.filter(payment_method=payment_method)

        total_amount = qs.aggregate(s=Sum('amount'))['s'] or zero
        count = qs.count()

        # Group by category
        cat_group = (
            qs.values('category__name', 'category__code')
            .annotate(total=Sum('amount'), count=Count('id'))
            .order_by('-total')
        )

        return {
            'expenses': qs,
            'total_amount': total_amount.quantize(Decimal('0.01')),
            'total_count': count,
            'category_breakdown': cat_group,
            'start_date': start_date,
            'end_date': end_date,
        }

    @classmethod
    def get_machine_cost_report(cls, start_date=None, end_date=None) -> List[Dict[str, Any]]:
        """Generates fleet operating cost comparison with fuel, parts, and cost/hour."""
        zero = Decimal('0.00')
        machines = Machine.objects.filter(is_deleted=False).select_related('machine_type')
        results = []

        for m in machines:
            exp_qs = Expense.objects.filter(machine=m, is_deleted=False, is_reversed=False)
            if start_date:
                exp_qs = exp_qs.filter(expense_date__gte=start_date)
            if end_date:
                exp_qs = exp_qs.filter(expense_date__lte=end_date)

            fuel_cost = exp_qs.filter(
                Q(category__name__icontains='fuel') | Q(category__name__icontains='diesel') | Q(category__code__icontains='fuel')
            ).aggregate(s=Sum('amount'))['s'] or zero

            maint_cost = exp_qs.exclude(
                Q(category__name__icontains='fuel') | Q(category__name__icontains='diesel') | Q(category__code__icontains='fuel')
            ).aggregate(s=Sum('amount'))['s'] or zero

            total_cost = (fuel_cost + maint_cost).quantize(Decimal('0.01'))
            meter = m.current_meter_reading or zero
            cost_per_unit = (total_cost / meter).quantize(Decimal('0.01')) if meter > zero else zero

            results.append({
                'machine_id': m.id,
                'machine_code': m.machine_code,
                'name': m.name,
                'machine_type': m.machine_type.name if m.machine_type else '--',
                'fuel_cost': fuel_cost.quantize(Decimal('0.01')),
                'maintenance_cost': maint_cost.quantize(Decimal('0.01')),
                'total_cost': total_cost,
                'meter_reading': meter,
                'meter_unit': m.get_meter_unit_display(),
                'cost_per_unit': cost_per_unit,
            })

        return results

    @classmethod
    def get_fuel_analysis_report(cls, start_date=None, end_date=None, machine_id=None) -> Dict[str, Any]:
        """Generates fuel consumption and efficiency analysis."""
        zero = Decimal('0.00')
        qs = FuelEntry.objects.filter(is_deleted=False, linked_expense__is_reversed=False).select_related(
            'machine', 'supplier', 'operator', 'linked_expense'
        ).order_by('-date', '-id')

        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
        if machine_id:
            qs = qs.filter(machine_id=machine_id)

        totals = qs.aggregate(
            total_qty=Sum('quantity'),
            total_cost=Sum('total_amount')
        )
        total_liters = (totals['total_qty'] or zero).quantize(Decimal('0.01'))
        total_cost = (totals['total_cost'] or zero).quantize(Decimal('0.01'))
        avg_rate = (total_cost / total_liters).quantize(Decimal('0.01')) if total_liters > zero else zero

        return {
            'entries': qs,
            'total_liters': total_liters,
            'total_cost': total_cost,
            'avg_rate': avg_rate,
            'count': qs.count(),
        }

    @classmethod
    def export_expenses_to_csv(cls, queryset) -> HttpResponse:
        """Streams CSV format for expense report."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="Expense_Report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Expense Code', 'Date', 'Category', 'Description', 'Amount (INR)',
            'Payment Method', 'Account', 'Machine', 'Supplier / Vendor', 'Created By'
        ])

        for exp in queryset:
            writer.writerow([
                exp.expense_code,
                exp.expense_date.strftime('%Y-%m-%d'),
                exp.category.name if exp.category else '--',
                exp.description or '',
                f"{exp.amount:.2f}",
                exp.get_payment_method_display(),
                exp.account.account_name if exp.account else '--',
                f"{exp.machine.machine_code} - {exp.machine.name}" if exp.machine else '--',
                exp.supplier.name if exp.supplier else '--',
                exp.created_by.username if exp.created_by else '--'
            ])

        return response
