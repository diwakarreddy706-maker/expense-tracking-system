from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from apps.accounts.decorators import role_required, owner_required
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog
from .models import Machine, MachineType
from .forms import MachineForm, MachineTypeForm


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
