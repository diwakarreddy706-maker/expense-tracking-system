from django.shortcuts import render
from django.http import JsonResponse


def dashboard_index(request):
    """
    Renders the executive dashboard template with the approved layout hierarchy.
    """
    context = {
        'title': 'Executive Dashboard',
        'is_foundation_mode': True,
    }
    return render(request, 'dashboard/index.html', context)


def dashboard_summary_api(request):
    """
    Health/status API for dashboard summary endpoint.
    """
    return JsonResponse({
        'status': 'foundation_ready',
        'module': 'dashboard',
        'message': 'Dashboard API endpoint initialized for Phase 1.'
    })
