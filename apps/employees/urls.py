from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    # Operational Directory
    path('', views.employee_list_view, name='list'),
    path('add/', views.employee_create_view, name='create'),
    path('<int:employee_id>/edit/', views.employee_edit_view, name='edit'),
    path('<int:employee_id>/delete/', views.employee_delete_view, name='delete'),

    # Financial Wages & Payouts (Owner & Accountant)
    path('wages/', views.employee_wages_view, name='wages'),
    path('<int:employee_id>/finance/', views.employee_financial_profile_view, name='financial_profile'),
    path('accruals/add/', views.employee_accrual_create_view, name='accrual_create'),
    path('payouts/add/', views.employee_payout_create_view, name='payout_create'),
    path('payments/<int:payment_id>/reverse/', views.employee_payment_reverse_view, name='payment_reverse'),
]
