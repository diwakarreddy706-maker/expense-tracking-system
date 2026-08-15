from django.urls import path
from . import views

app_name = 'fuel'

urlpatterns = [
    path('', views.fuel_list_view, name='list'),
]
