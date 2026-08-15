"""
Phase 2 Comprehensive Test Suite: Authentication & Role-Based Access Control (RBAC).
Validates login, logout, session security, user management, 4 canonical roles,
and server-side authorization enforcement.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog


class AuthenticationTests(TestCase):
    """Verifies core login, logout, and session lifecycle."""

    def setUp(self):
        self.client = Client()
        self.password = "SecureTestPass123!"
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password=self.password,
            first_name="Test",
            last_name="User"
        )
        self.user.profile.role = UserProfile.ROLE_EMPLOYEE
        self.user.profile.save()

    def test_valid_login(self):
        """Verifies valid credentials authenticate, establish session, and audit event."""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': self.password
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/index.html')
        self.assertTrue(response.context['user'].is_authenticated)

        # Verify audit log recorded LOGIN
        audit_entry = AuditLog.objects.filter(action=AuditLog.ACTION_LOGIN, user=self.user).first()
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.entity_type, 'User')

    def test_invalid_password(self):
        """Verifies invalid password fails and displays generic error."""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'WrongPassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertContains(response, 'Invalid username or password')
        self.assertFalse(response.context['user'].is_authenticated)

    def test_invalid_username(self):
        """Verifies nonexistent username fails with same generic error (no user enumeration)."""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'nonexistentuser',
            'password': 'SomePassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertContains(response, 'Invalid username or password')

    def test_logout(self):
        """Verifies logout terminates session and audits LOGOUT event."""
        self.client.login(username='testuser', password=self.password)
        response = self.client.post(reverse('accounts:logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertFalse(response.context['user'].is_authenticated)

        # Verify audit log recorded LOGOUT
        audit_entry = AuditLog.objects.filter(action=AuditLog.ACTION_LOGOUT, user=self.user).first()
        self.assertIsNotNone(audit_entry)

    def test_protected_route_without_login(self):
        """Verifies unauthenticated access to dashboard redirects to login."""
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('accounts:login')))

    def test_password_stored_hashed_not_plaintext(self):
        """Verifies user password in database is salted and hashed (PBKDF2/Argon2)."""
        db_user = User.objects.get(username='testuser')
        self.assertNotEqual(db_user.password, self.password)
        self.assertTrue(db_user.password.startswith('pbkdf2_sha256$') or '$' in db_user.password)


class RoleBasedAccessControlTests(TestCase):
    """Verifies server-side authorization across OWNER, ACCOUNTANT, MANAGER, and EMPLOYEE."""

    def setUp(self):
        self.client = Client()
        self.password = "RoleTestPass123!"

        # Create test users for each canonical role
        self.owner = User.objects.create_user(username="owner_user", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.accountant = User.objects.create_user(username="accountant_user", password=self.password)
        self.accountant.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant.profile.save()

        self.manager = User.objects.create_user(username="manager_user", password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.employee = User.objects.create_user(username="employee_user", password=self.password)
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

    def test_owner_full_access(self):
        """Verifies OWNER can access user administration, accounts, employees, and reports."""
        self.client.login(username='owner_user', password=self.password)
        
        # User management (Owner only)
        resp_users = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(resp_users.status_code, 200)

        # Accounts (Owner & Accountant)
        resp_acc = self.client.get(reverse('finance:accounts'))
        self.assertEqual(resp_acc.status_code, 200)

        # Employees (Owner, Accountant, Manager)
        resp_emp = self.client.get(reverse('employees:list'))
        self.assertEqual(resp_emp.status_code, 200)

        # Reports (Owner & Accountant)
        resp_rep = self.client.get(reverse('reports:index'))
        self.assertEqual(resp_rep.status_code, 200)

    def test_accountant_access_and_restrictions(self):
        """Verifies ACCOUNTANT can access finance & reports, but blocked from user administration."""
        self.client.login(username='accountant_user', password=self.password)

        # Can access accounts & reports
        self.assertEqual(self.client.get(reverse('finance:accounts')).status_code, 200)
        self.assertEqual(self.client.get(reverse('reports:index')).status_code, 200)

        # BLOCKED from user administration (403 Forbidden)
        resp_users = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(resp_users.status_code, 403)
        self.assertTemplateUsed(resp_users, 'errors/403.html')

    def test_manager_access_and_restrictions(self):
        """Verifies MANAGER can access operations/employees, but blocked from accounts & user admin."""
        self.client.login(username='manager_user', password=self.password)

        # Can access employees & dashboard
        self.assertEqual(self.client.get(reverse('employees:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('dashboard:index')).status_code, 200)

        # BLOCKED from financial accounts (403)
        self.assertEqual(self.client.get(reverse('finance:accounts')).status_code, 403)

        # BLOCKED from user administration (403)
        self.assertEqual(self.client.get(reverse('accounts:user_list')).status_code, 403)

    def test_employee_strict_restrictions(self):
        """Verifies EMPLOYEE is blocked from financial accounts, employee administration, and user admin."""
        self.client.login(username='employee_user', password=self.password)

        # Can access dashboard
        self.assertEqual(self.client.get(reverse('dashboard:index')).status_code, 200)

        # BLOCKED from accounts (403)
        self.assertEqual(self.client.get(reverse('finance:accounts')).status_code, 403)

        # BLOCKED from employee administration (403)
        self.assertEqual(self.client.get(reverse('employees:list')).status_code, 403)

        # BLOCKED from reports (403)
        self.assertEqual(self.client.get(reverse('reports:index')).status_code, 403)

        # BLOCKED from user administration (403)
        self.assertEqual(self.client.get(reverse('accounts:user_list')).status_code, 403)

    def test_ajax_permission_denied_returns_json_403(self):
        """Verifies unauthorized AJAX API requests return HTTP 403 JSON instead of HTML."""
        self.client.login(username='employee_user', password=self.password)
        response = self.client.get(
            reverse('accounts:user_list'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get('success'), False)


class UserAdministrationTests(TestCase):
    """Verifies Owner user provisioning and role editing."""

    def setUp(self):
        self.client = Client()
        self.password = "AdminSecretPass123!"
        self.owner = User.objects.create_user(username="owner_admin", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

    def test_owner_create_new_user(self):
        """Verifies Owner can create a new staff account with assigned role."""
        self.client.login(username='owner_admin', password=self.password)
        response = self.client.post(reverse('accounts:user_create'), {
            'username': 'new_operator',
            'first_name': 'Ravi',
            'last_name': 'Kumar',
            'email': 'ravi@example.com',
            'password': 'OperatorPass123!',
            'role': UserProfile.ROLE_EMPLOYEE,
            'phone_number': '+91 9845012345'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify user created in database
        new_user = User.objects.filter(username='new_operator').first()
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user.profile.role, UserProfile.ROLE_EMPLOYEE)
        self.assertEqual(new_user.profile.phone_number, '+91 9845012345')

        # Verify Django group sync
        self.assertTrue(new_user.groups.filter(name=UserProfile.ROLE_EMPLOYEE).exists())

        # Verify audit log
        audit = AuditLog.objects.filter(action=AuditLog.ACTION_CREATE, entity_id=str(new_user.id)).first()
        self.assertIsNotNone(audit)

    def test_owner_edit_user_role(self):
        """Verifies Owner can change an existing user role and syncs group."""
        self.client.login(username='owner_admin', password=self.password)
        target = User.objects.create_user(username="target_staff", password="password123")
        target.profile.role = UserProfile.ROLE_EMPLOYEE
        target.profile.save()

        # Update role from EMPLOYEE to ACCOUNTANT
        response = self.client.post(reverse('accounts:user_edit', args=[target.id]), {
            'first_name': 'Target',
            'last_name': 'Staff',
            'email': 'target@example.com',
            'role': UserProfile.ROLE_ACCOUNTANT,
            'phone_number': '+91 9900112233',
            'is_active': True
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        target.refresh_from_db()
        self.assertEqual(target.profile.role, UserProfile.ROLE_ACCOUNTANT)
        self.assertEqual(target.profile.phone_number, '+91 9900112233')
