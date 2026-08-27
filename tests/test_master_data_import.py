"""
Comprehensive Automated Test Suite for Phase 18:
Real Business Master Data CSV Import, Preview, Onboarding, and Reconciliation.
"""

import io
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import UserProfile
from apps.finance.models import Account, Customer, Supplier, Receivable, Payable
from apps.machines.models import Machine, MachineType
from apps.employees.models import Employee, EmployeeCompensation
from apps.finance.services.import_service import MasterDataImportService


class MasterDataImportTests(TestCase):
    """
    Tests for MasterDataImportService, CSV preview validation, atomic import,
    template generation, opening balance reconciliation, and RBAC enforcement.
    """

    def setUp(self):
        self.client = Client()

        # Create Owner User
        self.owner = User.objects.create_user(username='import_owner', password='password123')
        UserProfile.objects.update_or_create(user=self.owner, defaults={'role': 'OWNER'})

        # Create Accountant User
        self.accountant = User.objects.create_user(username='import_accountant', password='password123')
        UserProfile.objects.update_or_create(user=self.accountant, defaults={'role': 'ACCOUNTANT'})

        # Create Manager User
        self.manager = User.objects.create_user(username='import_manager', password='password123')
        UserProfile.objects.update_or_create(user=self.manager, defaults={'role': 'MANAGER'})

        # Create Employee User
        self.employee_user = User.objects.create_user(username='import_emp_user', password='password123')
        UserProfile.objects.update_or_create(user=self.employee_user, defaults={'role': 'EMPLOYEE'})

        # Seed standard MachineTypes
        self.tractor_type, _ = MachineType.objects.get_or_create(code='TRACTOR', defaults={'name': 'Tractor'})
        self.harvester_type, _ = MachineType.objects.get_or_create(code='PADDY_HARVESTER', defaults={'name': 'Paddy Harvester'})

    def test_csv_template_generation_and_download(self):
        """Tests that standard CSV templates are generated correctly and downloadable."""
        self.client.login(username='import_owner', password='password123')

        for entity in ['machines', 'customers', 'suppliers', 'employees', 'accounts']:
            csv_text = MasterDataImportService.generate_csv_template(entity)
            self.assertTrue(len(csv_text) > 0)
            self.assertIn(',', csv_text)

            url = reverse('finance:setup_csv_template', kwargs={'entity_type': entity})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
            self.assertIn(f'attachment; filename="{entity}_template.csv"', response['Content-Disposition'])

    def test_csv_preview_valid_machine_file(self):
        """Tests that a valid machine CSV parses without errors and marks readiness."""
        csv_content = (
            "machine_code,name,machine_type,registration_no,current_meter_reading,meter_unit,purchase_price,status\n"
            "MCH-101,John Deere 5050D,TRACTOR,KA-25-TR-1001,150.50,HOURS,750000.00,ACTIVE\n"
            "MCH-102,Kubota Combine,PADDY_HARVESTER,KA-25-HV-2002,320.00,HOURS,2200000.00,ACTIVE\n"
        )
        file_obj = io.StringIO(csv_content)
        result = MasterDataImportService.parse_and_validate('machines', file_obj)

        self.assertTrue(result['success'])
        self.assertEqual(result['total_rows'], 2)
        self.assertEqual(result['valid_rows_count'], 2)
        self.assertEqual(result['invalid_rows_count'], 0)
        self.assertTrue(result['is_ready_for_import'])
        self.assertEqual(len(result['errors']), 0)

    def test_csv_preview_invalid_machine_type_and_negative_values(self):
        """Tests that invalid enum machine types and negative numbers are detected."""
        csv_content = (
            "machine_code,name,machine_type,registration_no,current_meter_reading,meter_unit,purchase_price,status\n"
            "MCH-999,Invalid Aeroplane,SPACESHIP,KA-01-XX-9999,-50.00,HOURS,-10000.00,ACTIVE\n"
        )
        file_obj = io.StringIO(csv_content)
        result = MasterDataImportService.parse_and_validate('machines', file_obj)

        self.assertTrue(result['success'])
        self.assertEqual(result['total_rows'], 1)
        self.assertEqual(result['valid_rows_count'], 0)
        self.assertEqual(result['invalid_rows_count'], 1)
        self.assertFalse(result['is_ready_for_import'])
        self.assertTrue(len(result['errors']) > 0)
        self.assertFalse(result['preview_rows'][0]['is_valid'])

    def test_csv_preview_duplicate_codes_in_file_and_db(self):
        """Tests that duplicate codes within CSV or existing DB records are rejected."""
        # Create an existing machine
        Machine.objects.create(
            machine_code='MCH-EXISTS',
            name='Existing Tractor',
            machine_type=self.tractor_type,
            registration_no='AP-01-AA-0001'
        )

        csv_content = (
            "machine_code,name,machine_type,registration_no,current_meter_reading,meter_unit,purchase_price,status\n"
            "MCH-EXISTS,Duplicate in DB,TRACTOR,AP-01-AA-0002,100,HOURS,500000,ACTIVE\n"
            "MCH-DUP,Duplicate In File 1,TRACTOR,AP-01-AA-0003,100,HOURS,500000,ACTIVE\n"
            "MCH-DUP,Duplicate In File 2,TRACTOR,AP-01-AA-0004,100,HOURS,500000,ACTIVE\n"
        )
        file_obj = io.StringIO(csv_content)
        result = MasterDataImportService.parse_and_validate('machines', file_obj)

        self.assertEqual(result['invalid_rows_count'], 2)  # MCH-EXISTS and the second MCH-DUP

    def test_csv_import_machines_atomic_execution(self):
        """Tests atomic import execution for machines."""
        preview_data = [
            {
                'row_number': 2,
                'is_valid': True,
                'data': {
                    'machine_code': 'MCH-NEW-1',
                    'name': 'Mahindra Yuvo 575',
                    'machine_type': 'TRACTOR',
                    'registration_no': 'KA-25-T-8899',
                    'current_meter_reading': '250.00',
                    'meter_unit': 'HOURS',
                    'purchase_price': '820000.00',
                    'status': 'ACTIVE'
                }
            }
        ]

        result = MasterDataImportService.execute_import('machines', preview_data, self.owner)
        self.assertTrue(result['success'])
        self.assertEqual(result['imported_count'], 1)

        m = Machine.objects.get(machine_code='MCH-NEW-1')
        self.assertEqual(m.name, 'Mahindra Yuvo 575')
        self.assertEqual(m.current_meter_reading, Decimal('250.00'))
        self.assertEqual(m.purchase_price, Decimal('820000.00'))

    def test_csv_import_customers_with_opening_receivable(self):
        """Tests customer onboarding with opening balance creates opening receivable cleanly."""
        preview_data = [
            {
                'row_number': 2,
                'is_valid': True,
                'data': {
                    'customer_code': 'CUST-IMPORT-1',
                    'name': 'Gowda Farmers Syndicate',
                    'phone': '9876543210',
                    'location_address': 'Mandya District',
                    'opening_balance': '18500.00',
                    'notes': 'Season opening balance'
                }
            }
        ]

        result = MasterDataImportService.execute_import('customers', preview_data, self.owner)
        self.assertTrue(result['success'])
        self.assertEqual(result['imported_count'], 1)
        self.assertEqual(result['opening_records_created'], 1)

        c = Customer.objects.get(customer_code='CUST-IMPORT-1')
        self.assertEqual(c.name, 'Gowda Farmers Syndicate')

        # Verify opening receivable created
        rec = Receivable.objects.get(customer=c)
        self.assertEqual(rec.total_amount, Decimal('18500.00'))
        self.assertEqual(rec.invoice_no, 'OPENING-BAL')
        self.assertEqual(rec.status, Receivable.STATUS_UNPAID)

    def test_csv_import_suppliers_with_opening_payable(self):
        """Tests supplier onboarding with opening balance creates opening payable cleanly."""
        preview_data = [
            {
                'row_number': 2,
                'is_valid': True,
                'data': {
                    'supplier_code': 'SUPP-IMPORT-1',
                    'name': 'Sri Venkateshwara Fuels',
                    'supplier_type': 'FUEL_PUMP',
                    'phone': '9845012345',
                    'location_address': 'Highway Junction',
                    'payment_terms': 'Weekly',
                    'opening_balance': '42000.00',
                    'notes': 'Diesel opening due'
                }
            }
        ]

        result = MasterDataImportService.execute_import('suppliers', preview_data, self.owner)
        self.assertTrue(result['success'])
        self.assertEqual(result['imported_count'], 1)
        self.assertEqual(result['opening_records_created'], 1)

        s = Supplier.objects.get(supplier_code='SUPP-IMPORT-1')
        self.assertEqual(s.supplier_type, Supplier.TYPE_FUEL_PUMP)

        # Verify opening payable created
        pay = Payable.objects.get(supplier=s)
        self.assertEqual(pay.total_amount, Decimal('42000.00'))
        self.assertEqual(pay.bill_no, 'OPENING-BAL')
        self.assertEqual(pay.status, Payable.STATUS_UNPAID)

    def test_csv_import_employees_with_compensation_rates(self):
        """Tests employee onboarding creates employee and authoritative EmployeeCompensation."""
        preview_data = [
            {
                'row_number': 2,
                'is_valid': True,
                'data': {
                    'employee_code': 'EMP-IMPORT-1',
                    'full_name': 'Basavaraj Patil',
                    'role': 'TRACTOR_DRIVER',
                    'phone_number': '9900112233',
                    'wage_type': 'DAILY_WAGE',
                    'base_rate': '650.00',
                    'emergency_contact': '9880011223'
                }
            }
        ]

        result = MasterDataImportService.execute_import('employees', preview_data, self.owner)
        self.assertTrue(result['success'])

        emp = Employee.objects.get(employee_code='EMP-IMPORT-1')
        self.assertEqual(emp.full_name, 'Basavaraj Patil')
        self.assertEqual(emp.role, Employee.ROLE_TRACTOR_DRIVER)

        # Verify EmployeeCompensation record created
        comp = EmployeeCompensation.objects.get(employee=emp)
        self.assertEqual(comp.wage_type, Employee.WAGE_DAILY)
        self.assertEqual(comp.rate, Decimal('650.00'))
        self.assertTrue(comp.is_active)

    def test_csv_import_accounts_with_initial_balance(self):
        """Tests financial account onboarding sets initial and current balances correctly."""
        preview_data = [
            {
                'row_number': 2,
                'is_valid': True,
                'data': {
                    'account_name': 'HDFC Primary Current',
                    'account_type': 'BANK_CURRENT',
                    'bank_name': 'HDFC Bank Ltd',
                    'account_number': '50200012345678',
                    'ifsc_code': 'HDFC0001234',
                    'opening_balance': '125000.00'
                }
            }
        ]

        result = MasterDataImportService.execute_import('accounts', preview_data, self.owner)
        self.assertTrue(result['success'])

        acc = Account.objects.get(account_name='HDFC Primary Current')
        self.assertEqual(acc.opening_balance, Decimal('125000.00'))
        self.assertEqual(acc.current_balance, Decimal('125000.00'))
        self.assertEqual(acc.account_type, Account.TYPE_BANK_CURRENT)

    def test_opening_balance_reconciliation_view_and_equity_equation(self):
        """Tests the opening balance reconciliation dashboard metrics and calculations."""
        self.client.login(username='import_owner', password='password123')

        # Create account
        Account.objects.create(account_name='Cash Box', account_type='CASH', opening_balance=Decimal('50000.00'), current_balance=Decimal('50000.00'))
        # Create Customer + Opening Receivable
        c = Customer.objects.create(customer_code='CUST-REC-1', name='Farmer A')
        Receivable.objects.create(receivable_code='REC-1', customer=c, invoice_no='OP-1', total_amount=Decimal('10000.00'), created_by=self.owner)
        # Create Supplier + Opening Payable
        s = Supplier.objects.create(supplier_code='SUPP-PAY-1', name='Supplier B')
        Payable.objects.create(payable_code='PAY-1', supplier=s, bill_no='OP-1', total_amount=Decimal('4000.00'), created_by=self.owner)

        url = reverse('finance:setup_reconciliation')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Net Onboarding Capital = 50000 + 10000 - 4000 = 56000
        self.assertEqual(response.context['net_onboarding_capital'], Decimal('56000.00'))
        self.assertEqual(response.context['total_opening_funds'], Decimal('50000.00'))
        self.assertEqual(response.context['total_cust_receivables'], Decimal('10000.00'))
        self.assertEqual(response.context['total_supp_payables'], Decimal('4000.00'))

    def test_ajax_csv_preview_and_import_endpoints(self):
        """Tests the HTTP AJAX preview and import endpoints end-to-end."""
        self.client.login(username='import_accountant', password='password123')

        csv_content = (
            "customer_code,name,phone,location_address,opening_balance,notes\n"
            "CUST-AJAX-1,Siddeshwar Farms,9876541234,Belgaum,5000.00,AJAX test customer\n"
        )
        csv_file = SimpleUploadedFile("customers.csv", csv_content.encode('utf-8'), content_type="text/csv")

        # 1. Preview AJAX
        preview_url = reverse('finance:setup_csv_preview')
        preview_resp = self.client.post(preview_url, {'entity_type': 'customers', 'csv_file': csv_file})
        self.assertEqual(preview_resp.status_code, 200)
        data = preview_resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['valid_rows_count'], 1)

        # 2. Import AJAX
        import_url = reverse('finance:setup_csv_import')
        import_resp = self.client.post(
            import_url,
            json.dumps({'entity_type': 'customers', 'preview_rows': data['preview_rows']}),
            content_type='application/json'
        )
        self.assertEqual(import_resp.status_code, 200)
        import_data = import_resp.json()
        self.assertTrue(import_data['success'])
        self.assertEqual(import_data['imported_count'], 1)

        self.assertTrue(Customer.objects.filter(customer_code='CUST-AJAX-1').exists())

    def test_master_data_import_rbac_security(self):
        """Tests that Owner and Accountant can access import views, but Manager and Employee are forbidden."""
        # 1. Manager attempts to access preview
        self.client.login(username='import_manager', password='password123')
        resp = self.client.post(reverse('finance:setup_csv_preview'), {'entity_type': 'machines'})
        self.assertEqual(resp.status_code, 403)

        resp = self.client.get(reverse('finance:setup_reconciliation'))
        self.assertEqual(resp.status_code, 403)

        # 2. Employee attempts to access setup hub
        self.client.login(username='import_emp_user', password='password123')
        resp = self.client.get(reverse('finance:setup_hub'))
        self.assertEqual(resp.status_code, 403)

        # 3. Accountant access allowed
        self.client.login(username='import_accountant', password='password123')
        resp = self.client.get(reverse('finance:setup_hub'))
        self.assertEqual(resp.status_code, 200)
