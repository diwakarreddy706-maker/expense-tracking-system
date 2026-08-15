from django.shortcuts import render
from apps.accounts.decorators import accountant_or_owner_required


@accountant_or_owner_required
def report_index_view(request):
    """Placeholder view for Phase 12 reports (Owner & Accountant only)."""
    return render(request, 'base.html', {'title': 'Financial Reports'})
