from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    # Business Accounts
    path('accounts/', views.accounts_list_view, name='accounts'),
    path('accounts/add/', views.account_create_view, name='account_create'),
    path('accounts/<int:account_id>/edit/', views.account_edit_view, name='account_edit'),
    path('accounts/<int:account_id>/toggle/', views.account_toggle_status_view, name='account_toggle'),

    # Customers
    path('customers/', views.customers_list_view, name='customers'),
    path('customers/add/', views.customer_create_view, name='customer_create'),
    path('customers/<int:customer_id>/edit/', views.customer_edit_view, name='customer_edit'),
    path('customers/<int:customer_id>/delete/', views.customer_delete_view, name='customer_delete'),

    # Suppliers
    path('suppliers/', views.suppliers_list_view, name='suppliers'),
    path('suppliers/add/', views.supplier_create_view, name='supplier_create'),
    path('suppliers/<int:supplier_id>/edit/', views.supplier_edit_view, name='supplier_edit'),
    path('suppliers/<int:supplier_id>/delete/', views.supplier_delete_view, name='supplier_delete'),

    # Receivables / Payables / Closings
    path('receivables/', views.receivables_list_view, name='receivables'),
    path('payables/', views.payables_list_view, name='payables'),
    path('closing/', views.daily_closing_view, name='daily_closing'),
    path('reversal/<int:transaction_id>/', views.transaction_reversal_view, name='reversal'),
]
