from django.urls import path
from . import views

app_name = 'machines'

urlpatterns = [
    # Machine Master
    path('', views.machine_list_view, name='list'),
    path('add/', views.machine_create_view, name='create'),
    path('types/add-ajax/', views.machine_type_create_ajax_view, name='type_create_ajax'),
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
    path('work/<int:entry_id>/invoice/', views.work_entry_invoice_view, name='work_invoice'),

    # Step 1 & 5: Rented Combine Harvester Owners & Settlements
    path('rented-owners/', views.rented_owners_list_view, name='rented_owners'),
    path('rented-owners/add/', views.rented_owner_create_view, name='rented_owner_create'),
    path('rented-owners/settlement/<int:settlement_id>/settle/', views.rented_settlement_settle_view, name='rented_settlement_settle'),

    # Step 2: Harvester & Transit Truck Compliance
    path('compliance/', views.harvester_compliance_list_view, name='compliance_list'),
    path('compliance/add/', views.harvester_compliance_create_view, name='compliance_create'),
    path('compliance/<int:compliance_id>/whatsapp/', views.harvester_compliance_whatsapp_view, name='compliance_whatsapp'),

    # Farmer Credit Ledger (Udhar Katha)
    path('farmers/ledger/', views.farmer_credit_ledger_view, name='farmer_ledger'),
    path('farmers/ledger/<int:customer_id>/', views.farmer_credit_ledger_view, name='farmer_ledger_detail'),
    path('farmers/ledger/<int:customer_id>/collect/', views.farmer_collect_payment_view, name='farmer_collect_payment'),
    path('farmers/add-ajax/', views.farmer_create_ajax_view, name='farmer_create_ajax'),

    # AJAX Form Lookups
    path('ajax/farmer/<int:customer_id>/', views.farmer_details_ajax_view, name='farmer_details_ajax'),
    path('ajax/machine/<int:machine_id>/', views.machine_details_ajax_view, name='machine_details_ajax'),

    # Phase 15: Machinery Maintenance & Service Management
    path('maintenance/', views.maintenance_dashboard_view, name='maintenance_dashboard'),
    path('maintenance/jobs/', views.maintenance_job_list_view, name='maintenance_job_list'),
    path('maintenance/jobs/add/', views.maintenance_job_create_view, name='maintenance_job_create'),
    path('maintenance/jobs/<int:job_id>/', views.maintenance_job_detail_view, name='maintenance_job_detail'),
    path('maintenance/jobs/<int:job_id>/edit/', views.maintenance_job_edit_view, name='maintenance_job_edit'),
    path('maintenance/jobs/<int:job_id>/start/', views.maintenance_job_start_view, name='maintenance_job_start'),
    path('maintenance/jobs/<int:job_id>/complete/', views.maintenance_job_complete_view, name='maintenance_job_complete'),
    path('maintenance/jobs/<int:job_id>/cancel/', views.maintenance_job_cancel_view, name='maintenance_job_cancel'),
    path('maintenance/jobs/<int:job_id>/delete/', views.maintenance_job_delete_view, name='maintenance_job_delete'),
    path('maintenance/jobs/<int:job_id>/parts/add/', views.maintenance_part_add_view, name='maintenance_part_add'),
    path('maintenance/jobs/<int:job_id>/parts/<int:part_id>/delete/', views.maintenance_part_delete_view, name='maintenance_part_delete'),
    path('maintenance/jobs/<int:job_id>/post-expense/', views.maintenance_job_post_expense_view, name='maintenance_job_post_expense'),
    path('maintenance/schedules/', views.maintenance_schedule_list_view, name='maintenance_schedule_list'),
    path('maintenance/schedules/add/', views.maintenance_schedule_create_view, name='maintenance_schedule_create'),
    path('maintenance/schedules/<int:schedule_id>/edit/', views.maintenance_schedule_edit_view, name='maintenance_schedule_edit'),
    path('maintenance/history/<int:machine_id>/', views.machine_service_history_view, name='machine_service_history'),
]
