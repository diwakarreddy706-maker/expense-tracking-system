from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    # Expenses
    path('', views.expense_list_view, name='list'),
    path('add/', views.expense_create_view, name='create'),
    path('<int:expense_id>/', views.expense_detail_view, name='detail'),
    path('<int:expense_id>/reverse/', views.expense_reverse_view, name='reverse'),

    # Quick Expense API
    path('api/quick/', views.expense_quick_api_view, name='api_quick'),
    path('api/options/', views.expense_options_api_view, name='api_options'),

    # Categories
    path('categories/', views.category_list_view, name='categories'),
    path('categories/add/', views.category_create_view, name='category_create'),
    path('categories/<int:category_id>/edit/', views.category_edit_view, name='category_edit'),
    path('categories/<int:category_id>/toggle/', views.category_toggle_view, name='category_toggle'),
]
