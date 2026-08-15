from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q
from apps.accounts.decorators import role_required, accountant_or_owner_required, owner_required
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog
from .models import Account, Customer, Supplier
from .forms import AccountForm, CustomerForm, SupplierForm


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
# FINANCIAL PLACEHOLDERS (To be fully implemented in Phase 7-10)
# ============================================================================

@accountant_or_owner_required
def receivables_list_view(request):
    return render(request, 'base.html', {'title': 'Receivables'})


@accountant_or_owner_required
def payables_list_view(request):
    return render(request, 'base.html', {'title': 'Payables'})


@accountant_or_owner_required
def daily_closing_view(request):
    return render(request, 'base.html', {'title': 'Daily Closing'})


@owner_required
def transaction_reversal_view(request, transaction_id):
    return JsonResponse({'status': 'reversed', 'id': transaction_id})
