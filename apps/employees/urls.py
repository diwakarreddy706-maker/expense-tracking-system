from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    path('', views.employee_list_view, name='list'),
    path('add/', views.employee_create_view, name='create'),
    path('<int:employee_id>/edit/', views.employee_edit_view, name='edit'),
    path('<int:employee_id>/delete/', views.employee_delete_view, name='delete'),
    path('wages/', views.employee_wages_view, name='wages'),
]
