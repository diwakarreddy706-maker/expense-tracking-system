import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError

from apps.accounts.decorators import role_required, accountant_or_owner_required, owner_required
from apps.finance.models import Account, Supplier, AccountTransaction
from apps.machines.models import Machine
from apps.employees.models import Employee
from .models import Expense, ExpenseCategory
from .forms import ExpenseForm, QuickExpenseForm, ExpenseCategoryForm
from .services.expense_service import ExpenseService


# ============================================================================
# EXPENSE VIEWS & LISTING
# ============================================================================

@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER', 'EMPLOYEE'])
def expense_list_view(request):
    """
    Lists operational business expenses with rich multi-parameter filtering.
    """
    query = request.GET.get('q', '').strip()
    cat_id = request.GET.get('category', '').strip()
    acc_id = request.GET.get('account', '').strip()
    method = request.GET.get('method', '').strip()
    mch_id = request.GET.get('machine', '').strip()
    segment = request.GET.get('segment', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    expenses = Expense.objects.filter(is_deleted=False).select_related(
        'category', 'account', 'machine', 'employee', 'created_by'
    )

    if query:
        expenses = expenses.filter(
            Q(expense_code__icontains=query) |
            Q(description__icontains=query) |
            Q(reference_no__icontains=query) |
            Q(category__name__icontains=query)
        )
    if cat_id:
        expenses = expenses.filter(category_id=cat_id)
    if acc_id:
        expenses = expenses.filter(account_id=acc_id)
    if method:
        expenses = expenses.filter(payment_method=method)
    if mch_id:
        expenses = expenses.filter(machine_id=mch_id)
    if segment:
        expenses = expenses.filter(business_segment=segment)
    if start_date:
        expenses = expenses.filter(expense_date__gte=start_date)
    if end_date:
        expenses = expenses.filter(expense_date__lte=end_date)

    return render(request, 'expenses/expense_list.html', {
        'expenses': expenses,
        'categories': ExpenseCategory.objects.filter(is_deleted=False, is_active=True),
        'accounts': Account.objects.filter(is_deleted=False, is_active=True),
        'machines': Machine.objects.filter(is_deleted=False),
        'query': query,
        'cat_id': cat_id,
        'acc_id': acc_id,
        'method': method,
        'mch_id': mch_id,
        'segment': segment,
        'start_date': start_date,
        'end_date': end_date,
        'title': 'Operational Expenses',
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER', 'EMPLOYEE'])
def expense_create_view(request):
    """
    Standard full expense entry workflow.
    Delegates atomic financial processing to ExpenseService.
    """
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            try:
                expense, ledger_tx = ExpenseService.create_expense(
                    user=request.user,
                    amount=form.cleaned_data['amount'],
                    category=form.cleaned_data['category'],
                    account=form.cleaned_data.get('account'),
                    payment_method=form.cleaned_data['payment_method'],
                    business_segment=form.cleaned_data['business_segment'],
                    expense_date=form.cleaned_data['expense_date'],
                    machine=form.cleaned_data.get('machine'),
                    employee=form.cleaned_data.get('employee'),
                    supplier=form.cleaned_data.get('supplier'),
                    reference_no=form.cleaned_data.get('reference_no'),
                    description=form.cleaned_data.get('description'),
                    is_quick_expense=False,
                    request=request
                )
                messages.success(request, f"Expense '{expense.expense_code}' (₹{expense.amount}) successfully posted to ledger.")
                return redirect('expenses:list')
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = ExpenseForm()

    return render(request, 'expenses/expense_form.html', {
        'form': form,
        'title': 'Record New Expense',
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER', 'EMPLOYEE'])
def expense_detail_view(request, expense_id):
    """
    Shows comprehensive audit and financial details for an expense record.
    """
    expense = get_object_or_404(
        Expense.objects.select_related('category', 'account', 'machine', 'employee', 'supplier', 'created_by'),
        id=expense_id,
        is_deleted=False
    )
    
    # Retrieve linked ledger transaction if applicable
    ledger_tx = AccountTransaction.objects.filter(
        reference_type='Expense',
        reference_id=expense.id,
        is_deleted=False
    ).first()

    return render(request, 'expenses/expense_detail.html', {
        'expense': expense,
        'ledger_tx': ledger_tx,
        'title': f"Expense Detail: {expense.expense_code}",
    })


@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER', 'EMPLOYEE'])
def expense_options_api_view(request):
    """Returns active categories, accounts, and machines for quick entry dropdowns."""
    cats = list(ExpenseCategory.objects.filter(is_deleted=False, is_active=True).values('id', 'name'))
    accs = list(Account.objects.filter(is_deleted=False, is_active=True).values('id', 'account_name', 'account_type'))
    mchs = list(Machine.objects.filter(is_deleted=False).exclude(status=Machine.STATUS_DECOMMISSIONED).values('id', 'name', 'machine_code'))
    return JsonResponse({
        'categories': cats,
        'accounts': accs,
        'machines': mchs
    })


@require_POST
@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER', 'EMPLOYEE'])
def expense_quick_api_view(request):
    """
    Quick Expense API for rapid mobile field entry (< 20 seconds).
    Accepts JSON or Form-Data and executes via authoritative ExpenseService.
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        amount = Decimal(str(data.get('amount', '0.00')))
        category_id = data.get('category_id') or data.get('category')
        account_id = data.get('account_id') or data.get('account')
        machine_id = data.get('machine_id') or data.get('machine')
        method = data.get('payment_method', Expense.METHOD_CASH)
        description = data.get('description', '')

        category = get_object_or_404(ExpenseCategory, id=category_id, is_deleted=False, is_active=True)
        account = get_object_or_404(Account, id=account_id, is_deleted=False, is_active=True) if account_id else None
        machine = Machine.objects.filter(id=machine_id, is_deleted=False).first() if machine_id else None

        expense, ledger_tx = ExpenseService.create_expense(
            user=request.user,
            amount=amount,
            category=category,
            account=account,
            payment_method=method,
            machine=machine,
            description=description,
            is_quick_expense=True,
            request=request
        )

        return JsonResponse({
            'success': True,
            'expense_id': expense.id,
            'expense_code': expense.expense_code,
            'amount': str(expense.amount),
            'ledger_transaction_id': ledger_tx.id if ledger_tx else None,
            'account_balance': str(account.current_balance) if account else None,
            'message': f"Quick expense '{expense.expense_code}' recorded successfully."
        })
    except (ValidationError, Exception) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_POST
@owner_required
def expense_reverse_view(request, expense_id):
    """
    Financial Reversal endpoint (Owner only).
    Enforces Rule 10: History is preserved; creates a compensatory REVERSAL ledger entry.
    """
    reason = request.POST.get('reason', '').strip()
    try:
        expense, reversal_tx = ExpenseService.reverse_expense(
            expense_id=expense_id,
            user=request.user,
            reason=reason,
            request=request
        )
        messages.success(request, f"Expense '{expense.expense_code}' reversed. Reversal ledger entry #{reversal_tx.id} recorded.")
    except (ValidationError, Exception) as e:
        messages.error(request, f"Reversal failed: {str(e)}")

    return redirect('expenses:detail', expense_id=expense_id)


# ============================================================================
# CATEGORIES MANAGEMENT
# ============================================================================

@accountant_or_owner_required
def category_list_view(request):
    """Lists expense categories with active filter and search."""
    query = request.GET.get('q', '').strip()
    categories = ExpenseCategory.objects.filter(is_deleted=False).select_related('parent')
    if query:
        categories = categories.filter(Q(name__icontains=query) | Q(code__icontains=query))

    return render(request, 'expenses/categories_list.html', {
        'categories': categories,
        'query': query,
        'title': 'Expense Categories',
    })


@accountant_or_owner_required
def category_create_view(request):
    """Creates a new expense category."""
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' ({cat.code}) created.")
            return redirect('expenses:categories')
    else:
        form = ExpenseCategoryForm()

    return render(request, 'expenses/category_form.html', {
        'form': form,
        'title': 'Add Expense Category',
    })


@accountant_or_owner_required
def category_edit_view(request, category_id):
    """Edits an existing expense category."""
    category = get_object_or_404(ExpenseCategory, id=category_id, is_deleted=False)
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=category)
        if form.is_valid():
            updated = form.save()
            messages.success(request, f"Category '{updated.name}' updated.")
            return redirect('expenses:categories')
    else:
        form = ExpenseCategoryForm(instance=category)

    return render(request, 'expenses/category_form.html', {
        'form': form,
        'category': category,
        'title': f"Edit Category: {category.name}",
    })


@accountant_or_owner_required
def category_toggle_view(request, category_id):
    """Toggles active status of expense category."""
    category = get_object_or_404(ExpenseCategory, id=category_id, is_deleted=False)
    category.is_active = not category.is_active
    category.save()
    status_str = "activated" if category.is_active else "deactivated"
    messages.info(request, f"Category '{category.name}' {status_str}.")
    return redirect('expenses:categories')
