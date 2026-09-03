from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_index_view, name='index'),
    path('expenses/', views.expense_reports_view, name='expenses'),
    path('expenses/pdf/', views.expense_analysis_pdf_view, name='expense_pdf'),
    path('operational/', views.operational_reports_view, name='operational'),
    path('machinery-pnl/pdf/', views.machinery_pnl_pdf_view, name='machinery_pnl_pdf'),
    path('receivables-aging/pdf/', views.receivables_aging_pdf_view, name='receivables_aging_pdf'),
    path('financial/', views.financial_reports_view, name='financial'),
    path('export/', views.financial_export_view, name='export'),
]

