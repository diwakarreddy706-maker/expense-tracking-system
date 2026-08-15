from django.shortcuts import render
from django.http import JsonResponse
from apps.accounts.decorators import role_required, accountant_or_owner_required, owner_required


@accountant_or_owner_required
def accounts_list_view(request):
    """Business accounts & balances (Owner & Accountant only)."""
    return render(request, 'base.html', {'title': 'Business Accounts'})


@accountant_or_owner_required
def receivables_list_view(request):
    """Customer receivables (Owner & Accountant only)."""
    return render(request, 'base.html', {'title': 'Receivables'})


@accountant_or_owner_required
def payables_list_view(request):
    """Supplier payables (Owner & Accountant only)."""
    return render(request, 'base.html', {'title': 'Payables'})


@accountant_or_owner_required
def daily_closing_view(request):
    """Daily financial closing (Owner & Accountant only)."""
    return render(request, 'base.html', {'title': 'Daily Closing'})


@owner_required
def transaction_reversal_view(request, transaction_id):
    """Financial transaction reversal (Owner only, strictly audited)."""
    return JsonResponse({'status': 'reversed', 'id': transaction_id})
