from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.expense_list_view, name='list'),
    path('categories/', views.category_list_view, name='categories'),
    path('categories/add/', views.category_create_view, name='category_create'),
    path('categories/<int:category_id>/edit/', views.category_edit_view, name='category_edit'),
    path('categories/<int:category_id>/toggle/', views.category_toggle_view, name='category_toggle'),
]
