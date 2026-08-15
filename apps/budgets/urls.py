from django.urls import path
from . import views

app_name = 'budgets'

urlpatterns = [
    path('', views.budget_list_view, name='list'),
    path('add/', views.budget_create_view, name='create'),
    path('<int:budget_id>/', views.budget_detail_view, name='detail'),
    path('<int:budget_id>/edit/', views.budget_edit_view, name='edit'),
    path('<int:budget_id>/items/add/', views.budget_item_add_view, name='item_add'),
    path('items/<int:item_id>/delete/', views.budget_item_delete_view, name='item_delete'),
    path('api/<int:budget_id>/', views.budget_vs_actual_api_view, name='api_vs_actual'),
]
