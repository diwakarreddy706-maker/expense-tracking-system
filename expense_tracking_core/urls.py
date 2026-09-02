"""
Root URL Configuration for Expense Tracking & Management System.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.http import JsonResponse

from apps.dashboard.views import dashboard_index
from apps.expenses.views import expense_quick_api_view


def health_check(request):
    """
    Standard health check endpoint to verify system status.
    """
    return JsonResponse({
        'status': 'healthy',
        'application': 'Expense Tracking & Management System',
        'version': '1.0.0-production',
        'phase': 'Phase 11 - Production Hardening & QA'
    })


def custom_bad_request_view(request, exception=None):
    return render(request, 'errors/400.html', status=400)


def custom_permission_denied_view(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def custom_page_not_found_view(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def custom_server_error_view(request):
    return render(request, 'errors/500.html', status=500)


handler400 = 'expense_tracking_core.urls.custom_bad_request_view'
handler403 = 'expense_tracking_core.urls.custom_permission_denied_view'
handler404 = 'expense_tracking_core.urls.custom_page_not_found_view'
handler500 = 'expense_tracking_core.urls.custom_server_error_view'

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('', dashboard_index, name='root'),
    path('dashboard/', include('apps.dashboard.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('expenses/', include('apps.expenses.urls')),
    path('api/expenses/quick/', expense_quick_api_view, name='api_expenses_quick'),
    path('fuel/', include('apps.fuel.urls')),
    path('machines/', include('apps.machines.urls')),
    path('employees/', include('apps.employees.urls')),
    path('finance/', include('apps.finance.urls')),
    path('budgets/', include('apps.budgets.urls')),
    path('reports/', include('apps.reports.urls')),
]

# Static & Media file handling in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
