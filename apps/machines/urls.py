from django.urls import path
from . import views

app_name = 'machines'

urlpatterns = [
    # Machine Master
    path('', views.machine_list_view, name='list'),
    path('add/', views.machine_create_view, name='create'),
    path('<int:machine_id>/edit/', views.machine_edit_view, name='edit'),
    path('<int:machine_id>/delete/', views.machine_delete_view, name='delete'),

    # Phase 12.5: Bookings & Dispatch
    path('bookings/', views.booking_list_view, name='booking_list'),
    path('bookings/add/', views.booking_create_view, name='booking_create'),
    path('bookings/<int:booking_id>/', views.booking_detail_view, name='booking_detail'),
    path('bookings/<int:booking_id>/edit/', views.booking_edit_view, name='booking_edit'),
    path('bookings/<int:booking_id>/confirm/', views.booking_confirm_view, name='booking_confirm'),
    path('bookings/<int:booking_id>/dispatch/', views.booking_dispatch_view, name='booking_dispatch'),
    path('bookings/<int:booking_id>/start/', views.booking_start_work_view, name='booking_start_work'),
    path('bookings/<int:booking_id>/complete/', views.booking_complete_work_view, name='booking_complete_work'),
    path('bookings/<int:booking_id>/cancel/', views.booking_cancel_view, name='booking_cancel'),
    path('bookings/<int:booking_id>/delete/', views.booking_delete_view, name='booking_delete'),
    path('dispatch/', views.dispatch_board_view, name='dispatch_board'),

    # Phase 12.4: Work Entries & Commercial Calculation
    path('work/', views.work_entry_list_view, name='work_list'),
    path('work/add/', views.work_entry_create_view, name='work_create'),
    path('work/<int:entry_id>/edit/', views.work_entry_edit_view, name='work_edit'),
    path('work/<int:entry_id>/delete/', views.work_entry_delete_view, name='work_delete'),
]
