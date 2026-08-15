from django.shortcuts import render


def machine_list_view(request):
    """Placeholder view for Phase 3/machines."""
    return render(request, 'base.html', {'title': 'Machines & Equipment'})
