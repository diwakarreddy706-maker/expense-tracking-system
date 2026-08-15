from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
def dashboard_index(request):
    """
    Renders the executive dashboard template with the approved layout hierarchy.
    Protected by server-side authentication.
    """
    context = {
        'title': 'Executive Dashboard',
        'is_foundation_mode': True,
        'user_role': request.user.profile.role if hasattr(request.user, 'profile') else 'EMPLOYEE',
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def dashboard_summary_api(request):
    """
    Health/status API for dashboard summary endpoint.
    Protected by server-side authentication.
    """
    return JsonResponse({
        'status': 'foundation_ready',
        'module': 'dashboard',
        'user': request.user.username,
        'role': request.user.profile.role if hasattr(request.user, 'profile') else 'EMPLOYEE',
        'message': 'Dashboard API endpoint initialized and authenticated.'
    })
