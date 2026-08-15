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

    # Customer Receivables & Settlements
    path('receivables/', views.receivables_list_view, name='receivables'),
    path('receivables/add/', views.receivable_create_view, name='receivable_create'),
    path('receivables/<int:receivable_id>/', views.receivable_detail_view, name='receivable_detail'),
    path('receivables/<int:receivable_id>/pay/', views.customer_payment_create_view, name='customer_payment_create'),
    path('customer-payments/<int:payment_id>/reverse/', views.customer_payment_reverse_view, name='customer_payment_reverse'),

    # Supplier Payables & Settlements
    path('payables/', views.payables_list_view, name='payables'),
    path('payables/add/', views.payable_create_view, name='payable_create'),
    path('payables/<int:payable_id>/', views.payable_detail_view, name='payable_detail'),
    path('payables/<int:payable_id>/pay/', views.supplier_payment_create_view, name='supplier_payment_create'),
    path('supplier-payments/<int:payment_id>/reverse/', views.supplier_payment_reverse_view, name='supplier_payment_reverse'),

    # Closings & General Reversals
    path('closing/', views.daily_closing_view, name='daily_closing'),
    path('closing/submit/', views.daily_closing_submit_view, name='daily_closing_submit'),
    path('reversal/<int:transaction_id>/', views.transaction_reversal_view, name='reversal'),
]
