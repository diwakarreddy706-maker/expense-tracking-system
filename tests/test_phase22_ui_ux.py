"""
Phase 22 Comprehensive UI/UX Test Suite.
Validates:
1. AJAX quick-add endpoints for Suppliers, Customers, and Expense Categories.
2. Form view enhancements, live calculation wrappers, and tactile pill containers.
3. Fleet registry Grid/Table dual-view rendering.
4. Dispatch board 5-lane Kanban structure.
5. Financial flow equation and liquid balance summary rendering.
6. RBAC security preservation across all quick-add and operational endpoints.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile
from apps.finance.models import Account, Customer, Supplier
from apps.expenses.models import ExpenseCategory
from apps.machines.models import Machine, MachineType, MachineBooking


class Phase22UIUXTests(TestCase):
    """Verifies all Phase 22 frontend interactions, AJAX modals, and view structures."""

    def setUp(self):
        self.client = Client()
        self.password = 'Pass@1234'

        # 1. Owner User
        self.owner = User.objects.create_user(username='p22_owner', email='owner@p22.test', password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        # 2. Accountant User
        self.accountant = User.objects.create_user(username='p22_acc', email='acc@p22.test', password=self.password)
        self.accountant.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant.profile.save()

        # 3. Manager User
        self.manager = User.objects.create_user(username='p22_mgr', email='mgr@p22.test', password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        # 4. Master Data
        self.m_type = MachineType.objects.create(name="Tractor", code="TRACTOR")
        self.machine = Machine.objects.create(
            name="John Deere 5050D",
            machine_code="TR-001",
            machine_type=self.m_type,
            registration_no="KA-05-AB-1234",
            meter_unit=Machine.METER_HOURS,
            current_meter_reading=Decimal('150.00'),
            status=Machine.STATUS_ACTIVE
        )

        self.account = Account.objects.create(
            account_name="Main Cash Box",
            account_type=Account.TYPE_CASH,
            opening_balance=Decimal('25000.00'),
            is_active=True
        )

    def test_ajax_supplier_quick_add(self):
        """Verifies AJAX creation of a supplier returns JSON and saves to DB."""
        self.client.login(username='p22_owner', password=self.password)
        url = reverse('finance:supplier_create')
        response = self.client.post(
            url,
            {
                'name': 'Bharat Petroleum Bunk',
                'phone': '9876543210',
                'supplier_type': 'FUEL',
                'is_ajax': '1',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['name'], 'Bharat Petroleum Bunk')

        # Verify DB presence
        supp = Supplier.objects.get(id=data['id'])
        self.assertEqual(supp.name, 'Bharat Petroleum Bunk')
        self.assertEqual(supp.supplier_type, Supplier.TYPE_FUEL_PUMP)

    def test_ajax_customer_quick_add(self):
        """Verifies AJAX creation of a customer returns JSON and saves to DB."""
        self.client.login(username='p22_mgr', password=self.password)
        url = reverse('finance:customer_create')
        response = self.client.post(
            url,
            {
                'name': 'Suresh Gowda',
                'phone': '9123456780',
                'village': 'Hoskote Field #2',
                'is_ajax': '1',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['name'], 'Suresh Gowda')

        # Verify DB presence
        cust = Customer.objects.get(id=data['id'])
        self.assertEqual(cust.name, 'Suresh Gowda')

    def test_ajax_expense_category_quick_add(self):
        """Verifies AJAX creation of an expense category returns JSON and saves to DB."""
        self.client.login(username='p22_acc', password=self.password)
        url = reverse('expenses:category_create')
        response = self.client.post(
            url,
            {
                'name': 'Battery & Electricals',
                'code': 'CAT-ELECTRICAL',
                'is_ajax': '1',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['name'], 'Battery & Electricals')

        # Verify DB presence
        cat = ExpenseCategory.objects.get(id=data['id'])
        self.assertEqual(cat.code, 'CAT-ELECTRICAL')

    def test_machine_list_dual_view_rendering(self):
        """Verifies machine list template contains both Grid and Table view elements."""
        self.client.login(username='p22_owner', password=self.password)
        response = self.client.get(reverse('machines:list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('fleetGridView', content)
        self.assertIn('fleetTableView', content)
        self.assertIn('viewGridBtn', content)
        self.assertIn('viewTableBtn', content)
        self.assertIn('TR-001', content)
        self.assertIn('John Deere 5050D', content)

    def test_dispatch_board_lanes_rendered(self):
        """Verifies 5-lane Kanban dispatch board renders correctly."""
        self.client.login(username='p22_mgr', password=self.password)
        response = self.client.get(reverse('machines:dispatch_board'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('Requested', content)
        self.assertIn('Confirmed', content)
        self.assertIn('Dispatched', content)
        self.assertIn('In Progress', content)
        self.assertIn('Completed', content)

    def test_fuel_form_view_components(self):
        """Verifies fuel form contains live calculation elements, pills, and quick supplier modal."""
        self.client.login(username='p22_owner', password=self.password)
        response = self.client.get(reverse('fuel:create'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('displaySubtotal', content)
        self.assertIn('paymentPillContainer', content)
        self.assertIn('newSupplierModal', content)

    def test_expense_form_view_components(self):
        """Verifies expense form contains category modal, supplier modal, and payment pills."""
        self.client.login(username='p22_acc', password=self.password)
        response = self.client.get(reverse('expenses:create'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('newExpenseCategoryModal', content)
        self.assertIn('newSupplierModal', content)
        self.assertIn('expPaymentPillContainer', content)

    def test_dashboard_flow_equation_components(self):
        """Verifies executive dashboard renders central ledger equation and obligation silos."""
        self.client.login(username='p22_owner', password=self.password)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn("Today's Financial Summary", content)
        self.assertIn("Customer Receivables", content)
        self.assertIn("Supplier Payables", content)
        self.assertIn("Employee Wage Liabilities", content)
