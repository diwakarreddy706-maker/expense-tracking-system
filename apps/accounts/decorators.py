from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpResponseForbidden


def role_required(allowed_roles):
    """
    Decorator for views that checks whether a user has one of the allowed roles.
    Enforces server-side authorization.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                    return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=401)
                return redirect('accounts:login')

            user_role = getattr(request.user, 'profile', None)
            role_name = user_role.role if user_role else 'EMPLOYEE'

            # Superusers always have full OWNER privileges
            if request.user.is_superuser or role_name in allowed_roles:
                return view_func(request, *args, **kwargs)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                return JsonResponse({'success': False, 'error': 'Permission denied. Insufficient role permissions.'}, status=403)

            return render(request, 'errors/403.html', {'title': '403 Forbidden'}, status=403)

        return _wrapped_view

    return decorator


def owner_required(view_func):
    return role_required(['OWNER'])(view_func)


def accountant_or_owner_required(view_func):
    return role_required(['OWNER', 'ACCOUNTANT'])(view_func)


def manager_or_above_required(view_func):
    return role_required(['OWNER', 'ACCOUNTANT', 'MANAGER'])(view_func)


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    CBV mixin that enforces role-based access control.
    """
    allowed_roles = []

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        profile = getattr(self.request.user, 'profile', None)
        if not profile:
            return False
        return profile.role in self.allowed_roles

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('accounts:login')
        return render(self.request, 'errors/403.html', {'title': '403 Forbidden'}, status=403)
