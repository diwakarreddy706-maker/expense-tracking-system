from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import re
from django.http import JsonResponse
from apps.accounts.decorators import role_required, owner_required
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog
from .models import (
    Machine, MachineType, MachineBooking, MachineWorkEntry,
    MachineMaintenanceSchedule, MaintenanceJob, MaintenancePartUsage,
    RentedHarvesterOwner, HarvesterCompliance, RentedHarvesterSettlement
)
from .forms import (
    MachineForm, MachineTypeForm, MachineBookingForm,
    BookingConfirmForm, BookingDispatchForm, BookingCancelForm,
    MachineWorkEntryForm, MachineMaintenanceScheduleForm,
    MaintenanceJobForm, MaintenancePartUsageForm,
    MaintenanceCompleteForm, MaintenanceExpensePostForm,
    RentedHarvesterOwnerForm, HarvesterComplianceForm
)
from .services.work_service import WorkService
from .services.booking_service import BookingService
from .services.maintenance_service import MaintenanceService
from apps.finance.models import Customer, Supplier, Account
from apps.expenses.models import Expense, ExpenseCategory
from apps.employees.models import Employee


DEFAULT_MACHINE_TYPES = [
    ('Tractor', 'TRACTOR'),
    ('Combine Harvester', 'COMBINE_HARVESTER'),
    ('Power Tiller', 'POWER_TILLER'),
    ('Earth Mover / JCB', 'EARTH_MOVER'),
    ('Rotavator / Cultivator', 'ROTAVATOR'),
    ('Sprayer / Drone', 'SPRAYER'),
    ('Thresher / Sheller', 'THRESHER'),
    ('Laser Land Leveler', 'LASER_LEVELER'),
    ('Baler', 'BALER'),
    ('Support Vehicle / Trailer', 'TRAILER'),
    ('Other Equipment', 'OTHER'),
]


def ensure_default_machine_types():
    """Seeds standard equipment types if table is empty."""
    if not MachineType.objects.exists():
        for name, code in DEFAULT_MACHINE_TYPES:
            MachineType.objects.get_or_create(code=code, defaults={'name': name})


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def machine_list_view(request):
    """Lists agricultural machinery with search and status filtering."""
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    m_type = request.GET.get('type', '').strip()

    machines = Machine.objects.filter(is_deleted=False).select_related('machine_type', 'default_operator')
    if query:
        machines = machines.filter(Q(name__icontains=query) | Q(machine_code__icontains=query) | Q(registration_no__icontains=query))
    if status:
        machines = machines.filter(status=status)
    if m_type:
        machines = machines.filter(machine_type__code=m_type)

    return render(request, 'machines/machine_list.html', {
        'machines': machines,
        'machine_types': MachineType.objects.all(),
        'query': query,
        'status': status,
        'm_type': m_type,
        'title': 'Machines & Heavy Equipment',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def machine_create_view(request):
    """Creates a new machine record."""
    ensure_default_machine_types()
    if request.method == 'POST':
        post_data = request.POST.copy()
        if not post_data.get('machine_code'):
            import uuid
            post_data['machine_code'] = f"MCH-{uuid.uuid4().hex[:6].upper()}"
        if not post_data.get('status'):
            post_data['status'] = Machine.STATUS_ACTIVE
        if not post_data.get('meter_unit'):
            post_data['meter_unit'] = Machine.METER_HOURS
        if not post_data.get('current_meter_reading'):
            post_data['current_meter_reading'] = '0.00'
        form = MachineForm(post_data)
        if form.is_valid():
            machine = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_CREATE,
                'Machine',
                machine.id,
                changes={'machine_code': machine.machine_code, 'name': machine.name, 'meter_unit': machine.meter_unit},
                request=request
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax'):
                return JsonResponse({
                    'success': True,
                    'id': machine.id,
                    'name': f"{machine.name} ({machine.machine_code})",
                    'code': machine.machine_code
                })
            messages.success(request, f"Machine '{machine.name}' ({machine.machine_code}) added.")
            return redirect('machines:list')
        elif request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax'):
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()})
    else:
        form = MachineForm()

    return render(request, 'machines/machine_form.html', {
        'form': form,
        'title': 'Add New Machine / Equipment',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def machine_edit_view(request, machine_id):
    """Edits an existing machine."""
    ensure_default_machine_types()
    machine = get_object_or_404(Machine, id=machine_id, is_deleted=False)
    if request.method == 'POST':
        form = MachineForm(request.POST, instance=machine)
        if form.is_valid():
            updated = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_UPDATE,
                'Machine',
                updated.id,
                changes={'name': updated.name, 'status': updated.status, 'current_meter_reading': str(updated.current_meter_reading)},
                request=request
            )
            messages.success(request, f"Machine '{updated.name}' updated.")
            return redirect('machines:list')
    else:
        form = MachineForm(instance=machine)

    return render(request, 'machines/machine_form.html', {
        'form': form,
        'machine': machine,
        'title': f"Edit Machine: {machine.name}",
    })


@owner_required
def machine_delete_view(request, machine_id):
    """Soft deletes a machine record (Owner only)."""
    machine = get_object_or_404(Machine, id=machine_id, is_deleted=False)
    machine.is_deleted = True
    machine.save()
    log_audit_event(
        request.user,
        AuditLog.ACTION_SOFT_DELETE,
        'Machine',
        machine.id,
        request=request
    )
    messages.warning(request, f"Machine '{machine.name}' deleted.")
    return redirect('machines:list')


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def machine_type_create_ajax_view(request):
    """Creates a new MachineType via AJAX."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        if not name:
            return JsonResponse({'success': False, 'error': 'Equipment type name is required.'}, status=400)
        if not code:
            code = re.sub(r'[^a-zA-Z0-9]+', '_', name).strip('_').upper()[:30]

        mtype, created = MachineType.objects.get_or_create(
            name__iexact=name,
            defaults={'name': name, 'code': code}
        )
        return JsonResponse({
            'success': True,
            'id': mtype.id,
            'name': str(mtype),
            'created': created
        })
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


# ==============================================================================
# PHASE 12.5: MACHINE BOOKING & DISPATCH WORKFLOW
# ==============================================================================

@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def booking_list_view(request):
    """Lists machine bookings with status and date filtering and operational KPI summaries."""
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    m_type = request.GET.get('machine_type', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    bookings = MachineBooking.objects.filter(is_deleted=False).select_related(
        'customer', 'machine_type', 'machine', 'operator', 'created_by'
    ).order_by('-work_date', '-id')

    if query:
        bookings = bookings.filter(
            Q(booking_code__icontains=query) |
            Q(customer__name__icontains=query) |
            Q(machine__name__icontains=query) |
            Q(village__icontains=query)
        )
    if status:
        bookings = bookings.filter(status=status)
    if m_type:
        bookings = bookings.filter(machine_type_id=m_type)
    if start_date:
        bookings = bookings.filter(work_date__gte=start_date)
    if end_date:
        bookings = bookings.filter(work_date__lte=end_date)

    # Operational KPIs
    all_active = MachineBooking.objects.filter(is_deleted=False)
    kpis = {
        'total': all_active.count(),
        'pending': all_active.filter(status=MachineBooking.STATUS_PENDING).count(),
        'confirmed': all_active.filter(status=MachineBooking.STATUS_CONFIRMED).count(),
        'dispatched': all_active.filter(status=MachineBooking.STATUS_DISPATCHED).count(),
        'in_progress': all_active.filter(status=MachineBooking.STATUS_IN_PROGRESS).count(),
        'completed': all_active.filter(status=MachineBooking.STATUS_COMPLETED).count(),
    }

    return render(request, 'machines/booking_list.html', {
        'bookings': bookings,
        'machine_types': MachineType.objects.all(),
        'kpis': kpis,
        'query': query,
        'status': status,
        'selected_m_type': m_type,
        'start_date': start_date,
        'end_date': end_date,
        'title': 'Machine Bookings & Schedule',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def booking_create_view(request):
    """Creates a new customer machine booking."""
    ensure_default_machine_types()
    if request.method == 'POST':
        form = MachineBookingForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                booking = BookingService.create_booking(
                    customer=cd['customer'],
                    machine_type=cd['machine_type'],
                    work_date=cd['work_date'],
                    billing_type=cd['billing_type'],
                    created_by=request.user,
                    machine=cd.get('machine'),
                    operator=cd.get('operator'),
                    requested_start_time=cd.get('requested_start_time'),
                    expected_quantity=cd.get('expected_quantity', Decimal('0.00')),
                    expected_duration_hours=cd.get('expected_duration_hours', Decimal('0.00')),
                    work_location=cd.get('work_location'),
                    village=cd.get('village'),
                    crop_description=cd.get('crop_description'),
                    notes=cd.get('notes'),
                    request=request
                )
                messages.success(request, f"Booking '{booking.booking_code}' created for {booking.customer.name}.")
                return redirect('machines:booking_detail', booking_id=booking.id)
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
    else:
        form = MachineBookingForm()

    return render(request, 'machines/booking_form.html', {
        'form': form,
        'title': 'Create Machine Booking',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def booking_detail_view(request, booking_id):
    """Details and operational lifecycle view for a booking."""
    booking = get_object_or_404(
        MachineBooking.objects.select_related('customer', 'machine_type', 'machine', 'operator', 'created_by'),
        id=booking_id,
        is_deleted=False
    )
    work_entries = booking.work_entries.filter(is_deleted=False)

    return render(request, 'machines/booking_detail.html', {
        'booking': booking,
        'work_entries': work_entries,
        'title': f"Booking: {booking.booking_code}",
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def booking_edit_view(request, booking_id):
    """Edits an existing booking."""
    booking = get_object_or_404(MachineBooking, id=booking_id, is_deleted=False)
    if booking.status in [MachineBooking.STATUS_COMPLETED, MachineBooking.STATUS_CANCELLED]:
        messages.error(request, f"Cannot edit booking in '{booking.get_status_display()}' status.")
        return redirect('machines:booking_detail', booking_id=booking.id)

    if request.method == 'POST':
        form = MachineBookingForm(request.POST, instance=booking)
        if form.is_valid():
            try:
                BookingService.update_booking(booking, request.user, form.cleaned_data, request=request)
                messages.success(request, f"Booking '{booking.booking_code}' updated.")
                return redirect('machines:booking_detail', booking_id=booking.id)
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
    else:
        form = MachineBookingForm(instance=booking)

    return render(request, 'machines/booking_form.html', {
        'form': form,
        'booking': booking,
        'title': f"Edit Booking: {booking.booking_code}",
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def booking_confirm_view(request, booking_id):
    """Confirms booking and assigns machine and operator."""
    booking = get_object_or_404(MachineBooking, id=booking_id, is_deleted=False)
    if request.method == 'POST':
        machine_id = request.POST.get('machine')
        operator_id = request.POST.get('operator')

        machine = get_object_or_404(Machine, id=machine_id, is_deleted=False) if machine_id else booking.machine
        operator = get_object_or_404(Employee, id=operator_id, is_deleted=False) if operator_id else booking.operator

        try:
            BookingService.confirm_booking(booking, request.user, machine=machine, operator=operator, request=request)
            messages.success(request, f"Booking '{booking.booking_code}' confirmed with Machine {booking.machine.name} and Operator {booking.operator.full_name}.")
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
        return redirect('machines:booking_detail', booking_id=booking.id)

    # GET fallback: show available machines and operators
    available_machines = BookingService.get_available_machines(booking.machine_type, booking.work_date, exclude_booking_id=booking.id)
    available_operators = Employee.objects.filter(is_deleted=False, status=Employee.STATUS_ACTIVE)
    return render(request, 'machines/booking_confirm_modal.html', {
        'booking': booking,
        'available_machines': available_machines,
        'available_operators': available_operators,
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def booking_dispatch_view(request, booking_id):
    """Dispatches confirmed machine to field."""
    booking = get_object_or_404(MachineBooking, id=booking_id, is_deleted=False)
    if request.method == 'POST':
        dispatch_notes = request.POST.get('dispatch_notes', '').strip()
        try:
            BookingService.dispatch_booking(booking, request.user, dispatch_notes=dispatch_notes, request=request)
            messages.success(request, f"Booking '{booking.booking_code}' dispatched to {booking.customer.name}'s field.")
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
    return redirect('machines:booking_detail', booking_id=booking.id)


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def booking_start_work_view(request, booking_id):
    """Marks work as started (IN_PROGRESS)."""
    booking = get_object_or_404(MachineBooking, id=booking_id, is_deleted=False)
    if request.method == 'POST':
        try:
            BookingService.start_work(booking, request.user, request=request)
            messages.success(request, f"Work started for booking '{booking.booking_code}'.")
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
    return redirect('machines:booking_detail', booking_id=booking.id)


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def booking_complete_work_view(request, booking_id):
    """Marks work as completed (COMPLETED)."""
    booking = get_object_or_404(MachineBooking, id=booking_id, is_deleted=False)
    if request.method == 'POST':
        try:
            BookingService.complete_work(booking, request.user, request=request)
            messages.success(request, f"Work completed for booking '{booking.booking_code}'. Ready to record work & billing log.")
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
    return redirect('machines:booking_detail', booking_id=booking.id)


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def booking_cancel_view(request, booking_id):
    """Cancels a booking."""
    booking = get_object_or_404(MachineBooking, id=booking_id, is_deleted=False)
    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason', '').strip()
        try:
            BookingService.cancel_booking(booking, request.user, cancellation_reason=reason, request=request)
            messages.warning(request, f"Booking '{booking.booking_code}' has been cancelled.")
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
    return redirect('machines:booking_detail', booking_id=booking.id)


@owner_required
def booking_delete_view(request, booking_id):
    """Soft deletes a booking (Owner only)."""
    booking = get_object_or_404(MachineBooking, id=booking_id, is_deleted=False)
    BookingService.soft_delete_booking(booking, request.user, request=request)
    messages.warning(request, f"Booking '{booking.booking_code}' deleted.")
    return redirect('machines:booking_list')


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def dispatch_board_view(request):
    """
    Operational Dispatch Board displaying columns for:
    PENDING, CONFIRMED, DISPATCHED, IN_PROGRESS, COMPLETED.
    """
    all_bookings = MachineBooking.objects.filter(is_deleted=False).select_related(
        'customer', 'machine_type', 'machine', 'operator'
    ).order_by('-work_date', '-id')

    pending_list = all_bookings.filter(status=MachineBooking.STATUS_PENDING)
    confirmed_list = all_bookings.filter(status=MachineBooking.STATUS_CONFIRMED)
    dispatched_list = all_bookings.filter(status=MachineBooking.STATUS_DISPATCHED)
    in_progress_list = all_bookings.filter(status=MachineBooking.STATUS_IN_PROGRESS)
    completed_list = all_bookings.filter(status=MachineBooking.STATUS_COMPLETED)[:20]

    return render(request, 'machines/dispatch_board.html', {
        'pending_list': pending_list,
        'confirmed_list': confirmed_list,
        'dispatched_list': dispatched_list,
        'in_progress_list': in_progress_list,
        'completed_list': completed_list,
        'title': 'Machinery Operational Dispatch Board',
    })


# ==============================================================================
# PHASE 12.4: MACHINE WORK ENTRY & BILLING VIEWS
# ==============================================================================

@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def work_entry_list_view(request):
    """Lists machine field work logs and billing calculations."""
    query = request.GET.get('q', '').strip()
    machine_id = request.GET.get('machine', '').strip()
    customer_id = request.GET.get('customer', '').strip()
    b_type = request.GET.get('billing_type', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    entries = MachineWorkEntry.objects.filter(is_deleted=False).select_related(
        'machine', 'machine__machine_type', 'customer', 'operator', 'created_by', 'booking'
    ).order_by('-work_date', '-id')

    if query:
        entries = entries.filter(
            Q(work_code__icontains=query) |
            Q(machine__name__icontains=query) |
            Q(machine__machine_code__icontains=query) |
            Q(customer__name__icontains=query)
        )
    if machine_id:
        entries = entries.filter(machine_id=machine_id)
    if customer_id:
        entries = entries.filter(customer_id=customer_id)
    if b_type:
        entries = entries.filter(billing_type=b_type)
    if start_date:
        entries = entries.filter(work_date__gte=start_date)
    if end_date:
        entries = entries.filter(work_date__lte=end_date)

    total_billed = entries.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    total_harvester_hours = entries.filter(billing_type=MachineWorkEntry.BILLING_TIME_HOURLY).aggregate(s=Sum('net_working_hours'))['s'] or Decimal('0.00')
    total_tractor_acres = entries.filter(billing_type=MachineWorkEntry.BILLING_ACRE).aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')

    return render(request, 'machines/work_entry_list.html', {
        'entries': entries,
        'machines': Machine.objects.filter(is_deleted=False),
        'customers': Customer.objects.filter(is_deleted=False),
        'total_billed': total_billed,
        'total_harvester_hours': total_harvester_hours,
        'total_tractor_acres': total_tractor_acres,
        'query': query,
        'selected_machine': machine_id,
        'selected_customer': customer_id,
        'selected_billing_type': b_type,
        'start_date': start_date,
        'end_date': end_date,
        'title': 'Machine Work Entries & Billing Logs',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def work_entry_create_view(request):
    """Records a new machine work and commercial calculation entry with optional booking integration."""
    booking_id = request.GET.get('booking_id')
    linked_booking = None
    initial_data = {}

    if booking_id:
        linked_booking = get_object_or_404(MachineBooking, id=booking_id, is_deleted=False)
        initial_data = {
            'booking': linked_booking,
            'customer': linked_booking.customer,
            'machine': linked_booking.machine,
            'operator': linked_booking.operator,
            'work_date': linked_booking.work_date,
            'billing_type': linked_booking.billing_type,
            'notes': f"Recorded from Booking {linked_booking.booking_code}. {linked_booking.notes or ''}".strip(),
        }
        if linked_booking.billing_type == MachineWorkEntry.BILLING_TIME_HOURLY:
            initial_data['start_time'] = linked_booking.requested_start_time
        elif linked_booking.billing_type in [MachineWorkEntry.BILLING_ACRE, MachineWorkEntry.BILLING_PIECE]:
            initial_data['quantity'] = linked_booking.expected_quantity

        if linked_booking.machine:
            initial_data['start_meter'] = linked_booking.machine.current_meter_reading

    if request.method == 'POST':
        form = MachineWorkEntryForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            entry = WorkService.create_work_entry(
                work_date=cd['work_date'],
                machine=cd['machine'],
                customer=cd['customer'],
                operator=cd.get('operator'),
                booking=cd.get('booking') or linked_booking,
                billing_type=cd['billing_type'],
                start_time=cd.get('start_time'),
                end_time=cd.get('end_time'),
                break_hours=cd.get('break_hours') or Decimal('0.00'),
                hourly_rate=cd.get('hourly_rate') or Decimal('0.00'),
                quantity=cd.get('quantity') or Decimal('0.00'),
                unit_rate=cd.get('unit_rate') or Decimal('0.00'),
                start_meter=cd.get('start_meter'),
                end_meter=cd.get('end_meter'),
                manual_bill_no=cd.get('manual_bill_no'),
                advance_amount=cd.get('advance_amount') or Decimal('0.00'),
                udhar_amount=cd.get('udhar_amount') or Decimal('0.00'),
                payment_mode=cd.get('payment_mode') or 'UDHAR',
                payment_account=cd.get('payment_account'),
                fuel_liters=cd.get('fuel_liters') or Decimal('0.00'),
                fuel_rate=cd.get('fuel_rate') or Decimal('95.00'),
                notes=cd.get('notes'),
                auto_create_receivable=True,
                created_by=request.user,
                request=request
            )
            adv_info = f" (Advance Paid: ₹{entry.advance_amount:,.2f}, Balance Udhar: ₹{entry.udhar_amount:,.2f})" if entry.advance_amount or entry.udhar_amount else ""
            messages.success(request, f"Harvesting Bill '{entry.work_code}' recorded. Total: ₹{entry.total_amount:,.2f}{adv_info}")
            if entry.booking:
                return redirect('machines:booking_detail', booking_id=entry.booking.id)
            return redirect('machines:work_invoice', entry_id=entry.id)
    else:
        form = MachineWorkEntryForm(initial=initial_data)

    return render(request, 'machines/work_entry_form.html', {
        'form': form,
        'linked_booking': linked_booking,
        'machine_types': MachineType.objects.all(),
        'title': f"Record Work Entry {'(Booking: ' + linked_booking.booking_code + ')' if linked_booking else ''}",
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def work_entry_edit_view(request, entry_id):
    """Edits and recalculates an existing machine work entry."""
    entry = get_object_or_404(MachineWorkEntry, id=entry_id, is_deleted=False)
    if request.method == 'POST':
        form = MachineWorkEntryForm(request.POST, instance=entry)
        if form.is_valid():
            cd = form.cleaned_data
            updated = WorkService.update_work_entry(
                entry=entry,
                work_date=cd['work_date'],
                machine=cd['machine'],
                customer=cd['customer'],
                operator=cd.get('operator'),
                booking=cd.get('booking') or entry.booking,
                billing_type=cd['billing_type'],
                start_time=cd.get('start_time'),
                end_time=cd.get('end_time'),
                break_hours=cd.get('break_hours', Decimal('0.00')),
                hourly_rate=cd.get('hourly_rate', Decimal('0.00')),
                quantity=cd.get('quantity', Decimal('0.00')),
                unit_rate=cd.get('unit_rate', Decimal('0.00')),
                start_meter=cd.get('start_meter'),
                end_meter=cd.get('end_meter'),
                notes=cd.get('notes'),
                user=request.user,
                request=request
            )
            messages.success(request, f"Work Entry '{updated.work_code}' updated. Recalculated Total: ₹{updated.total_amount:,.2f}")
            return redirect('machines:work_list')
    else:
        form = MachineWorkEntryForm(instance=entry)

    return render(request, 'machines/work_entry_form.html', {
        'form': form,
        'entry': entry,
        'machine_types': MachineType.objects.all(),
        'title': f"Edit Work Entry: {entry.work_code}",
    })


@owner_required
def work_entry_delete_view(request, entry_id):
    """Soft deletes a machine work entry (Owner only)."""
    entry = get_object_or_404(MachineWorkEntry, id=entry_id, is_deleted=False)
    WorkService.soft_delete_work_entry(entry, request.user, request=request)
    messages.warning(request, f"Work Entry '{entry.work_code}' deleted.")
    return redirect('machines:work_list')


# ==============================================================================
# PHASE 15: MACHINERY MAINTENANCE & SERVICE MANAGEMENT VIEWS
# ==============================================================================

@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_dashboard_view(request):
    """
    Machinery Maintenance & Service Operations Dashboard (Phase 15).
    Provides KPI summary cards, active workshop repairs, due schedules, and recent completed jobs.
    """
    # 1. KPI Cards
    under_maintenance_count = Machine.objects.filter(is_deleted=False, status=Machine.STATUS_UNDER_MAINTENANCE).count()
    open_jobs_count = MaintenanceJob.objects.filter(is_deleted=False).exclude(status__in=[MaintenanceJob.STATUS_COMPLETED, MaintenanceJob.STATUS_CANCELLED]).count()
    breakdowns_count = MaintenanceJob.objects.filter(is_deleted=False, maintenance_type=MaintenanceJob.TYPE_BREAKDOWN_REPAIR).count()

    today = timezone.now().date()
    month_start = today.replace(day=1)
    cost_this_month = MaintenanceJob.objects.filter(
        is_deleted=False,
        status=MaintenanceJob.STATUS_COMPLETED,
        completed_date__gte=month_start
    ).aggregate(total=Sum('total_maintenance_cost'))['total'] or Decimal('0.00')

    # Evaluate schedules for Due Soon & Overdue
    all_schedules = MachineMaintenanceSchedule.objects.filter(is_active=True, machine__is_deleted=False).select_related('machine')
    schedules_due_soon = []
    schedules_overdue = []

    for sch in all_schedules:
        status_info = sch.evaluate_status()
        sch.eval_status = status_info
        if status_info['status'] == MachineMaintenanceSchedule.STATUS_DUE_SOON:
            schedules_due_soon.append(sch)
        elif status_info['status'] in [MachineMaintenanceSchedule.STATUS_DUE, MachineMaintenanceSchedule.STATUS_OVERDUE]:
            schedules_overdue.append(sch)

    # Active Workshop Repairs
    active_repairs = MaintenanceJob.objects.filter(
        is_deleted=False
    ).exclude(
        status__in=[MaintenanceJob.STATUS_COMPLETED, MaintenanceJob.STATUS_CANCELLED]
    ).select_related('machine', 'supplier').order_by('-reported_date')[:10]

    # Recent Completed Maintenance
    recent_completed = MaintenanceJob.objects.filter(
        is_deleted=False,
        status=MaintenanceJob.STATUS_COMPLETED
    ).select_related('machine', 'supplier', 'linked_expense').order_by('-completed_date')[:10]

    return render(request, 'machines/maintenance_dashboard.html', {
        'under_maintenance_count': under_maintenance_count,
        'open_jobs_count': open_jobs_count,
        'breakdowns_count': breakdowns_count,
        'cost_this_month': cost_this_month,
        'due_soon_count': len(schedules_due_soon),
        'overdue_count': len(schedules_overdue),
        'schedules_due_soon': schedules_due_soon,
        'schedules_overdue': schedules_overdue,
        'active_repairs': active_repairs,
        'recent_completed': recent_completed,
        'title': 'Machinery Maintenance Dashboard',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_job_list_view(request):
    """
    List & Multi-filter Registry for all Maintenance and Breakdown Jobs.
    """
    machine_id = request.GET.get('machine', '').strip()
    m_type = request.GET.get('type', '').strip()
    status = request.GET.get('status', '').strip()
    supplier_id = request.GET.get('supplier', '').strip()
    query = request.GET.get('q', '').strip()

    jobs = MaintenanceJob.objects.filter(is_deleted=False).select_related('machine', 'supplier', 'linked_expense', 'created_by')

    if machine_id:
        jobs = jobs.filter(machine_id=machine_id)
    if m_type:
        jobs = jobs.filter(maintenance_type=m_type)
    if status:
        jobs = jobs.filter(status=status)
    if supplier_id:
        jobs = jobs.filter(supplier_id=supplier_id)
    if query:
        jobs = jobs.filter(
            Q(maintenance_code__icontains=query) |
            Q(problem_description__icontains=query) |
            Q(work_performed__icontains=query) |
            Q(breakdown_location__icontains=query) |
            Q(machine__name__icontains=query) |
            Q(machine__machine_code__icontains=query)
        )

    # Total cost of filtered jobs
    total_filtered_cost = jobs.aggregate(total=Sum('total_maintenance_cost'))['total'] or Decimal('0.00')

    return render(request, 'machines/maintenance_job_list.html', {
        'jobs': jobs,
        'machines': Machine.objects.filter(is_deleted=False),
        'suppliers': Supplier.objects.filter(is_deleted=False),
        'type_choices': MaintenanceJob.MAINTENANCE_TYPE_CHOICES,
        'status_choices': MaintenanceJob.STATUS_CHOICES,
        'selected_machine': machine_id,
        'selected_type': m_type,
        'selected_status': status,
        'selected_supplier': supplier_id,
        'query': query,
        'total_filtered_cost': total_filtered_cost,
        'title': 'Maintenance & Breakdown Jobs',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_job_create_view(request):
    """Creates a new Maintenance or Breakdown Job."""
    initial = {}
    if request.GET.get('machine_id'):
        initial['machine'] = request.GET.get('machine_id')
    if request.GET.get('schedule_id'):
        initial['maintenance_schedule'] = request.GET.get('schedule_id')
        initial['maintenance_type'] = MaintenanceJob.TYPE_PREVENTIVE_SERVICE
    if request.GET.get('type'):
        initial['maintenance_type'] = request.GET.get('type')

    if request.method == 'POST':
        form = MaintenanceJobForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                job = MaintenanceService.create_maintenance_job(
                    machine=cd['machine'],
                    maintenance_type=cd['maintenance_type'],
                    problem_description=cd['problem_description'],
                    reported_date=cd.get('reported_date'),
                    maintenance_schedule=cd.get('maintenance_schedule'),
                    meter_reading=cd.get('meter_reading'),
                    breakdown_location=cd.get('breakdown_location'),
                    breakdown_time=cd.get('breakdown_time'),
                    machine_stopped=cd.get('machine_stopped', False),
                    severity=cd.get('severity', MaintenanceJob.SEVERITY_MEDIUM),
                    supplier=cd.get('supplier'),
                    external_workshop_name=cd.get('external_workshop_name'),
                    labor_cost=cd.get('labor_cost', Decimal('0.00')),
                    external_service_cost=cd.get('external_service_cost', Decimal('0.00')),
                    other_cost=cd.get('other_cost', Decimal('0.00')),
                    diagnosis=cd.get('diagnosis'),
                    notes=cd.get('notes'),
                    created_by=request.user,
                    request=request
                )
                messages.success(request, f"Maintenance Job '{job.maintenance_code}' reported successfully.")
                return redirect('machines:maintenance_job_detail', job_id=job.id)
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
    else:
        form = MaintenanceJobForm(initial=initial)

    return render(request, 'machines/maintenance_job_form.html', {
        'form': form,
        'title': 'Report Maintenance / Breakdown Job',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_job_detail_view(request, job_id):
    """
    Detailed interactive page for MaintenanceJob.
    Shows problem, diagnosis, parts usage table, cost summary, and action modals.
    """
    job = get_object_or_404(
        MaintenanceJob.objects.select_related('machine', 'maintenance_schedule', 'supplier', 'linked_expense', 'created_by'),
        id=job_id,
        is_deleted=False
    )
    part_usages = job.part_usages.select_related('supplier').all()
    part_form = MaintenancePartUsageForm()
    complete_form = MaintenanceCompleteForm(initial={
        'completed_date': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        'meter_reading': job.meter_reading or job.machine.current_meter_reading,
        'labor_cost': job.labor_cost,
        'external_service_cost': job.external_service_cost,
        'other_cost': job.other_cost,
        'work_performed': job.work_performed or '',
    })
    expense_post_form = MaintenanceExpensePostForm(initial={
        'payment_method': Expense.METHOD_CASH
    })

    audit_logs = AuditLog.objects.filter(entity_type='MaintenanceJob', entity_id=str(job.id)).order_by('-timestamp')[:10]

    return render(request, 'machines/maintenance_job_detail.html', {
        'job': job,
        'part_usages': part_usages,
        'part_form': part_form,
        'complete_form': complete_form,
        'expense_post_form': expense_post_form,
        'audit_logs': audit_logs,
        'title': f"Maintenance Job: {job.maintenance_code}",
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_job_edit_view(request, job_id):
    """Edits an existing maintenance job."""
    job = get_object_or_404(MaintenanceJob, id=job_id, is_deleted=False)
    if job.status == MaintenanceJob.STATUS_COMPLETED:
        messages.warning(request, "Completed maintenance jobs cannot be modified.")
        return redirect('machines:maintenance_job_detail', job_id=job.id)

    if request.method == 'POST':
        form = MaintenanceJobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            MaintenanceService.recalculate_job_costs(job)
            log_audit_event(
                request.user,
                AuditLog.ACTION_UPDATE,
                'MaintenanceJob',
                job.id,
                changes={'maintenance_code': job.maintenance_code},
                request=request
            )
            messages.success(request, f"Maintenance Job '{job.maintenance_code}' updated.")
            return redirect('machines:maintenance_job_detail', job_id=job.id)
    else:
        form = MaintenanceJobForm(instance=job)

    return render(request, 'machines/maintenance_job_form.html', {
        'form': form,
        'job': job,
        'title': f"Edit Maintenance Job: {job.maintenance_code}",
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_job_start_view(request, job_id):
    """Transitions a job to IN_REPAIR and marks machine UNDER_MAINTENANCE."""
    if request.method == 'POST':
        job = get_object_or_404(MaintenanceJob, id=job_id, is_deleted=False)
        diagnosis = request.POST.get('diagnosis', '').strip()
        try:
            MaintenanceService.start_maintenance_job(job, request.user, diagnosis=diagnosis, request=request)
            messages.success(request, f"Maintenance '{job.maintenance_code}' is now IN REPAIR. Machine set to UNDER MAINTENANCE.")
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
    return redirect('machines:maintenance_job_detail', job_id=job_id)


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_job_complete_view(request, job_id):
    """Completes maintenance and safely returns machine to ACTIVE."""
    if request.method == 'POST':
        job = get_object_or_404(MaintenanceJob, id=job_id, is_deleted=False)
        form = MaintenanceCompleteForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                completed = MaintenanceService.complete_maintenance_job(
                    job=job,
                    user=request.user,
                    completed_date=cd['completed_date'],
                    meter_reading=cd.get('meter_reading'),
                    work_performed=cd['work_performed'],
                    labor_cost=cd.get('labor_cost'),
                    external_service_cost=cd.get('external_service_cost'),
                    other_cost=cd.get('other_cost'),
                    request=request
                )
                messages.success(request, f"Maintenance Job '{completed.maintenance_code}' COMPLETED. Total Cost: ₹{completed.total_maintenance_cost:,.2f}")
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
        else:
            for field, errs in form.errors.items():
                messages.error(request, f"{field}: {errs[0]}")
    return redirect('machines:maintenance_job_detail', job_id=job_id)


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_job_cancel_view(request, job_id):
    """Cancels a maintenance job."""
    if request.method == 'POST':
        job = get_object_or_404(MaintenanceJob, id=job_id, is_deleted=False)
        reason = request.POST.get('cancellation_reason', '').strip()
        try:
            MaintenanceService.cancel_maintenance_job(job, request.user, cancellation_reason=reason, request=request)
            messages.warning(request, f"Maintenance Job '{job.maintenance_code}' was CANCELLED.")
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
    return redirect('machines:maintenance_job_detail', job_id=job_id)


@owner_required
def maintenance_job_delete_view(request, job_id):
    """Soft deletes a maintenance job (Owner only)."""
    if request.method == 'POST':
        job = get_object_or_404(MaintenanceJob, id=job_id, is_deleted=False)
        MaintenanceService.soft_delete_maintenance_job(job, request.user, request=request)
        messages.warning(request, f"Maintenance Job '{job.maintenance_code}' deleted.")
        return redirect('machines:maintenance_job_list')
    return redirect('machines:maintenance_job_detail', job_id=job_id)


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_part_add_view(request, job_id):
    """Adds a spare part item to an editable maintenance job."""
    job = get_object_or_404(MaintenanceJob, id=job_id, is_deleted=False)
    if request.method == 'POST':
        form = MaintenancePartUsageForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                part = MaintenanceService.add_part_usage(
                    job=job,
                    part_name=cd['part_name'],
                    quantity=cd['quantity'],
                    unit_cost=cd['unit_cost'],
                    part_number=cd.get('part_number'),
                    supplier=cd.get('supplier'),
                    notes=cd.get('notes'),
                    user=request.user,
                    request=request
                )
                messages.success(request, f"Spare Part '{part.part_name}' added (₹{part.total_cost:,.2f}). Total Parts: ₹{job.parts_cost:,.2f}")
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
        else:
            for field, errs in form.errors.items():
                messages.error(request, f"{field}: {errs[0]}")
    return redirect('machines:maintenance_job_detail', job_id=job_id)


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_part_delete_view(request, job_id, part_id):
    """Deletes a spare part item from a maintenance job."""
    if request.method == 'POST':
        part = get_object_or_404(MaintenancePartUsage, id=part_id, maintenance_job_id=job_id)
        try:
            MaintenanceService.delete_part_usage(part, user=request.user, request=request)
            messages.warning(request, f"Part '{part.part_name}' removed.")
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
    return redirect('machines:maintenance_job_detail', job_id=job_id)


@role_required(['OWNER', 'ACCOUNTANT'])
def maintenance_job_post_expense_view(request, job_id):
    """
    Explicit action by Owner / Accountant to post a completed MaintenanceJob to Expenses.
    """
    if request.method == 'POST':
        job = get_object_or_404(MaintenanceJob, id=job_id, is_deleted=False)
        form = MaintenanceExpensePostForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                expense = MaintenanceService.post_maintenance_expense(
                    job=job,
                    account=cd['account'],
                    category=cd['category'],
                    user=request.user,
                    payment_method=cd['payment_method'],
                    request=request
                )
                messages.success(request, f"Maintenance Job posted to Expense '{expense.expense_code}' (₹{expense.amount:,.2f}).")
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
        else:
            for field, errs in form.errors.items():
                messages.error(request, f"{field}: {errs[0]}")
    return redirect('machines:maintenance_job_detail', job_id=job_id)


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_schedule_list_view(request):
    """Lists all preventive maintenance schedules with live evaluation status."""
    schedules = MachineMaintenanceSchedule.objects.filter(machine__is_deleted=False).select_related('machine')
    machine_id = request.GET.get('machine', '').strip()
    if machine_id:
        schedules = schedules.filter(machine_id=machine_id)

    evaluated_schedules = []
    for s in schedules:
        s.eval_status = s.evaluate_status()
        evaluated_schedules.append(s)

    return render(request, 'machines/maintenance_schedule_list.html', {
        'schedules': evaluated_schedules,
        'machines': Machine.objects.filter(is_deleted=False),
        'selected_machine': machine_id,
        'title': 'Preventive Maintenance Schedules',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_schedule_create_view(request):
    """Creates a new preventive maintenance schedule."""
    if request.method == 'POST':
        form = MachineMaintenanceScheduleForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                schedule = MaintenanceService.create_schedule(
                    machine=cd['machine'],
                    schedule_name=cd['schedule_name'],
                    service_basis=cd['service_basis'],
                    service_interval_meter=cd.get('service_interval_meter'),
                    service_interval_days=cd.get('service_interval_days'),
                    last_service_date=cd.get('last_service_date'),
                    last_service_meter=cd.get('last_service_meter'),
                    warning_meter_before=cd.get('warning_meter_before', Decimal('25.00')),
                    warning_days_before=cd.get('warning_days_before', 7),
                    notes=cd.get('notes'),
                    created_by=request.user,
                    request=request
                )
                messages.success(request, f"Maintenance Schedule '{schedule.schedule_name}' created for {schedule.machine.name}.")
                return redirect('machines:maintenance_schedule_list')
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
    else:
        initial = {}
        if request.GET.get('machine_id'):
            initial['machine'] = request.GET.get('machine_id')
        form = MachineMaintenanceScheduleForm(initial=initial)

    return render(request, 'machines/maintenance_schedule_form.html', {
        'form': form,
        'title': 'Create Maintenance Schedule',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def maintenance_schedule_edit_view(request, schedule_id):
    """Edits a preventive maintenance schedule."""
    schedule = get_object_or_404(MachineMaintenanceSchedule, id=schedule_id)
    if request.method == 'POST':
        form = MachineMaintenanceScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                updated = MaintenanceService.update_schedule(
                    schedule=schedule,
                    schedule_name=cd['schedule_name'],
                    service_basis=cd['service_basis'],
                    service_interval_meter=cd.get('service_interval_meter'),
                    service_interval_days=cd.get('service_interval_days'),
                    last_service_date=cd.get('last_service_date'),
                    last_service_meter=cd.get('last_service_meter'),
                    warning_meter_before=cd.get('warning_meter_before', Decimal('25.00')),
                    warning_days_before=cd.get('warning_days_before', 7),
                    notes=cd.get('notes'),
                    is_active=cd.get('is_active', True),
                    user=request.user,
                    request=request
                )
                messages.success(request, f"Maintenance Schedule '{updated.schedule_name}' updated.")
                return redirect('machines:maintenance_schedule_list')
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
    else:
        form = MachineMaintenanceScheduleForm(instance=schedule)

    return render(request, 'machines/maintenance_schedule_form.html', {
        'form': form,
        'schedule': schedule,
        'title': f"Edit Schedule: {schedule.schedule_name}",
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def machine_service_history_view(request, machine_id):
    """
    Dedicated Service & Breakdown History Timeline for a specific Machine.
    """
    machine = get_object_or_404(Machine, id=machine_id, is_deleted=False)
    jobs = machine.maintenance_jobs.filter(is_deleted=False).select_related('supplier', 'linked_expense').order_by('-reported_date', '-id')
    schedules = machine.maintenance_schedules.filter(is_active=True)

    # Statistics
    total_jobs = jobs.count()
    preventive_count = jobs.filter(maintenance_type=MaintenanceJob.TYPE_PREVENTIVE_SERVICE).count()
    breakdown_count = jobs.filter(maintenance_type=MaintenanceJob.TYPE_BREAKDOWN_REPAIR).count()
    total_maintenance_cost = jobs.filter(status=MaintenanceJob.STATUS_COMPLETED).aggregate(total=Sum('total_maintenance_cost'))['total'] or Decimal('0.00')

    for s in schedules:
        s.eval_status = s.evaluate_status()

    return render(request, 'machines/maintenance_history.html', {
        'machine': machine,
        'jobs': jobs,
        'schedules': schedules,
        'total_jobs': total_jobs,
        'preventive_count': preventive_count,
        'breakdown_count': breakdown_count,
        'total_maintenance_cost': total_maintenance_cost,
        'title': f"Service History: {machine.name} ({machine.machine_code})",
    })


# ==============================================================================
# RENTED COMBINE HARVESTER OWNERS & SETTLEMENTS (STEP 1 & STEP 5)
# ==============================================================================

@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def rented_owners_list_view(request):
    """
    Rented Combine Harvester Owners 360 & Settlement Ledger Hub.
    """
    query = request.GET.get('q', '').strip()
    active_tab = request.GET.get('tab', 'ledger')

    owners = RentedHarvesterOwner.objects.filter(is_deleted=False).prefetch_related('machines', 'settlements').order_by('name')
    if query:
        owners = owners.filter(
            Q(name__icontains=query) |
            Q(owner_code__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(village__icontains=query)
        )

    settlements = RentedHarvesterSettlement.objects.select_related('owner', 'work_entry', 'work_entry__machine', 'work_entry__customer').order_by('-created_at')

    # Metrics
    total_owners_count = owners.count()
    rented_machines_count = Machine.objects.filter(is_deleted=False, ownership_type=Machine.OWNERSHIP_RENTED).count()
    total_gross_settlements = settlements.aggregate(s=Sum('gross_earnings'))['s'] or Decimal('0.00')
    total_pending_payout = settlements.filter(status=RentedHarvesterSettlement.STATUS_PENDING).aggregate(s=Sum('net_payable'))['s'] or Decimal('0.00')

    form = RentedHarvesterOwnerForm()

    return render(request, 'machines/rented_owners_list.html', {
        'owners': owners,
        'settlements': settlements,
        'form': form,
        'active_tab': active_tab,
        'query': query,
        'total_owners_count': total_owners_count,
        'rented_machines_count': rented_machines_count,
        'total_gross_settlements': total_gross_settlements,
        'total_pending_payout': total_pending_payout,
        'title': 'Rented Fleet Owners 360° | Sri Basaveshwara & Co',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def rented_owner_create_view(request):
    """Creates a new third-party combine harvester owner."""
    if request.method == 'POST':
        form = RentedHarvesterOwnerForm(request.POST)
        if form.is_valid():
            owner = form.save()
            messages.success(request, f"Rented Harvester Owner '{owner.name}' registered successfully.")
            return redirect('machines:rented_owners')
        else:
            messages.error(request, "Please correct the errors in the owner form.")
    return redirect('machines:rented_owners')


@role_required(['OWNER', 'ACCOUNTANT'])
def rented_settlement_settle_view(request, settlement_id):
    """Marks a rented owner payout settlement as paid / settled."""
    settlement = get_object_or_404(RentedHarvesterSettlement, id=settlement_id)
    if request.method == 'POST':
        ref = request.POST.get('reference_no', '').strip()
        settlement.status = RentedHarvesterSettlement.STATUS_SETTLED
        settlement.settled_at = timezone.now()
        settlement.settlement_reference = ref or f"PAID-{timezone.now().strftime('%Y%m%d%H%M')}"
        settlement.save(update_fields=['status', 'settled_at', 'settlement_reference', 'updated_at'])
        messages.success(request, f"Settlement of ₹{settlement.net_payable:,.2f} marked as SETTLED to {settlement.owner.name}.")
    return redirect('machines:rented_owners')


# ==============================================================================
# HARVESTER & TRANSIT TRUCK COMPLIANCE (STEP 2)
# ==============================================================================

@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def harvester_compliance_list_view(request):
    """
    RTO Compliance & Expiry Reminder Center for Harvesters and Transit Trucks.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('filter', 'all').strip()

    records = HarvesterCompliance.objects.filter(is_deleted=False).select_related('machine', 'rented_owner').order_by('registration_no')
    if query:
        records = records.filter(
            Q(registration_no__icontains=query) |
            Q(vehicle_name__icontains=query) |
            Q(owner_name__icontains=query)
        )

    # Calculate live status on records
    expired_count = 0
    expiring_soon_count = 0
    valid_count = 0

    evaluated_records = []
    for r in records:
        overall = r.overall_status
        r.evaluated_overall = overall
        if overall == 'EXPIRED':
            expired_count += 1
        elif overall == 'EXPIRING_SOON':
            expiring_soon_count += 1
        else:
            valid_count += 1

        if status_filter == 'expired' and overall != 'EXPIRED':
            continue
        elif status_filter == 'expiring' and overall != 'EXPIRING_SOON':
            continue
        evaluated_records.append(r)

    total_count = len(records)
    health_pct = round((valid_count / total_count * 100)) if total_count > 0 else 100

    form = HarvesterComplianceForm()

    return render(request, 'machines/compliance_list.html', {
        'records': evaluated_records,
        'form': form,
        'total_count': total_count,
        'expired_count': expired_count,
        'expiring_soon_count': expiring_soon_count,
        'valid_count': valid_count,
        'health_pct': health_pct,
        'status_filter': status_filter,
        'query': query,
        'title': 'Truck Compliance & Expiry Reminder Center',
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def harvester_compliance_create_view(request):
    """Registers a new vehicle/harvester compliance record."""
    if request.method == 'POST':
        form = HarvesterComplianceForm(request.POST)
        if form.is_valid():
            comp = form.save()
            messages.success(request, f"Compliance record for '{comp.registration_no}' ({comp.vehicle_name}) saved.")
            return redirect('machines:compliance_list')
        else:
            messages.error(request, "Please correct the errors in the compliance form.")
    return redirect('machines:compliance_list')


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def harvester_compliance_whatsapp_view(request, compliance_id):
    """Generates the pre-filled WhatsApp alert redirect for vehicle compliance renewal."""
    comp = get_object_or_404(HarvesterCompliance, id=compliance_id, is_deleted=False)
    msg = comp.generate_whatsapp_alert_text()
    phone = comp.owner_phone or ''
    # Clean phone number (strip spaces/dashes)
    clean_phone = re.sub(r'\D', '', phone)
    if clean_phone and not clean_phone.startswith('91') and len(clean_phone) == 10:
        clean_phone = '91' + clean_phone
    import urllib.parse
    encoded_msg = urllib.parse.quote(msg)
    whatsapp_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}" if clean_phone else f"https://api.whatsapp.com/send?text={encoded_msg}"
    return redirect(whatsapp_url)


# ==============================================================================
# PRINTABLE HARVESTING BILL INVOICE & UDHAR RECEIPT (STEP 3 & 4)
# ==============================================================================

@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def work_entry_invoice_view(request, entry_id):
    """
    Renders the printable official Harvesting Bill & Udhar Receipt for a farmer.
    """
    entry = get_object_or_404(
        MachineWorkEntry.objects.select_related(
            'machine', 'customer', 'operator', 'receivable', 'harvester_settlement', 'harvester_settlement__owner'
        ),
        id=entry_id,
        is_deleted=False
    )
    import urllib.parse
    phone = re.sub(r'\D', '', entry.customer.phone or '')
    if phone and not phone.startswith('91') and len(phone) == 10:
        phone = '91' + phone

    # Calculate Farmer cumulative outstanding Udhar balance across all bills
    from django.db.models import Sum, F
    farmer_outstanding_udhar = entry.customer.receivables.filter(
        is_deleted=False
    ).exclude(status='PAID').aggregate(
        s=Sum(F('total_amount') - F('received_amount'))
    )['s'] or Decimal('0.00')

    pm_label = entry.get_payment_mode_display() if hasattr(entry, 'get_payment_mode_display') else entry.payment_mode
    wa_msg = (
        f"🌾 *SRI BASAVESHWARA & CO.*\n"
        f"*Harvesting Bill & Farmer Receipt*\n"
        f"--------------------------------\n"
        f"• Bill No: {entry.manual_bill_no or entry.work_code}\n"
        f"• Date: {entry.work_date.strftime('%d-%m-%Y')}\n"
        f"• Farmer: {entry.customer.name} ({entry.customer.location_address or 'Field'})\n"
        f"• Mobile: {entry.customer.phone or '--'}\n"
        f"• Machine: {entry.machine.name} ({entry.machine.registration_no or entry.machine.machine_code})\n"
        f"• Operator: {entry.operator.full_name if entry.operator else 'Basaveshwara Crew'}\n"
        f"• Timings: {entry.start_time or ''} - {entry.end_time or ''} (Net: {entry.net_working_hours} hrs)\n"
        f"• Cutting Rate: ₹{entry.hourly_rate:,.2f}/hr\n"
        f"--------------------------------\n"
        f"• Gross Total: ₹{entry.total_amount:,.2f}\n"
        f"• Advance Paid: ₹{entry.advance_amount:,.2f} ({pm_label})\n"
        f"• Balance This Bill: ₹{entry.udhar_amount:,.2f}\n"
        f"• Total Outstanding Udhar: ₹{farmer_outstanding_udhar:,.2f}\n"
        f"--------------------------------\n"
        f"Thank you for choosing Sri Basaveshwara & Co."
    )
    encoded_msg = urllib.parse.quote(wa_msg)
    whatsapp_url = f"https://api.whatsapp.com/send?phone={phone}&text={encoded_msg}" if phone else f"https://api.whatsapp.com/send?text={encoded_msg}"

    return render(request, 'machines/work_entry_invoice.html', {
        'entry': entry,
        'farmer_outstanding_udhar': farmer_outstanding_udhar,
        'whatsapp_url': whatsapp_url,
        'title': f"Bill & Receipt: {entry.manual_bill_no or entry.work_code}",
    })


# ==============================================================================
# AJAX HELPERS FOR FARMER & MACHINE AUTOFILL
# ==============================================================================

@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def farmer_details_ajax_view(request, customer_id):
    """Returns customer details (name, phone, village/location, current udhar balance) for instant form autofill."""
    customer = get_object_or_404(Customer, id=customer_id, is_deleted=False)
    # Calculate outstanding balance from unpaid receivables
    unpaid = customer.receivables.filter(is_deleted=False).exclude(status='PAID').aggregate(
        s=Sum(F('total_amount') - F('received_amount'))
    )['s'] or Decimal('0.00')
    return JsonResponse({
        'name': customer.name,
        'phone': customer.phone or '',
        'village': customer.location_address or '',
        'outstanding_udhar': str(unpaid)
    })


@role_required(['OWNER', 'MANAGER', 'ACCOUNTANT'])
def machine_details_ajax_view(request, machine_id):
    """Returns machine details (hourly rate, ownership, owner name) for instant form autofill."""
    machine = get_object_or_404(Machine, id=machine_id, is_deleted=False)
    return JsonResponse({
        'name': machine.name,
        'machine_code': machine.machine_code,
        'hourly_rate': str(machine.hourly_rate),
        'ownership_type': machine.ownership_type,
        'is_rented': machine.ownership_type == Machine.OWNERSHIP_RENTED,
        'owner_name': machine.rented_owner.name if machine.rented_owner else None,
        'owner_rate': str(machine.rented_owner.standard_hourly_rate) if machine.rented_owner else str(machine.hourly_rate),
    })

