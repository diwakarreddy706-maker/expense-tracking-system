from io import StringIO

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.expenses.models import Expense, ExpenseCategory
from apps.finance.models import Account, Customer
from apps.machines.models import Machine, MachineType


class CleanupBusinessDataCommandTests(TestCase):
    def setUp(self):
        self.owner_pw = "OwnerSecret9663!"
        self.owner = User.objects.create_user(
            username="Doddanna Gowad",
            password=self.owner_pw,
            first_name="Doddanna",
            last_name="Gowad",
            is_staff=True,
            is_superuser=True,
        )
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.extra_user = User.objects.create_user(
            username="old_demo_staff",
            password="TempPass123!",
        )

        self.mtype = MachineType.objects.create(code="TRACTOR", name="Tractor")
        self.machine = Machine.objects.create(
            machine_code="T-001",
            name="Test Tractor",
            machine_type=self.mtype,
        )
        self.cat = ExpenseCategory.objects.create(code="CAT-FUEL", name="Fuel")
        self.account = Account.objects.create(
            account_name="Cash",
            account_type=Account.TYPE_CASH,
            opening_balance=100,
        )
        self.customer = Customer.objects.create(customer_code="CUST-001", name="Farmer A")
        self.expense = Expense.objects.create(
            expense_code="EXP-001",
            amount=500,
            category=self.cat,
            account=self.account,
            created_by=self.extra_user,
        )
        AuditLog.objects.create(user=self.extra_user, action=AuditLog.ACTION_CREATE, entity_type="Expense")

    def test_requires_yes_flag(self):
        with self.assertRaises(CommandError):
            call_command("cleanup_business_data")
        self.assertEqual(Machine.objects.count(), 1)
        self.assertEqual(User.objects.count(), 2)

    def test_cleans_data_and_preserves_owner_username_and_password(self):
        original_hash = self.owner.password
        out = StringIO()

        call_command("cleanup_business_data", "--yes", stdout=out)

        self.assertEqual(Machine.objects.count(), 0)
        self.assertEqual(Expense.objects.count(), 0)
        self.assertEqual(Account.objects.count(), 0)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(AuditLog.objects.count(), 0)
        self.assertEqual(User.objects.count(), 1)

        self.assertEqual(MachineType.objects.count(), 1)
        self.assertEqual(ExpenseCategory.objects.count(), 1)

        kept = User.objects.get(id=self.owner.id)
        self.assertEqual(kept.username, "Doddanna Gowad")
        self.assertEqual(kept.password, original_hash)
        self.assertIsNotNone(authenticate(username="Doddanna Gowad", password=self.owner_pw))

    def test_cleanup_view_rbac_and_validation(self):
        self.client.login(username="old_demo_staff", password="TempPass123!")
        res = self.client.post(reverse("accounts:cleanup_business_data"), {
            "confirm_phrase": "CLEAR DATA",
            "password": "TempPass123!",
        })
        self.assertEqual(res.status_code, 403)
        self.assertEqual(Machine.objects.count(), 1)

        self.client.login(username="Doddanna Gowad", password=self.owner_pw)
        bad_phrase = self.client.post(reverse("accounts:cleanup_business_data"), {
            "confirm_phrase": "WRONG",
            "password": self.owner_pw,
        })
        self.assertEqual(bad_phrase.status_code, 302)
        self.assertEqual(Machine.objects.count(), 1)

        bad_pw = self.client.post(reverse("accounts:cleanup_business_data"), {
            "confirm_phrase": "CLEAR DATA",
            "password": "WrongPassword",
        })
        self.assertEqual(bad_pw.status_code, 302)
        self.assertEqual(Machine.objects.count(), 1)

        ok = self.client.post(reverse("accounts:cleanup_business_data"), {
            "confirm_phrase": "CLEAR DATA",
            "password": self.owner_pw,
        }, follow=True)
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(Machine.objects.count(), 0)
        self.assertEqual(User.objects.count(), 1)
        self.assertIsNotNone(authenticate(username="Doddanna Gowad", password=self.owner_pw))
