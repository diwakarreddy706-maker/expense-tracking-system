from django.shortcuts import render
from apps.accounts.decorators import manager_or_above_required


@manager_or_above_required
def employee_list_view(request):
    """Placeholder view for employees & wages (Owner, Accountant, Manager)."""
    return render(request, 'base.html', {'title': 'Employees & Wages'})
