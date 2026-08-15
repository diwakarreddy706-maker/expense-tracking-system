from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q, Sum
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.decorators import (
    accountant_or_owner_required,
    manager_or_above_required,
    owner_required
)
from .models import Budget, BudgetItem
from .forms import BudgetForm, BudgetItemForm
from .services.budget_service import BudgetService
from apps.expenses.models import ExpenseCategory
from apps.machines.models import Machine


@manager_or_above_required
def budget_list_view(request):
    """
    Lists operational budgets with multi-parameter filtering,
    aggregate metrics, and progress bars.
    """
    now = timezone.now()
    year_str = request.GET.get('year', str(now.year)).strip()
    month_str = request.GET.get('month', str(now.month)).strip()
    segment = request.GET.get('segment', '').strip()
    status = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    year = int(year_str) if year_str.isdigit() else now.year
    month = int(month_str) if month_str.isdigit() else now.month

    budgets_qs = Budget.objects.filter(is_deleted=False).prefetch_related('items__category', 'items__machine')

    if query:
        budgets_qs = budgets_qs.filter(Q(title__icontains=query) | Q(notes__icontains=query))
    if year_str:
        budgets_qs = budgets_qs.filter(period_year=year)
    if month_str:
        budgets_qs = budgets_qs.filter(period_month=month)
    if segment:
        budgets_qs = budgets_qs.filter(business_segment=segment)
    if status:
        budgets_qs = budgets_qs.filter(status=status)

    # Calculate live budget vs actual metrics for each budget
    budget_cards = []
    for b in budgets_qs:
        calc = BudgetService.calculate_budget_vs_actual(b)
        budget_cards.append(calc)

    summary_metrics = BudgetService.get_budget_dashboard_summary(month, year)

    return render(request, 'budgets/budget_list.html', {
        'budget_cards': budget_cards,
        'summary_metrics': summary_metrics,
        'selected_year': year,
        'selected_month': month,
        'selected_segment': segment,
        'selected_status': status,
        'query': query,
        'segment_choices': Budget.SEGMENT_CHOICES,
        'status_choices': Budget.STATUS_CHOICES,
        'title': 'Budgets & Financial Controls',
    })


@accountant_or_owner_required
def budget_create_view(request):
    """Creates a new operational budget with allocations."""
    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            try:
                budget = BudgetService.create_budget(
                    user=request.user,
                    title=form.cleaned_data['title'],
                    period_month=int(form.cleaned_data['period_month']),
                    period_year=form.cleaned_data['period_year'],
                    business_segment=form.cleaned_data['business_segment'],
                    notes=form.cleaned_data.get('notes'),
                    status=form.cleaned_data['status'],
                    request=request
                )
                messages.success(request, f"Budget '{budget.title}' successfully created.")
                return redirect('budgets:detail', budget_id=budget.id)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        now = timezone.now()
        form = BudgetForm(initial={
            'period_month': now.month,
            'period_year': now.year,
            'status': Budget.STATUS_ACTIVE
        })

    return render(request, 'budgets/budget_form.html', {
        'form': form,
        'title': 'Create Operational Budget',
    })


@manager_or_above_required
def budget_detail_view(request, budget_id):
    """Detailed inspector for a budget showing allocated items vs actuals."""
    budget = get_object_or_404(
        Budget.objects.select_related('created_by'),
        id=budget_id,
        is_deleted=False
    )

    calc = BudgetService.calculate_budget_vs_actual(budget)
    item_form = BudgetItemForm()

    return render(request, 'budgets/budget_detail.html', {
        'budget': budget,
        'calc': calc,
        'item_form': item_form,
        'title': f"Budget: {budget.title}",
    })


@accountant_or_owner_required
def budget_edit_view(request, budget_id):
    """Edits budget metadata."""
    budget = get_object_or_404(Budget, id=budget_id, is_deleted=False)

    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget)
        if form.is_valid():
            try:
                BudgetService.update_budget(
                    budget_id=budget.id,
                    user=request.user,
                    title=form.cleaned_data['title'],
                    status=form.cleaned_data['status'],
                    notes=form.cleaned_data.get('notes'),
                    request=request
                )
                messages.success(request, f"Budget '{budget.title}' updated.")
                return redirect('budgets:detail', budget_id=budget.id)
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = BudgetForm(instance=budget)

    return render(request, 'budgets/budget_form.html', {
        'form': form,
        'budget': budget,
        'title': f"Edit Budget: {budget.title}",
    })


@require_POST
@accountant_or_owner_required
def budget_item_add_view(request, budget_id):
    """Adds a category/machine budget allocation item to a budget."""
    budget = get_object_or_404(Budget, id=budget_id, is_deleted=False)
    form = BudgetItemForm(request.POST)

    if form.is_valid():
        category = form.cleaned_data['category']
        machine = form.cleaned_data.get('machine')
        allocated = form.cleaned_data['allocated_amount']
        notes = form.cleaned_data.get('notes')

        # Check existing item
        existing = BudgetItem.objects.filter(budget=budget, category=category, machine=machine).first()
        if existing:
            existing.allocated_amount = allocated
            existing.notes = notes
            existing.save()
            messages.success(request, f"Allocation for '{category.name}' updated to ₹{allocated}.")
        else:
            BudgetItem.objects.create(
                budget=budget,
                category=category,
                machine=machine,
                allocated_amount=allocated,
                notes=notes
            )
            messages.success(request, f"Allocation for '{category.name}' added (₹{allocated}).")
    else:
        for field, errs in form.errors.items():
            messages.error(request, f"{field}: {errs[0]}")

    return redirect('budgets:detail', budget_id=budget.id)


@require_POST
@accountant_or_owner_required
def budget_item_delete_view(request, item_id):
    """Deletes a budget item."""
    item = get_object_or_404(BudgetItem, id=item_id)
    budget_id = item.budget_id
    cat_name = item.category.name
    item.delete()
    messages.info(request, f"Allocation item '{cat_name}' removed.")
    return redirect('budgets:detail', budget_id=budget_id)


@manager_or_above_required
def budget_vs_actual_api_view(request, budget_id):
    """API endpoint for JSON representation of budget vs actual data."""
    budget = get_object_or_404(Budget, id=budget_id, is_deleted=False)
    calc = BudgetService.calculate_budget_vs_actual(budget)

    data = {
        'budget_id': budget.id,
        'title': budget.title,
        'period': f"{budget.period_month:02d}/{budget.period_year}",
        'segment': budget.business_segment,
        'total_allocated': str(calc['total_allocated']),
        'total_actual': str(calc['total_actual']),
        'total_remaining': str(calc['total_remaining']),
        'overall_utilization_pct': str(calc['overall_utilization']),
        'overall_status': calc['overall_status'],
        'items': [
            {
                'category': it['category'].name,
                'machine': it['machine'].machine_code if it['machine'] else None,
                'allocated_amount': str(it['allocated_amount']),
                'actual_amount': str(it['actual_amount']),
                'remaining_amount': str(it['remaining_amount']),
                'utilization_pct': str(it['utilization_pct']),
                'status': it['status'],
            }
            for it in calc['items']
        ]
    }
    return JsonResponse(data)
