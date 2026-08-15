from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('accounts/', views.accounts_list_view, name='accounts'),
    path('receivables/', views.receivables_list_view, name='receivables'),
    path('payables/', views.payables_list_view, name='payables'),
    path('daily-closing/', views.daily_closing_view, name='daily_closing'),
]
