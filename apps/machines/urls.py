from django.urls import path
from . import views

app_name = 'machines'

urlpatterns = [
    path('', views.machine_list_view, name='list'),
    path('add/', views.machine_create_view, name='create'),
    path('<int:machine_id>/edit/', views.machine_edit_view, name='edit'),
    path('<int:machine_id>/delete/', views.machine_delete_view, name='delete'),
]
