from django.shortcuts import render


def fuel_list_view(request):
    """Placeholder view for Phase 5 fuel & lubricants."""
    return render(request, 'base.html', {'title': 'Fuel & Lubricants'})
