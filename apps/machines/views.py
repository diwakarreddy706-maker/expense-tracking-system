from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum
from decimal import Decimal
from apps.accounts.decorators import role_required, owner_required
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog
from .models import Machine, MachineType, MachineWorkEntry
from .forms import MachineForm, MachineTypeForm, MachineWorkEntryForm
from .services.work_service import WorkService
from apps.finance.models import Customer


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
        'machine', 'machine__machine_type', 'customer', 'operator', 'created_by'
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
    """Records a new machine work and commercial calculation entry."""
    if request.method == 'POST':
        form = MachineWorkEntryForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            entry = WorkService.create_work_entry(
                work_date=cd['work_date'],
                machine=cd['machine'],
                customer=cd['customer'],
                operator=cd.get('operator'),
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
            return redirect('machines:work_list')
    else:
        form = MachineWorkEntryForm()

    return render(request, 'machines/work_entry_form.html', {
        'form': form,
        'title': 'Record Machine Work Entry',
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
