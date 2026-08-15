from django.shortcuts import render


def accounts_list_view(request):
    """Placeholder view for accounts & balances."""
    return render(request, 'base.html', {'title': 'Business Accounts'})


def receivables_list_view(request):
    """Placeholder view for receivables."""
    return render(request, 'base.html', {'title': 'Receivables'})


def payables_list_view(request):
    """Placeholder view for payables."""
    return render(request, 'base.html', {'title': 'Payables'})


def daily_closing_view(request):
    """Placeholder view for daily closing."""
    return render(request, 'base.html', {'title': 'Daily Closing'})
