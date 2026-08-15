from django.http import JsonResponse
from django.shortcuts import render


def login_view(request):
    """Placeholder view for Phase 2 authentication."""
    return render(request, 'base.html', {'title': 'Login'})


def profile_view(request):
    """Placeholder view for Phase 2 user profile."""
    return render(request, 'base.html', {'title': 'Profile'})
