from django.urls import path
from . import views

app_name = 'machines'

urlpatterns = [
    path('', views.machine_list_view, name='list'),
]
