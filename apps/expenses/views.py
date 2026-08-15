from django.shortcuts import render
from django.http import JsonResponse


def expense_list_view(request):
    """Placeholder view for Phase 4 expense engine."""
    return render(request, 'base.html', {'title': 'Expenses'})
