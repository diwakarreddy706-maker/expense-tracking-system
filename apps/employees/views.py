from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from apps.accounts.decorators import role_required, manager_or_above_required, accountant_or_owner_required, owner_required
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog
from .models import Employee
from .forms import EmployeeForm


@manager_or_above_required
def employee_list_view(request):
    """Lists employees with search and status filtering."""
    query = request.GET.get('q', '').strip()
    role = request.GET.get('role', '').strip()
    status = request.GET.get('status', '').strip()

    employees = Employee.objects.filter(is_deleted=False)
    if query:
        employees = employees.filter(Q(full_name__icontains=query) | Q(employee_code__icontains=query) | Q(phone_number__icontains=query))
    if role:
        employees = employees.filter(role=role)
    if status:
        employees = employees.filter(status=status)

    return render(request, 'employees/employee_list.html', {
        'employees': employees,
        'query': query,
        'role': role,
        'status': status,
        'title': 'Staff & Operator Directory',
    })


@manager_or_above_required
def employee_create_view(request):
    """Creates a new employee record."""
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            emp = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_CREATE,
                'Employee',
                emp.id,
                changes={'employee_code': emp.employee_code, 'name': emp.full_name, 'role': emp.role},
                request=request
            )
            messages.success(request, f"Employee '{emp.full_name}' ({emp.employee_code}) registered.")
            return redirect('employees:list')
    else:
        form = EmployeeForm()

    return render(request, 'employees/employee_form.html', {
        'form': form,
        'title': 'Register New Employee',
    })


@manager_or_above_required
def employee_edit_view(request, employee_id):
    """Edits an existing employee record."""
    emp = get_object_or_404(Employee, id=employee_id, is_deleted=False)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=emp)
        if form.is_valid():
            updated = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_UPDATE,
                'Employee',
                updated.id,
                changes={'name': updated.full_name, 'status': updated.status},
                request=request
            )
            messages.success(request, f"Employee '{updated.full_name}' updated.")
            return redirect('employees:list')
    else:
        form = EmployeeForm(instance=emp)

    return render(request, 'employees/employee_form.html', {
        'form': form,
        'employee': emp,
        'title': f"Edit Employee: {emp.full_name}",
    })


@owner_required
def employee_delete_view(request, employee_id):
    """Soft deletes an employee record (Owner only)."""
    emp = get_object_or_404(Employee, id=employee_id, is_deleted=False)
    emp.is_deleted = True
    emp.save()
    log_audit_event(
        request.user,
        AuditLog.ACTION_SOFT_DELETE,
        'Employee',
        emp.id,
        request=request
    )
    messages.warning(request, f"Employee '{emp.full_name}' deleted.")
    return redirect('employees:list')


@accountant_or_owner_required
def employee_wages_view(request):
    """Financial wage accruals & advance payouts (Owner & Accountant only)."""
    return render(request, 'base.html', {'title': 'Employee Wages & Payouts'})
