from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q, Sum
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.decorators import (
    role_required,
    manager_or_above_required,
    accountant_or_owner_required,
    owner_required
)
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog
from apps.finance.models import Account
from .models import Employee, EmployeePayment, EmployeeCompensation
from .forms import EmployeeForm, SalaryAccrualForm, EmployeePayoutForm, EmployeeCompensationForm
from .services.employee_service import EmployeeFinancialService


# ============================================================================
# OPERATIONAL EMPLOYEE DIRECTORY
# ============================================================================

@manager_or_above_required
def employee_list_view(request):
    """
    Operational staff directory (Accessible to Owner, Accountant, Manager).
    Manager sees operational roster; wage financial data is strictly partitioned.
    """
    query = request.GET.get('q', '').strip()
    role = request.GET.get('role', '').strip()
    status = request.GET.get('status', '').strip()

    employees = Employee.objects.filter(is_deleted=False).prefetch_related('compensations')
    if query:
        employees = employees.filter(
            Q(full_name__icontains=query) |
            Q(employee_code__icontains=query) |
            Q(phone_number__icontains=query)
        )
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
    """Registers a new employee record."""
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
    """Edits employee details."""
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


# ============================================================================
# FINANCIAL WAGE & PAYOUT MODULES (Strictly restricted to Owner & Accountant)
# ============================================================================

@accountant_or_owner_required
def employee_wages_view(request):
    """
    Employee financial hub listing all wage accruals, advances, and settlements.
    Restricted to Owner & Accountant.
    """
    query = request.GET.get('q', '').strip()
    emp_id = request.GET.get('employee', '').strip()
    p_type = request.GET.get('type', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    payments = EmployeePayment.objects.filter(is_deleted=False).select_related('employee', 'account', 'compensation', 'created_by')

    if query:
        payments = payments.filter(
            Q(payment_code__icontains=query) |
            Q(employee__full_name__icontains=query) |
            Q(reference_no__icontains=query) |
            Q(notes__icontains=query)
        )
    if emp_id:
        payments = payments.filter(employee_id=emp_id)
    if p_type:
        payments = payments.filter(payment_type=p_type)
    if start_date:
        payments = payments.filter(date__gte=start_date)
    if end_date:
        payments = payments.filter(date__lte=end_date)

    total_accrued = payments.filter(payment_type=EmployeePayment.TYPE_SALARY_ACCRUAL, is_reversed=False).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    total_disbursed = payments.filter(payment_type__in=[
        EmployeePayment.TYPE_ADVANCE_PAYOUT,
        EmployeePayment.TYPE_SALARY_SETTLEMENT,
        EmployeePayment.TYPE_BONUS
    ], is_reversed=False).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    return render(request, 'employees/employee_wages_list.html', {
        'payments': payments,
        'employees': Employee.objects.filter(is_deleted=False),
        'total_accrued': total_accrued,
        'total_disbursed': total_disbursed,
        'query': query,
        'emp_id': emp_id,
        'p_type': p_type,
        'start_date': start_date,
        'end_date': end_date,
        'title': 'Employee Wages & Payouts',
    })


@accountant_or_owner_required
def employee_financial_profile_view(request, employee_id):
    """
    Detailed financial ledger profile for an individual staff member.
    Shows Compensations, Accruals, Advances, Settlements, Net Outstanding, and Payment History.
    """
    emp = get_object_or_404(Employee, id=employee_id, is_deleted=False)
    balances = EmployeeFinancialService.calculate_employee_balances(emp.id)

    compensations = emp.compensations.all().order_by('-is_active', '-effective_from')
    payment_history = EmployeePayment.objects.filter(
        employee=emp,
        is_deleted=False
    ).select_related('account', 'compensation', 'linked_ledger_transaction', 'created_by').order_by('-date', '-id')

    return render(request, 'employees/employee_financial_profile.html', {
        'employee': emp,
        'balances': balances,
        'compensations': compensations,
        'payment_history': payment_history,
        'title': f"Financial Ledger: {emp.full_name}",
    })


@accountant_or_owner_required
def employee_compensation_create_view(request, employee_id):
    """Adds a new compensation rate structure to an employee."""
    emp = get_object_or_404(Employee, id=employee_id, is_deleted=False)
    if request.method == 'POST':
        form = EmployeeCompensationForm(request.POST)
        if form.is_valid():
            try:
                comp = EmployeeFinancialService.add_compensation(
                    user=request.user,
                    employee=emp,
                    wage_type=form.cleaned_data['wage_type'],
                    rate=form.cleaned_data['rate'],
                    effective_from=form.cleaned_data['effective_from'],
                    effective_to=form.cleaned_data.get('effective_to'),
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Added compensation rate: {comp.get_wage_type_display()} (₹{comp.rate}) for {emp.full_name}.")
                return redirect('employees:financial_profile', employee_id=emp.id)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = EmployeeCompensationForm(initial={'effective_from': timezone.now().date(), 'is_active': True})

    return render(request, 'employees/employee_compensation_form.html', {
        'form': form,
        'employee': emp,
        'title': f"Add Compensation Rate: {emp.full_name}",
    })


@accountant_or_owner_required
def employee_compensation_edit_view(request, compensation_id):
    """Edits an existing compensation rate structure."""
    comp = get_object_or_404(EmployeeCompensation, id=compensation_id)
    emp = comp.employee
    if request.method == 'POST':
        form = EmployeeCompensationForm(request.POST, instance=comp)
        if form.is_valid():
            try:
                updated = EmployeeFinancialService.update_compensation(
                    user=request.user,
                    compensation_id=comp.id,
                    rate=form.cleaned_data['rate'],
                    effective_from=form.cleaned_data['effective_from'],
                    effective_to=form.cleaned_data.get('effective_to'),
                    is_active=form.cleaned_data.get('is_active', True),
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Updated compensation rate for {emp.full_name}.")
                return redirect('employees:financial_profile', employee_id=emp.id)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = EmployeeCompensationForm(instance=comp)

    return render(request, 'employees/employee_compensation_form.html', {
        'form': form,
        'employee': emp,
        'compensation': comp,
        'title': f"Edit Compensation: {emp.full_name}",
    })


@accountant_or_owner_required
def employee_compensation_toggle_view(request, compensation_id):
    """Toggles active/inactive status of a compensation structure."""
    comp = get_object_or_404(EmployeeCompensation, id=compensation_id)
    emp = comp.employee
    if comp.is_active:
        EmployeeFinancialService.deactivate_compensation(user=request.user, compensation_id=comp.id, request=request)
        messages.warning(request, f"Deactivated {comp.get_wage_type_display()} for {emp.full_name}.")
    else:
        EmployeeFinancialService.update_compensation(
            user=request.user,
            compensation_id=comp.id,
            rate=comp.rate,
            effective_from=comp.effective_from,
            effective_to=None,
            is_active=True,
            notes=comp.notes,
            request=request
        )
        messages.success(request, f"Activated {comp.get_wage_type_display()} for {emp.full_name}.")

    return redirect('employees:financial_profile', employee_id=emp.id)


@accountant_or_owner_required
def employee_accrual_create_view(request):
    """
    Records earned salary, daily wage, or commission (increases wage liability).
    RULE 4: Does NOT move cash/bank money.
    """
    initial_emp_id = request.GET.get('employee')
    initial_comp_id = request.GET.get('compensation')
    if request.method == 'POST':
        form = SalaryAccrualForm(request.POST)
        if form.is_valid():
            try:
                accrual = EmployeeFinancialService.record_salary_accrual(
                    user=request.user,
                    employee=form.cleaned_data['employee'],
                    amount=form.cleaned_data['amount'],
                    compensation=form.cleaned_data.get('compensation'),
                    units_logged=form.cleaned_data.get('units_logged'),
                    date_val=form.cleaned_data['date'],
                    reference_no=form.cleaned_data.get('reference_no'),
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Wage accrual of ₹{accrual.amount} recorded for {accrual.employee.full_name}.")
                return redirect('employees:financial_profile', employee_id=accrual.employee.id)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        initial = {}
        if initial_emp_id:
            initial['employee'] = initial_emp_id
        if initial_comp_id:
            initial['compensation'] = initial_comp_id
        form = SalaryAccrualForm(initial=initial)

    return render(request, 'employees/employee_accrual_form.html', {
        'form': form,
        'title': 'Record Wage / Salary Accrual',
    })


@accountant_or_owner_required
def employee_payout_create_view(request):
    """
    Records an actual money payout (Advance Payout, Salary Settlement, Bonus).
    Atomically debits central financial ledger.
    """
    initial_emp = request.GET.get('employee')
    initial_type = request.GET.get('type', EmployeePayment.TYPE_SALARY_SETTLEMENT)

    if request.method == 'POST':
        form = EmployeePayoutForm(request.POST)
        if form.is_valid():
            try:
                payout = EmployeeFinancialService.record_payout(
                    user=request.user,
                    employee=form.cleaned_data['employee'],
                    payment_type=form.cleaned_data['payment_type'],
                    amount=form.cleaned_data['amount'],
                    account=form.cleaned_data['account'],
                    payment_method=form.cleaned_data['payment_method'],
                    date_val=form.cleaned_data['date'],
                    reference_no=form.cleaned_data.get('reference_no'),
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Payout '{payout.payment_code}' of ₹{payout.amount} debited from {payout.account.account_name}.")
                return redirect('employees:financial_profile', employee_id=payout.employee.id)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = EmployeePayoutForm(initial={'employee': initial_emp, 'payment_type': initial_type})

    return render(request, 'employees/employee_payout_form.html', {
        'form': form,
        'title': 'Disburse Staff Payout',
    })


@require_POST
@owner_required
def employee_payment_reverse_view(request, payment_id):
    """
    Reverses an employee payment or wage accrual (Owner only).
    """
    reason = request.POST.get('reason', '').strip()
    try:
        payment = EmployeeFinancialService.reverse_payment(
            payment_id=payment_id,
            user=request.user,
            reason=reason,
            request=request
        )
        messages.success(request, f"Payment '{payment.payment_code}' successfully reversed.")
    except (ValidationError, Exception) as e:
        messages.error(request, f"Reversal failed: {str(e)}")

    return redirect('employees:financial_profile', employee_id=payment.employee.id if 'payment' in locals() else 1)

