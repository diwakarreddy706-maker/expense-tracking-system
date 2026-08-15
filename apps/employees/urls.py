from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    path('', views.employee_list_view, name='list'),
    path('wages/', views.employee_wages_view, name='wages'),
    path('<int:employee_id>/delete/', views.employee_delete_view, name='delete'),
]
