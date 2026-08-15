from django.shortcuts import render


def report_index_view(request):
    """Placeholder view for Phase 12 reports."""
    return render(request, 'base.html', {'title': 'Financial Reports'})
