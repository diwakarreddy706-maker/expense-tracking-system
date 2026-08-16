from django.urls import path
from . import views

app_name = 'machines'

urlpatterns = [
    path('', views.machine_list_view, name='list'),
    path('add/', views.machine_create_view, name='create'),
    path('<int:machine_id>/edit/', views.machine_edit_view, name='edit'),
    path('<int:machine_id>/delete/', views.machine_delete_view, name='delete'),

    # Phase 12.4: Work Entries & Billing Logs
    path('work/', views.work_entry_list_view, name='work_list'),
    path('work/add/', views.work_entry_create_view, name='work_create'),
    path('work/<int:entry_id>/edit/', views.work_entry_edit_view, name='work_edit'),
    path('work/<int:entry_id>/delete/', views.work_entry_delete_view, name='work_delete'),
]
