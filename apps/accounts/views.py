from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .forms import LoginForm, UserProfileUpdateForm, UserCreateForm, UserEditForm
from .decorators import role_required, owner_required
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog


def login_view(request):
    """
    Renders login interface and authenticates user credentials.
    Audits successful and failed login attempts.
    """
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            log_audit_event(user, AuditLog.ACTION_LOGIN, 'User', user.id, request=request)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            
            next_url = request.GET.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('dashboard:index')
        else:
            # Generic message to avoid username enumeration
            messages.error(request, "Invalid username or password. Please check your credentials.")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'title': 'Sign In'})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    """
    Terminates authenticated session, audits logout event, and redirects to login.
    """
    if request.user.is_authenticated:
        user = request.user
        log_audit_event(user, AuditLog.ACTION_LOGOUT, 'User', user.id, request=request)
        auth_logout(request)
        messages.info(request, "You have been logged out successfully.")
    return redirect('accounts:login')


@login_required
def profile_view(request):
    """
    Allows authenticated users to view profile details and update password.
    """
    profile = request.user.profile
    profile_form = UserProfileUpdateForm(instance=profile)
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = UserProfileUpdateForm(request.POST, instance=profile)
            if profile_form.is_valid():
                profile_form.save()
                log_audit_event(request.user, AuditLog.ACTION_UPDATE, 'UserProfile', profile.id, request=request)
                messages.success(request, "Profile updated successfully.")
                return redirect('accounts:profile')
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                log_audit_event(user, AuditLog.ACTION_UPDATE, 'UserPassword', user.id, request=request)
                messages.success(request, "Password changed successfully.")
                return redirect('accounts:profile')
            else:
                messages.error(request, "Please correct the password errors below.")

    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'title': 'User Profile & Security',
    })


@owner_required
def user_list_view(request):
    """
    Owner-only view for system user administration.
    """
    users = User.objects.select_related('profile').order_by('-date_joined')
    return render(request, 'accounts/user_list.html', {
        'users': users,
        'title': 'User Management & Roles',
    })


@owner_required
def user_create_view(request):
    """
    Owner-only view to provision new staff/operator accounts.
    """
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            log_audit_event(
                request.user,
                AuditLog.ACTION_CREATE,
                'User',
                new_user.id,
                changes={'username': new_user.username, 'role': new_user.profile.role},
                request=request
            )
            messages.success(request, f"User '{new_user.username}' created successfully with role {new_user.profile.get_role_display()}.")
            return redirect('accounts:user_list')
    else:
        form = UserCreateForm()

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Create New User',
    })


@owner_required
def user_edit_view(request, user_id):
    """
    Owner-only view to update user role and active status.
    """
    target_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=target_user)
        if form.is_valid():
            old_role = target_user.profile.role
            old_active = target_user.is_active
            updated_user = form.save()
            
            changes = {}
            if old_role != updated_user.profile.role:
                changes['role'] = {'old': old_role, 'new': updated_user.profile.role}
            if old_active != updated_user.is_active:
                changes['is_active'] = {'old': old_active, 'new': updated_user.is_active}

            log_audit_event(
                request.user,
                AuditLog.ACTION_UPDATE,
                'User',
                updated_user.id,
                changes=changes,
                request=request
            )
            messages.success(request, f"User '{updated_user.username}' updated successfully.")
            return redirect('accounts:user_list')
    else:
        form = UserEditForm(instance=target_user)

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'target_user': target_user,
        'title': f"Edit User: {target_user.username}",
    })
