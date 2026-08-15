from django.shortcuts import render


def budget_list_view(request):
    """Placeholder view for Phase 10 budgets."""
    return render(request, 'base.html', {'title': 'Budgets'})
