from django.shortcuts import render
from django.http import JsonResponse, HttpResponseForbidden
from apps.accounts.decorators import role_required, accountant_or_owner_required


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def report_index_view(request):
    """
    Overview hub for all reporting modules.
    Accessible to Owner, Accountant, and Manager.
    """
    return render(request, 'base.html', {'title': 'Reports Hub'})


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def operational_reports_view(request):
    """
    Operational analytics (Fuel consumption, Machine hours, Work logs).
    Accessible to Owner, Accountant, and Manager.
    """
    return render(request, 'base.html', {'title': 'Operational Reports'})


@accountant_or_owner_required
def financial_reports_view(request):
    """
    Financial reports (P&L, Cashflow, Account Ledgers, Tax summaries).
    Strictly restricted to Owner and Accountant.
    """
    return render(request, 'base.html', {'title': 'Financial Reports'})


@accountant_or_owner_required
def financial_export_view(request):
    """
    Financial export endpoint (Excel, PDF, CSV).
    Strictly restricted to Owner and Accountant.
    """
    return JsonResponse({'status': 'authorized', 'format': request.GET.get('format', 'excel')})
