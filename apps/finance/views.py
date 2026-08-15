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
from .models import (
    Account, Customer, Supplier,
    Receivable, CustomerPayment,
    Payable, SupplierPayment,
    DailyClosing
)
from .forms import (
    AccountForm, CustomerForm, SupplierForm,
    ReceivableForm, CustomerPaymentForm,
    PayableForm, SupplierPaymentForm,
    DailyClosingForm
)
from .services.settlement_service import (
    CustomerReceivableService,
    SupplierPayableService
)


# ============================================================================
# BUSINESS ACCOUNTS MASTER
# ============================================================================

@accountant_or_owner_required
def accounts_list_view(request):
    """Lists business accounts with search and filtering."""
    query = request.GET.get('q', '').strip()
    acc_type = request.GET.get('type', '').strip()

    accounts = Account.objects.filter(is_deleted=False)
    if query:
        accounts = accounts.filter(Q(account_name__icontains=query) | Q(account_number__icontains=query) | Q(bank_name__icontains=query))
    if acc_type:
        accounts = accounts.filter(account_type=acc_type)

    return render(request, 'finance/accounts_list.html', {
        'accounts': accounts,
        'query': query,
        'acc_type': acc_type,
        'title': 'Business Financial Accounts',
    })


@accountant_or_owner_required
def account_create_view(request):
    """Creates a new financial account."""
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_CREATE,
                'Account',
                account.id,
                changes={'account_name': account.account_name, 'type': account.account_type},
                request=request
            )
            messages.success(request, f"Account '{account.account_name}' created successfully.")
            return redirect('finance:accounts')
    else:
        form = AccountForm()

    return render(request, 'finance/account_form.html', {
        'form': form,
        'title': 'Add New Business Account',
    })


@accountant_or_owner_required
def account_edit_view(request, account_id):
    """Edits an existing financial account."""
    account = get_object_or_404(Account, id=account_id, is_deleted=False)
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            updated = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_UPDATE,
                'Account',
                updated.id,
                changes={'account_name': updated.account_name},
                request=request
            )
            messages.success(request, f"Account '{updated.account_name}' updated.")
            return redirect('finance:accounts')
    else:
        form = AccountForm(instance=account)

    return render(request, 'finance/account_form.html', {
        'form': form,
        'account': account,
        'title': f"Edit Account: {account.account_name}",
    })


@accountant_or_owner_required
def account_toggle_status_view(request, account_id):
    """Toggles active/inactive status of an account (soft deactivate)."""
    account = get_object_or_404(Account, id=account_id, is_deleted=False)
    account.is_active = not account.is_active
    account.save()
    log_audit_event(
        request.user,
        AuditLog.ACTION_UPDATE,
        'Account',
        account.id,
        changes={'is_active': account.is_active},
        request=request
    )
    status_str = "activated" if account.is_active else "deactivated"
    messages.info(request, f"Account '{account.account_name}' {status_str}.")
    return redirect('finance:accounts')


# ============================================================================
# CUSTOMERS MASTER
# ============================================================================

@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def customers_list_view(request):
    """Lists customers with search and filtering."""
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    customers = Customer.objects.filter(is_deleted=False)
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(customer_code__icontains=query) | Q(phone__icontains=query))
    if status:
        customers = customers.filter(status=status)

    return render(request, 'finance/customers_list.html', {
        'customers': customers,
        'query': query,
        'status': status,
        'title': 'Customer & Farmer Directory',
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def customer_create_view(request):
    """Creates a new customer record."""
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_CREATE,
                'Customer',
                customer.id,
                changes={'customer_code': customer.customer_code, 'name': customer.name},
                request=request
            )
            messages.success(request, f"Customer '{customer.name}' ({customer.customer_code}) created.")
            return redirect('finance:customers')
    else:
        form = CustomerForm()

    return render(request, 'finance/customer_form.html', {
        'form': form,
        'title': 'Add New Customer',
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def customer_edit_view(request, customer_id):
    """Edits an existing customer."""
    customer = get_object_or_404(Customer, id=customer_id, is_deleted=False)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            updated = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_UPDATE,
                'Customer',
                updated.id,
                changes={'name': updated.name},
                request=request
            )
            messages.success(request, f"Customer '{updated.name}' updated.")
            return redirect('finance:customers')
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'finance/customer_form.html', {
        'form': form,
        'customer': customer,
        'title': f"Edit Customer: {customer.name}",
    })


@owner_required
def customer_delete_view(request, customer_id):
    """Soft deletes customer (Owner only)."""
    customer = get_object_or_404(Customer, id=customer_id, is_deleted=False)
    customer.is_deleted = True
    customer.save()
    log_audit_event(
        request.user,
        AuditLog.ACTION_SOFT_DELETE,
        'Customer',
        customer.id,
        request=request
    )
    messages.warning(request, f"Customer '{customer.name}' deleted.")
    return redirect('finance:customers')


# ============================================================================
# SUPPLIERS MASTER
# ============================================================================

@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def suppliers_list_view(request):
    """Lists suppliers with search and filtering."""
    query = request.GET.get('q', '').strip()
    supp_type = request.GET.get('type', '').strip()

    suppliers = Supplier.objects.filter(is_deleted=False)
    if query:
        suppliers = suppliers.filter(Q(name__icontains=query) | Q(supplier_code__icontains=query) | Q(phone__icontains=query))
    if supp_type:
        suppliers = suppliers.filter(supplier_type=supp_type)

    return render(request, 'finance/suppliers_list.html', {
        'suppliers': suppliers,
        'query': query,
        'supp_type': supp_type,
        'title': 'Suppliers & Vendors',
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def supplier_create_view(request):
    """Creates a new supplier."""
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_CREATE,
                'Supplier',
                supplier.id,
                changes={'supplier_code': supplier.supplier_code, 'name': supplier.name},
                request=request
            )
            messages.success(request, f"Supplier '{supplier.name}' ({supplier.supplier_code}) created.")
            return redirect('finance:suppliers')
    else:
        form = SupplierForm()

    return render(request, 'finance/supplier_form.html', {
        'form': form,
        'title': 'Add New Supplier',
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])
def supplier_edit_view(request, supplier_id):
    """Edits an existing supplier."""
    supplier = get_object_or_404(Supplier, id=supplier_id, is_deleted=False)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            updated = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_UPDATE,
                'Supplier',
                updated.id,
                changes={'name': updated.name},
                request=request
            )
            messages.success(request, f"Supplier '{updated.name}' updated.")
            return redirect('finance:suppliers')
    else:
        form = SupplierForm(instance=supplier)

    return render(request, 'finance/supplier_form.html', {
        'form': form,
        'supplier': supplier,
        'title': f"Edit Supplier: {supplier.name}",
    })


@owner_required
def supplier_delete_view(request, supplier_id):
    """Soft deletes supplier (Owner only)."""
    supplier = get_object_or_404(Supplier, id=supplier_id, is_deleted=False)
    supplier.is_deleted = True
    supplier.save()
    log_audit_event(
        request.user,
        AuditLog.ACTION_SOFT_DELETE,
        'Supplier',
        supplier.id,
        request=request
    )
    messages.warning(request, f"Supplier '{supplier.name}' deleted.")
    return redirect('finance:suppliers')


# ============================================================================
# CUSTOMER RECEIVABLES & SETTLEMENTS (Owner & Accountant)
# ============================================================================

@accountant_or_owner_required
def receivables_list_view(request):
    """Lists Customer Receivables with search, status filtering, and metrics."""
    query = request.GET.get('q', '').strip()
    cust_id = request.GET.get('customer', '').strip()
    status = request.GET.get('status', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    receivables = Receivable.objects.filter(is_deleted=False).select_related('customer', 'created_by')

    if query:
        receivables = receivables.filter(
            Q(receivable_code__icontains=query) |
            Q(customer__name__icontains=query) |
            Q(invoice_no__icontains=query) |
            Q(notes__icontains=query)
        )
    if cust_id:
        receivables = receivables.filter(customer_id=cust_id)
    if status:
        receivables = receivables.filter(status=status)
    if start_date:
        receivables = receivables.filter(bill_date__gte=start_date)
    if end_date:
        receivables = receivables.filter(bill_date__lte=end_date)

    metrics = CustomerReceivableService.get_receivable_metrics()

    return render(request, 'finance/receivables_list.html', {
        'receivables': receivables,
        'customers': Customer.objects.filter(is_deleted=False),
        'metrics': metrics,
        'query': query,
        'cust_id': cust_id,
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
        'title': 'Customer Receivables & Collections',
    })


@accountant_or_owner_required
def receivable_create_view(request):
    """Creates a new customer receivable obligation."""
    if request.method == 'POST':
        form = ReceivableForm(request.POST)
        if form.is_valid():
            try:
                rcv = CustomerReceivableService.create_receivable(
                    user=request.user,
                    customer=form.cleaned_data['customer'],
                    total_amount=form.cleaned_data['total_amount'],
                    bill_date=form.cleaned_data['bill_date'],
                    due_date=form.cleaned_data.get('due_date'),
                    invoice_no=form.cleaned_data.get('invoice_no'),
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Receivable '{rcv.receivable_code}' of ₹{rcv.total_amount} registered for {rcv.customer.name}.")
                return redirect('finance:receivable_detail', receivable_id=rcv.id)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = ReceivableForm()

    return render(request, 'finance/receivable_form.html', {
        'form': form,
        'title': 'Create Customer Receivable',
    })


@accountant_or_owner_required
def receivable_detail_view(request, receivable_id):
    """Detailed inspector for a customer receivable and its settlement payments."""
    rcv = get_object_or_404(
        Receivable.objects.select_related('customer', 'created_by'),
        id=receivable_id,
        is_deleted=False
    )
    payments = rcv.payments.filter(is_deleted=False).select_related('account', 'linked_ledger_transaction', 'created_by').order_by('-payment_date', '-id')

    return render(request, 'finance/receivable_detail.html', {
        'receivable': rcv,
        'payments': payments,
        'title': f"Receivable: {rcv.receivable_code}",
    })


@accountant_or_owner_required
def customer_payment_create_view(request, receivable_id):
    """Records a customer receipt against a receivable obligation."""
    rcv = get_object_or_404(Receivable, id=receivable_id, is_deleted=False)
    if rcv.status == Receivable.STATUS_PAID:
        messages.info(request, f"Receivable '{rcv.receivable_code}' is already fully paid.")
        return redirect('finance:receivable_detail', receivable_id=rcv.id)

    if request.method == 'POST':
        form = CustomerPaymentForm(request.POST)
        if form.is_valid():
            try:
                payment = CustomerReceivableService.record_payment(
                    user=request.user,
                    receivable_id=rcv.id,
                    amount=form.cleaned_data['amount'],
                    account=form.cleaned_data['account'],
                    payment_method=form.cleaned_data['payment_method'],
                    payment_date=form.cleaned_data['payment_date'],
                    reference_no=form.cleaned_data.get('reference_no'),
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Payment '{payment.payment_code}' of ₹{payment.amount} credited to {payment.account.account_name}.")
                return redirect('finance:receivable_detail', receivable_id=rcv.id)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = CustomerPaymentForm(initial={'amount': rcv.outstanding_amount})

    return render(request, 'finance/customer_payment_form.html', {
        'form': form,
        'receivable': rcv,
        'title': f"Receive Payment: {rcv.receivable_code}",
    })


@require_POST
@owner_required
def customer_payment_reverse_view(request, payment_id):
    """Reverses a customer payment (Owner only)."""
    reason = request.POST.get('reason', '').strip()
    try:
        payment = CustomerReceivableService.reverse_payment(
            payment_id=payment_id,
            user=request.user,
            reason=reason,
            request=request
        )
        messages.success(request, f"Customer payment '{payment.payment_code}' successfully reversed.")
        return redirect('finance:receivable_detail', receivable_id=payment.receivable_id)
    except (ValidationError, Exception) as e:
        messages.error(request, f"Reversal failed: {str(e)}")
        return redirect('finance:receivables')


# ============================================================================
# SUPPLIER PAYABLES & SETTLEMENTS (Owner & Accountant)
# ============================================================================

@accountant_or_owner_required
def payables_list_view(request):
    """Lists Supplier Payables with search, status filtering, and metrics."""
    query = request.GET.get('q', '').strip()
    supp_id = request.GET.get('supplier', '').strip()
    status = request.GET.get('status', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    payables = Payable.objects.filter(is_deleted=False).select_related('supplier', 'linked_expense', 'created_by')

    if query:
        payables = payables.filter(
            Q(payable_code__icontains=query) |
            Q(supplier__name__icontains=query) |
            Q(bill_no__icontains=query) |
            Q(notes__icontains=query)
        )
    if supp_id:
        payables = payables.filter(supplier_id=supp_id)
    if status:
        payables = payables.filter(status=status)
    if start_date:
        payables = payables.filter(bill_date__gte=start_date)
    if end_date:
        payables = payables.filter(bill_date__lte=end_date)

    metrics = SupplierPayableService.get_payable_metrics()

    return render(request, 'finance/payables_list.html', {
        'payables': payables,
        'suppliers': Supplier.objects.filter(is_deleted=False),
        'metrics': metrics,
        'query': query,
        'supp_id': supp_id,
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
        'title': 'Supplier Payables & Obligations',
    })


@accountant_or_owner_required
def payable_create_view(request):
    """Creates a new supplier payable obligation."""
    if request.method == 'POST':
        form = PayableForm(request.POST)
        if form.is_valid():
            try:
                pay = SupplierPayableService.create_payable(
                    user=request.user,
                    supplier=form.cleaned_data['supplier'],
                    total_amount=form.cleaned_data['total_amount'],
                    bill_date=form.cleaned_data['bill_date'],
                    due_date=form.cleaned_data.get('due_date'),
                    bill_no=form.cleaned_data.get('bill_no'),
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Payable '{pay.payable_code}' of ₹{pay.total_amount} registered for {pay.supplier.name}.")
                return redirect('finance:payable_detail', payable_id=pay.id)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = PayableForm()

    return render(request, 'finance/payable_form.html', {
        'form': form,
        'title': 'Create Supplier Payable',
    })


@accountant_or_owner_required
def payable_detail_view(request, payable_id):
    """Detailed inspector for a supplier payable and its disbursement payments."""
    pay = get_object_or_404(
        Payable.objects.select_related('supplier', 'linked_expense', 'created_by'),
        id=payable_id,
        is_deleted=False
    )
    payments = pay.payments.filter(is_deleted=False).select_related('account', 'linked_ledger_transaction', 'created_by').order_by('-payment_date', '-id')

    return render(request, 'finance/payable_detail.html', {
        'payable': pay,
        'payments': payments,
        'title': f"Payable: {pay.payable_code}",
    })


@accountant_or_owner_required
def supplier_payment_create_view(request, payable_id):
    """Records a supplier payout against a payable obligation."""
    pay = get_object_or_404(Payable, id=payable_id, is_deleted=False)
    if pay.status == Payable.STATUS_PAID:
        messages.info(request, f"Payable '{pay.payable_code}' is already fully settled.")
        return redirect('finance:payable_detail', payable_id=pay.id)

    if request.method == 'POST':
        form = SupplierPaymentForm(request.POST)
        if form.is_valid():
            try:
                payment = SupplierPayableService.record_payment(
                    user=request.user,
                    payable_id=pay.id,
                    amount=form.cleaned_data['amount'],
                    account=form.cleaned_data['account'],
                    payment_method=form.cleaned_data['payment_method'],
                    payment_date=form.cleaned_data['payment_date'],
                    reference_no=form.cleaned_data.get('reference_no'),
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Disbursement '{payment.payment_code}' of ₹{payment.amount} debited from {payment.account.account_name}.")
                return redirect('finance:payable_detail', payable_id=pay.id)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = SupplierPaymentForm(initial={'amount': pay.outstanding_amount})

    return render(request, 'finance/supplier_payment_form.html', {
        'form': form,
        'payable': pay,
        'title': f"Disburse Payment: {pay.payable_code}",
    })


@require_POST
@owner_required
def supplier_payment_reverse_view(request, payment_id):
    """Reverses a supplier payment (Owner only)."""
    reason = request.POST.get('reason', '').strip()
    try:
        payment = SupplierPayableService.reverse_payment(
            payment_id=payment_id,
            user=request.user,
            reason=reason,
            request=request
        )
        messages.success(request, f"Supplier payment '{payment.payment_code}' successfully reversed.")
        return redirect('finance:payable_detail', payable_id=payment.payable_id)
    except (ValidationError, Exception) as e:
        messages.error(request, f"Reversal failed: {str(e)}")
        return redirect('finance:payables')


# ============================================================================
# DAILY FINANCIAL CLOSING & RECONCILIATION (Owner & Accountant)
# ============================================================================

@accountant_or_owner_required
def daily_closing_view(request):
    """
    Daily Financial Closing and Cash / Bank / UPI Reconciliation Dashboard.
    Reconciles actual physical cash or verified bank balances against expected ledger balance.
    """
    date_str = request.GET.get('date', '').strip()
    scope = request.GET.get('scope', DailyClosing.SCOPE_CONSOLIDATED).strip()
    acc_id_str = request.GET.get('account', '').strip()

    today = timezone.now().date()
    if date_str:
        try:
            closing_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            if closing_date > today:
                closing_date = today
                messages.warning(request, "Future dates are not permitted for daily closing. Adjusted to today.")
        except ValueError:
            closing_date = today
    else:
        closing_date = today

    acc_id = int(acc_id_str) if acc_id_str.isdigit() else None

    # Calculate live reconciliation figures
    reconciliation = None
    calc_error = None
    try:
        from .services.closing_service import DailyClosingService
        reconciliation = DailyClosingService.calculate_daily_reconciliation(
            closing_date=closing_date,
            scope=scope,
            account_id=acc_id
        )
    except ValidationError as e:
        calc_error = str(e)

    # Check if a locked snapshot already exists
    existing_closing = None
    if reconciliation and reconciliation.get('target_account'):
        existing_closing = DailyClosing.objects.filter(
            closing_date=closing_date,
            scope=scope,
            account=reconciliation['target_account']
        ).first()
    elif scope == DailyClosing.SCOPE_CONSOLIDATED:
        existing_closing = DailyClosing.objects.filter(
            closing_date=closing_date,
            scope=scope,
            account=None
        ).first()

    # Historical closings list
    recent_closings = DailyClosing.objects.select_related('account', 'closed_by').order_by('-closing_date', '-id')[:20]

    # Accounts categorized for quick switching
    cash_accounts = Account.objects.filter(is_deleted=False, is_active=True, account_type__in=[Account.TYPE_CASH, Account.TYPE_PETTY_CASH])
    bank_accounts = Account.objects.filter(is_deleted=False, is_active=True, account_type__in=[Account.TYPE_BANK_SAVINGS, Account.TYPE_BANK_CURRENT])
    upi_accounts = Account.objects.filter(is_deleted=False, is_active=True, account_type=Account.TYPE_UPI_WALLET)

    form = DailyClosingForm(initial={
        'closing_date': closing_date,
        'scope': scope,
        'account': reconciliation.get('target_account') if reconciliation else None,
        'actual_closing': existing_closing.actual_closing if existing_closing else (reconciliation['expected_closing'] if reconciliation else Decimal('0.00'))
    })

    return render(request, 'finance/daily_closing.html', {
        'closing_date': closing_date,
        'scope': scope,
        'acc_id': acc_id,
        'reconciliation': reconciliation,
        'calc_error': calc_error,
        'existing_closing': existing_closing,
        'recent_closings': recent_closings,
        'cash_accounts': cash_accounts,
        'bank_accounts': bank_accounts,
        'upi_accounts': upi_accounts,
        'form': form,
        'title': 'Daily Financial Closing & Cash Reconciliation',
    })


@require_POST
@accountant_or_owner_required
def daily_closing_submit_view(request):
    """
    Submits and locks a daily financial closing snapshot.
    """
    form = DailyClosingForm(request.POST)
    if form.is_valid():
        try:
            from .services.closing_service import DailyClosingService
            closing = DailyClosingService.submit_daily_closing(
                user=request.user,
                closing_date=form.cleaned_data['closing_date'],
                scope=form.cleaned_data['scope'],
                actual_closing=form.cleaned_data['actual_closing'],
                account_id=form.cleaned_data['account'].id if form.cleaned_data.get('account') else None,
                notes=form.cleaned_data.get('notes'),
                request=request
            )
            messages.success(request, f"Daily closing for {closing.closing_date} ({closing.get_scope_display()}) successfully locked [{closing.status}].")
            return redirect(f"{request.path_info.replace('submit/', '')}?date={closing.closing_date}&scope={closing.scope}" + (f"&account={closing.account_id}" if closing.account_id else ""))
        except ValidationError as e:
            messages.error(request, f"Closing failed: {str(e)}")
    else:
        for field, errs in form.errors.items():
            messages.error(request, f"{field}: {errs[0]}")

    return redirect('finance:daily_closing')


@owner_required
def transaction_reversal_view(request, transaction_id):
    return JsonResponse({'status': 'reversed', 'id': transaction_id})
