from django.shortcuts import render


def employee_list_view(request):
    """Placeholder view for Phase 6 employees & wages."""
    return render(request, 'base.html', {'title': 'Employees & Wages'})
