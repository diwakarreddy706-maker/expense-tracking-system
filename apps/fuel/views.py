from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q, Sum, Avg
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError

from apps.accounts.decorators import role_required, owner_required
from apps.machines.models import Machine
from apps.finance.models import Account, Supplier
from apps.employees.models import Employee
from .models import FuelEntry
from .forms import FuelEntryForm
from .services.fuel_service import FuelService


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER', 'EMPLOYEE'])
def fuel_list_view(request):
    """
    Lists Fuel & Lubricant logs with search, machine filtering, and summary statistics.
    """
    query = request.GET.get('q', '').strip()
    mch_id = request.GET.get('machine', '').strip()
    f_type = request.GET.get('type', '').strip()
    supp_id = request.GET.get('supplier', '').strip()
    acc_id = request.GET.get('account', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    entries = FuelEntry.objects.filter(is_deleted=False).select_related(
        'machine', 'supplier', 'account', 'operator', 'linked_expense', 'created_by'
    )

    if query:
        entries = entries.filter(
            Q(fuel_code__icontains=query) |
            Q(machine__name__icontains=query) |
            Q(reference_no__icontains=query) |
            Q(notes__icontains=query)
        )
    if mch_id:
        entries = entries.filter(machine_id=mch_id)
    if f_type:
        entries = entries.filter(fuel_type=f_type)
    if supp_id:
        entries = entries.filter(supplier_id=supp_id)
    if acc_id:
        entries = entries.filter(account_id=acc_id)
    if start_date:
        entries = entries.filter(date__gte=start_date)
    if end_date:
        entries = entries.filter(date__lte=end_date)

    # Basic analytics preparation (Section 22)
    stats = entries.aggregate(
        total_litres=Sum('quantity'),
        total_fuel_cost=Sum('total_amount'),
        avg_price=Avg('unit_price')
    )

    return render(request, 'fuel/fuel_list.html', {
        'entries': entries,
        'machines': Machine.objects.filter(is_deleted=False),
        'suppliers': Supplier.objects.filter(is_deleted=False),
        'accounts': Account.objects.filter(is_deleted=False, is_active=True),
        'stats': stats,
        'query': query,
        'mch_id': mch_id,
        'f_type': f_type,
        'supp_id': supp_id,
        'acc_id': acc_id,
        'start_date': start_date,
        'end_date': end_date,
        'title': 'Fuel & Lubricants Tracking',
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER', 'EMPLOYEE'])
def fuel_create_view(request):
    """
    Records a new fuel log and posts its 1:1 linked Expense and Ledger entries atomically.
    """
    if request.method == 'POST':
        form = FuelEntryForm(request.POST)
        if form.is_valid():
            try:
                fuel_entry = FuelService.create_fuel_entry(
                    user=request.user,
                    machine=form.cleaned_data['machine'],
                    fuel_type=form.cleaned_data['fuel_type'],
                    quantity=form.cleaned_data['quantity'],
                    unit_price=form.cleaned_data['unit_price'],
                    meter_reading=form.cleaned_data['meter_reading'],
                    payment_method=form.cleaned_data['payment_method'],
                    account=form.cleaned_data.get('account'),
                    supplier=form.cleaned_data.get('supplier'),
                    operator=form.cleaned_data.get('operator'),
                    date_val=form.cleaned_data['date'],
                    reference_no=form.cleaned_data.get('reference_no'),
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Fuel log '{fuel_entry.fuel_code}' (₹{fuel_entry.total_amount}) posted to expense ledger.")
                return redirect('fuel:list')
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = FuelEntryForm()

    return render(request, 'fuel/fuel_form.html', {
        'form': form,
        'title': 'Record Fuel / Lubricant Log',
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER', 'EMPLOYEE'])
def fuel_detail_view(request, fuel_id):
    """
    Detailed inspector for a fuel entry, linked expense, and central ledger debit.
    """
    entry = get_object_or_404(
        FuelEntry.objects.select_related(
            'machine', 'supplier', 'account', 'operator',
            'linked_expense', 'created_by'
        ),
        id=fuel_id,
        is_deleted=False
    )
    
    # Linked ledger transaction via linked_expense
    ledger_tx = None
    if entry.linked_expense:
        ledger_tx = entry.linked_expense.account.ledger_transactions.filter(
            reference_type='Expense',
            reference_id=entry.linked_expense.id,
            is_deleted=False
        ).first() if entry.linked_expense.account else None

    return render(request, 'fuel/fuel_detail.html', {
        'entry': entry,
        'ledger_tx': ledger_tx,
        'title': f"Fuel Log: {entry.fuel_code}",
    })


@require_POST
@owner_required
def fuel_reverse_view(request, fuel_id):
    """
    Financial reversal for a fuel entry (Owner only).
    """
    reason = request.POST.get('reason', '').strip()
    try:
        fuel_entry = FuelService.reverse_fuel_entry(
            fuel_entry_id=fuel_id,
            user=request.user,
            reason=reason,
            request=request
        )
        messages.success(request, f"Fuel log '{fuel_entry.fuel_code}' successfully reversed.")
    except (ValidationError, Exception) as e:
        messages.error(request, f"Reversal failed: {str(e)}")

    return redirect('fuel:detail', fuel_id=fuel_id)
