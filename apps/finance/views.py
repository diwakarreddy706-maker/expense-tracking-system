from django.shortcuts import render
from apps.accounts.decorators import role_required, accountant_or_owner_required, login_required


@accountant_or_owner_required
def accounts_list_view(request):
    """Placeholder view for accounts & balances (Owner & Accountant only)."""
    return render(request, 'base.html', {'title': 'Business Accounts'})


@accountant_or_owner_required
def receivables_list_view(request):
    """Placeholder view for receivables (Owner & Accountant only)."""
    return render(request, 'base.html', {'title': 'Receivables'})


@accountant_or_owner_required
def payables_list_view(request):
    """Placeholder view for payables (Owner & Accountant only)."""
    return render(request, 'base.html', {'title': 'Payables'})


@login_required
def daily_closing_view(request):
    """Placeholder view for daily closing."""
    return render(request, 'base.html', {'title': 'Daily Closing'})
