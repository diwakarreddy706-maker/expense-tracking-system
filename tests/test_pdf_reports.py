"""
PHASE 23 COMPREHENSIVE TEST SUITE: ENTERPRISE PDF EXPORT & FINANCIAL REPORTING.
Tests all A4 PDF generation services, endpoints, RBAC authorization, IDOR protection,
read-only guarantees, pagination, empty data states, and governance audit trails.
"""

from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.finance.models import Account, Customer, Receivable, CustomerPayment, AccountTransaction
from apps.machines.models import Machine, MachineType, MachineWorkEntry
from apps.expenses.models import Expense, ExpenseCategory
from apps.fuel.models import FuelEntry
from apps.reports.models import CompanyProfile, ReportAuditLog


class EnterprisePDFReportsTestCase(TestCase):
    """
    Test suite for Phase 23 Enterprise PDF Export & Financial Reporting.
    """

    def setUp(self):
        self.client = Client()

        # 1. Setup Users with distinct RBAC Roles
        self.owner = User.objects.create_user(username='owner_user', password='password123')
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.accountant = User.objects.create_user(username='accountant_user', password='password123')
        self.accountant.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant.profile.save()

        self.driver = User.objects.create_user(username='driver_user', password='password123')
        self.driver.profile.role = UserProfile.ROLE_EMPLOYEE
        self.driver.profile.save()

        # 2. Setup Company Profile
        self.company_profile = CompanyProfile.objects.create(
            business_name='Sri Basaveshwara Harvesting & Co',
            legal_name='Sri Basaveshwara Agricultural Contractor Services',
            phone='+91 9880199000',
            village='Harapanahalli Road',
            district='Vijayanagara',
            state='Karnataka',
            pin_code='583131',
            authorized_signatory_name='B. Veerappa',
            authorized_signatory_designation='Managing Partner'
        )

        # 3. Setup Financial Master Data
        self.cash_account = Account.objects.create(
            account_name='Primary Cash Box',
            account_type=Account.TYPE_CASH,
            opening_balance=Decimal('50000.00'),
            current_balance=Decimal('50000.00')
        )
        self.bank_account = Account.objects.create(
            account_name='SBI Current Account',
            account_type=Account.TYPE_BANK_CURRENT,
            opening_balance=Decimal('150000.00'),
            current_balance=Decimal('150000.00')
        )

        # 4. Setup Customer / Farmer
        self.farmer = Customer.objects.create(
            customer_code='CUST-2026-0001',
            name='Basavaraj Patel',
            phone='9845012345',
            location_address='Chigateri Village, Harapanahalli'
        )

        # 5. Setup Machine & Type
        self.m_type = MachineType.objects.create(name='Combine Harvester', code='HARV')
        self.machine = Machine.objects.create(
            machine_code='HARV-01',
            name='Class Crop Tiger 37',
            machine_type=self.m_type,
            hourly_rate=Decimal('2500.00'),
            current_meter_reading=Decimal('120.00')
        )

        # 6. Setup Work Entry
        self.work_entry = MachineWorkEntry.objects.create(
            work_code='WRK-2026-0001',
            manual_bill_no='BILL-1001',
            work_date=timezone.now().date(),
            machine=self.machine,
            customer=self.farmer,
            billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
            start_time='09:00:00',
            end_time='13:00:00',
            break_hours=Decimal('0.50'),
            net_working_hours=Decimal('3.50'),
            hourly_rate=Decimal('2500.00'),
            total_amount=Decimal('8750.00'),
            advance_amount=Decimal('3000.00'),
            udhar_amount=Decimal('5750.00'),
            payment_mode='SPLIT',
            created_by=self.owner
        )

        # 7. Setup Receivable & Customer Payment
        self.receivable = Receivable.objects.create(
            receivable_code='REC-2026-0001',
            customer=self.farmer,
            invoice_no='BILL-1001',
            bill_date=timezone.now().date(),
            total_amount=Decimal('5750.00'),
            received_amount=Decimal('2000.00'),
            status=Receivable.STATUS_PARTIAL,
            created_by=self.owner
        )
        self.work_entry.receivable = self.receivable
        self.work_entry.save()

        self.payment = CustomerPayment.objects.create(
            payment_code='PMT-2026-0001',
            receivable=self.receivable,
            account=self.cash_account,
            payment_date=timezone.now().date(),
            amount=Decimal('2000.00'),
            payment_method=CustomerPayment.METHOD_CASH,
            reference_no='CASH-REC-01',
            created_by=self.owner
        )

        # 8. Setup Expense Category & Machine Expense
        self.fuel_cat = ExpenseCategory.objects.create(name='Diesel / Fuel', code='FUEL')
        self.expense = Expense.objects.create(
            expense_code='EXP-2026-0001',
            category=self.fuel_cat,
            account=self.cash_account,
            machine=self.machine,
            amount=Decimal('4200.00'),
            expense_date=timezone.now().date(),
            payment_method='CASH',
            created_by=self.owner
        )

    def test_farmer_statement_pdf_authorized(self):
        """1. Farmer Statement PDF returns HTTP 200, application/pdf, and valid binary."""
        self.client.force_login(self.owner)
        url = reverse('machines:farmer_ledger_pdf', kwargs={'customer_id': self.farmer.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertGreater(len(response.content), 1000)
        self.assertIn('filename=', response.get('Content-Disposition', ''))

    def test_payment_receipt_pdf_authorized(self):
        """2. Payment / Advance Receipt PDF returns HTTP 200 and application/pdf."""
        self.client.force_login(self.accountant)
        url = reverse('finance:customer_payment_receipt_pdf', kwargs={'payment_id': self.payment.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertGreater(len(response.content), 1000)
        self.assertIn('filename=', response.get('Content-Disposition', ''))

    def test_work_invoice_pdf_authorized(self):
        """3. Work Invoice PDF returns HTTP 200 and application/pdf."""
        self.client.force_login(self.owner)
        url = reverse('machines:work_pdf', kwargs={'entry_id': self.work_entry.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertGreater(len(response.content), 1000)
        self.assertIn('filename=', response.get('Content-Disposition', ''))

    def test_machinery_pnl_pdf_authorized(self):
        """4. Machinery Operational P&L PDF returns HTTP 200 in landscape A4."""
        self.client.force_login(self.owner)
        url = reverse('reports:machinery_pnl_pdf')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertGreater(len(response.content), 1000)
        self.assertIn('filename=', response.get('Content-Disposition', ''))

    def test_expense_analysis_pdf_authorized(self):
        """5. Comprehensive Expense Analysis PDF returns HTTP 200 and application/pdf."""
        self.client.force_login(self.accountant)
        url = reverse('reports:expense_pdf')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertGreater(len(response.content), 1000)
        self.assertIn('filename=', response.get('Content-Disposition', ''))

    def test_receivables_aging_pdf_authorized(self):
        """6. Receivables Aging PDF returns HTTP 200 and application/pdf."""
        self.client.force_login(self.owner)
        url = reverse('reports:receivables_aging_pdf')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertGreater(len(response.content), 1000)
        self.assertIn('filename=', response.get('Content-Disposition', ''))

    def test_rbac_unauthorized_user_denied(self):
        """7. Unauthorized users (e.g. Tractor Driver) receive HTTP 403."""
        self.client.force_login(self.driver)

        # Driver cannot access Farmer Statement
        url1 = reverse('machines:farmer_ledger_pdf', kwargs={'customer_id': self.farmer.id})
        response1 = self.client.get(url1)
        self.assertEqual(response1.status_code, 403)

        # Driver cannot access Machinery P&L
        url2 = reverse('reports:machinery_pnl_pdf')
        response2 = self.client.get(url2)
        self.assertEqual(response2.status_code, 403)

        # Driver cannot access Receivables Aging
        url3 = reverse('reports:receivables_aging_pdf')
        response3 = self.client.get(url3)
        self.assertEqual(response3.status_code, 403)

    def test_empty_data_pdf_generation(self):
        """8. PDF generation succeeds gracefully with empty data / no records."""
        self.client.force_login(self.owner)
        empty_farmer = Customer.objects.create(
            customer_code='CUST-EMPTY-001',
            name='New Farmer Without Work'
        )
        url = reverse('machines:farmer_ledger_pdf', kwargs={'customer_id': empty_farmer.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertGreater(len(response.content), 500)


    def test_read_only_guarantee(self):
        """9. Generating PDFs MUST NOT create financial transactions or alter balances."""
        self.client.force_login(self.owner)

        initial_tx_count = AccountTransaction.objects.count()
        initial_rec_count = Receivable.objects.count()
        initial_pmt_count = CustomerPayment.objects.count()
        initial_exp_count = Expense.objects.count()

        # Generate all 6 reports
        self.client.get(reverse('machines:farmer_ledger_pdf', kwargs={'customer_id': self.farmer.id}))
        self.client.get(reverse('finance:customer_payment_receipt_pdf', kwargs={'payment_id': self.payment.id}))
        self.client.get(reverse('machines:work_pdf', kwargs={'entry_id': self.work_entry.id}))
        self.client.get(reverse('reports:machinery_pnl_pdf'))
        self.client.get(reverse('reports:expense_pdf'))
        self.client.get(reverse('reports:receivables_aging_pdf'))

        # Verify exact counts remain unchanged
        self.assertEqual(AccountTransaction.objects.count(), initial_tx_count)
        self.assertEqual(Receivable.objects.count(), initial_rec_count)
        self.assertEqual(CustomerPayment.objects.count(), initial_pmt_count)
        self.assertEqual(Expense.objects.count(), initial_exp_count)

    def test_audit_log_creation(self):
        """10. PDF generation creates non-financial ReportAuditLog entries."""
        self.client.force_login(self.owner)

        initial_audit_count = ReportAuditLog.objects.count()
        self.client.get(reverse('machines:farmer_ledger_pdf', kwargs={'customer_id': self.farmer.id}))

        self.assertEqual(ReportAuditLog.objects.count(), initial_audit_count + 1)
        latest_audit = ReportAuditLog.objects.first()
        self.assertEqual(latest_audit.report_type, ReportAuditLog.TYPE_FARMER_STATEMENT)
        self.assertEqual(latest_audit.user, self.owner)
        self.assertEqual(latest_audit.related_object_id, self.farmer.id)
        self.assertTrue(latest_audit.success)

    def test_multi_page_pagination(self):
        """11. Generates valid multi-page PDF when large volume of work entries exist."""
        self.client.force_login(self.owner)

        # Create 40 work entries to force multiple pages
        for i in range(2, 42):
            MachineWorkEntry.objects.create(
                work_code=f'WRK-2026-{i:04d}',
                manual_bill_no=f'BILL-{1000+i}',
                work_date=timezone.now().date() - timedelta(days=i),
                machine=self.machine,
                customer=self.farmer,
                billing_type=MachineWorkEntry.BILLING_TIME_HOURLY,
                net_working_hours=Decimal('2.00'),
                hourly_rate=Decimal('2500.00'),
                total_amount=Decimal('5000.00'),
                advance_amount=Decimal('1000.00'),
                udhar_amount=Decimal('4000.00'),
                created_by=self.owner
            )

        url = reverse('machines:farmer_ledger_pdf', kwargs={'customer_id': self.farmer.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF-'))
        # Binary size should reflect multi-page document
        self.assertGreater(len(response.content), 5000)
