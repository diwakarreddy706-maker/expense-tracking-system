from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from apps.accounts.decorators import role_required, accountant_or_owner_required
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog
from .models import ExpenseCategory
from .forms import ExpenseCategoryForm


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
            log_audit_event(
                request.user,
                AuditLog.ACTION_CREATE,
                'ExpenseCategory',
                cat.id,
                changes={'name': cat.name, 'code': cat.code},
                request=request
            )
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
            log_audit_event(
                request.user,
                AuditLog.ACTION_UPDATE,
                'ExpenseCategory',
                updated.id,
                changes={'name': updated.name},
                request=request
            )
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
    log_audit_event(
        request.user,
        AuditLog.ACTION_UPDATE,
        'ExpenseCategory',
        category.id,
        changes={'is_active': category.is_active},
        request=request
    )
    status_str = "activated" if category.is_active else "deactivated"
    messages.info(request, f"Category '{category.name}' {status_str}.")
    return redirect('expenses:categories')


# ============================================================================
# EXPENSES PLACEHOLDER (Phase 4)
# ============================================================================

@role_required(['OWNER', 'ACCOUNTANT', 'MANAGER', 'EMPLOYEE'])
def expense_list_view(request):
    """Placeholder view for expenses list."""
    return render(request, 'base.html', {'title': 'Expenses'})
