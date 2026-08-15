from django.urls import path
from . import views

app_name = 'fuel'

urlpatterns = [
    path('', views.fuel_list_view, name='list'),
    path('add/', views.fuel_create_view, name='create'),
    path('<int:fuel_id>/', views.fuel_detail_view, name='detail'),
    path('<int:fuel_id>/reverse/', views.fuel_reverse_view, name='reverse'),
]
