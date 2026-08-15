from django.shortcuts import render
from django.http import JsonResponse
from apps.accounts.decorators import manager_or_above_required, accountant_or_owner_required, owner_required


@manager_or_above_required
def employee_list_view(request):
    """Operational employee roster (Owner, Accountant, Manager)."""
    return render(request, 'base.html', {'title': 'Employee Directory'})


@accountant_or_owner_required
def employee_wages_view(request):
    """Financial wage accruals & advance payouts (Owner & Accountant only)."""
    return render(request, 'base.html', {'title': 'Employee Wages & Payouts'})


@owner_required
def employee_delete_view(request, employee_id):
    """Strictly Owner-only: employee profile removal."""
    return JsonResponse({'status': 'deleted', 'id': employee_id})
