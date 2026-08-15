from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_index_view, name='index'),
    path('operational/', views.operational_reports_view, name='operational'),
    path('financial/', views.financial_reports_view, name='financial'),
    path('export/', views.financial_export_view, name='export'),
]
