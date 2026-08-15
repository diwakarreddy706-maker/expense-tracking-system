from django.shortcuts import render
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.utils import timezone
from apps.accounts.decorators import role_required, accountant_or_owner_required
from apps.reports.services.report_service import ReportService
from apps.expenses.models import ExpenseCategory
from apps.machines.models import Machine
from apps.finance.models import Account, AccountTransaction, DailyClosing, Supplier


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def report_index_view(request):
    """
    Overview portal for operational and financial reporting suites.
    Accessible to Owner, Accountant, and Manager.
    """
    return render(request, 'reports/report_index.html', {
        'title': 'Business Reports & Analytics Hub'
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def operational_reports_view(request):
    """
    Operational analytics (Machine operating cost sheets & Fuel efficiency).
    Accessible to Owner, Accountant, and Manager.
    """
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    machine_id = request.GET.get('machine', '').strip()

    machine_costs = ReportService.get_machine_cost_report(start_date, end_date)
    fuel_data = ReportService.get_fuel_analysis_report(start_date, end_date, machine_id)

    return render(request, 'reports/operational_reports.html', {
        'machine_costs': machine_costs,
        'fuel_data': fuel_data,
        'machines': Machine.objects.filter(is_deleted=False),
        'start_date': start_date,
        'end_date': end_date,
        'selected_machine': machine_id,
        'title': 'Operational & Machinery Reports',
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def expense_reports_view(request):
    """
    Expense analysis report with multi-parameter filter matrix.
    """
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    category_id = request.GET.get('category', '').strip()
    machine_id = request.GET.get('machine', '').strip()
    payment_method = request.GET.get('payment_method', '').strip()

    report_data = ReportService.get_expense_report(
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
        machine_id=machine_id,
        payment_method=payment_method
    )

    if request.GET.get('format') == 'csv':
        return ReportService.export_expenses_to_csv(report_data['expenses'])

    return render(request, 'reports/expense_report.html', {
        'report_data': report_data,
        'categories': ExpenseCategory.objects.filter(is_deleted=False),
        'machines': Machine.objects.filter(is_deleted=False),
        'start_date': start_date,
        'end_date': end_date,
        'selected_category': category_id,
        'selected_machine': machine_id,
        'selected_method': payment_method,
        'title': 'Comprehensive Expense Analysis Report',
    })


@accountant_or_owner_required
def financial_reports_view(request):
    """
    Financial reports (Central Ledger transactions, Daily Closings, and Liquid reconciliations).
    Strictly restricted to Owner and Accountant.
    """
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    closings = DailyClosing.objects.select_related('account', 'closed_by').order_by('-closing_date', '-id')
    txs = AccountTransaction.objects.filter(is_deleted=False).select_related('account', 'created_by').order_by('-transaction_date', '-id')

    if start_date:
        closings = closings.filter(closing_date__gte=start_date)
        txs = txs.filter(transaction_date__gte=start_date)
    if end_date:
        closings = closings.filter(closing_date__lte=end_date)
        txs = txs.filter(transaction_date__lte=end_date)

    return render(request, 'reports/financial_reports.html', {
        'closings': closings[:50],
        'transactions': txs[:50],
        'start_date': start_date,
        'end_date': end_date,
        'title': 'Financial Statements & Reconciliation Audit',
    })


@accountant_or_owner_required
def financial_export_view(request):
    """
    Financial export endpoint (CSV / Excel).
    Strictly restricted to Owner and Accountant.
    """
    export_type = request.GET.get('type', 'expenses')
    if export_type == 'expenses':
        report_data = ReportService.get_expense_report(
            start_date=request.GET.get('start_date'),
            end_date=request.GET.get('end_date'),
            category_id=request.GET.get('category'),
            machine_id=request.GET.get('machine'),
            payment_method=request.GET.get('payment_method')
        )
        return ReportService.export_expenses_to_csv(report_data['expenses'])

    return JsonResponse({'status': 'authorized', 'export_type': export_type})
