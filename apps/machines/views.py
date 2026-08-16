from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.exceptions import ValidationError
from decimal import Decimal
from apps.accounts.decorators import role_required, owner_required
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog
from .models import Machine, MachineType, MachineBooking, MachineWorkEntry
from .forms import (
    MachineForm, MachineTypeForm, MachineBookingForm,
    BookingConfirmForm, BookingDispatchForm, BookingCancelForm,
    MachineWorkEntryForm
)
from .services.work_service import WorkService
from .services.booking_service import BookingService
from apps.finance.models import Customer
from apps.employees.models import Employee


@role_required(['OWNER', 'MANAGER'])
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


@role_required(['OWNER', 'MANAGER'])
def machine_create_view(request):
    """Creates a new machine record."""
    if request.method == 'POST':
        form = MachineForm(request.POST)
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
            messages.success(request, f"Machine '{machine.name}' ({machine.machine_code}) added.")
            return redirect('machines:list')
    else:
        form = MachineForm()

    return render(request, 'machines/machine_form.html', {
        'form': form,
        'title': 'Add New Machine / Equipment',
    })


@role_required(['OWNER', 'MANAGER'])
def machine_edit_view(request, machine_id):
    """Edits an existing machine."""
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


@role_required(['OWNER', 'MANAGER'])
def booking_create_view(request):
    """Creates a new customer machine booking."""
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


@role_required(['OWNER', 'MANAGER'])
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


@role_required(['OWNER', 'MANAGER'])
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


@role_required(['OWNER', 'MANAGER'])
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


@role_required(['OWNER', 'MANAGER'])
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


@role_required(['OWNER', 'MANAGER'])
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


@role_required(['OWNER', 'MANAGER'])
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
                break_hours=cd.get('break_hours', Decimal('0.00')),
                hourly_rate=cd.get('hourly_rate', Decimal('0.00')),
                quantity=cd.get('quantity', Decimal('0.00')),
                unit_rate=cd.get('unit_rate', Decimal('0.00')),
                start_meter=cd.get('start_meter'),
                end_meter=cd.get('end_meter'),
                notes=cd.get('notes'),
                created_by=request.user,
                request=request
            )
            messages.success(request, f"Work Entry '{entry.work_code}' recorded. Billed Total: ₹{entry.total_amount:,.2f}")
            if entry.booking:
                return redirect('machines:booking_detail', booking_id=entry.booking.id)
            return redirect('machines:work_list')
    else:
        form = MachineWorkEntryForm(initial=initial_data)

    return render(request, 'machines/work_entry_form.html', {
        'form': form,
        'linked_booking': linked_booking,
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
        'title': f"Edit Work Entry: {entry.work_code}",
    })


@owner_required
def work_entry_delete_view(request, entry_id):
    """Soft deletes a machine work entry (Owner only)."""
    entry = get_object_or_404(MachineWorkEntry, id=entry_id, is_deleted=False)
    WorkService.soft_delete_work_entry(entry, request.user, request=request)
    messages.warning(request, f"Work Entry '{entry.work_code}' deleted.")
    return redirect('machines:work_list')
