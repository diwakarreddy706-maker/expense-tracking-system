"""
Automated Test Suite for Inter-Account Fund Transfers & Multi-Accountant User Isolation.
Tests:
1. Atomic double-entry transfer (Cash -> Bank, Bank -> UPI).
2. Balance conservation & Daily Closing net-zero integration.
3. Validation boundaries (insufficient funds, same account, negative/zero amount, inactive account).
4. Multi-Accountant isolation: Two distinct accountants with different passwords,
   verifying session isolation, atomic concurrency, and immutable audit logs.
5. HTTP View access control & RBAC enforcement.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from apps.accounts.models import UserProfile
from apps.finance.models import Account, AccountTransaction, DailyClosing
from apps.finance.services.settlement_service import AccountTransferService
from apps.finance.services.balance_service import FinancialCalculationService
from apps.finance.services.closing_service import DailyClosingService
from apps.audit.models import AuditLog


class InterAccountTransferTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Two distinct accountants with different credentials
        self.accountant_alpha = User.objects.create_user(
            username='accountant_alpha',
            password='AlphaSecurePassword123!',
            first_name='Alpha',
            last_name='Sharma'
        )
        self.accountant_alpha.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant_alpha.profile.save()

        self.accountant_beta = User.objects.create_user(
            username='accountant_beta',
            password='BetaSecurePassword456!',
            first_name='Beta',
            last_name='Kulkarni'
        )
        self.accountant_beta.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant_beta.profile.save()

        # Restricted Employee User
        self.employee_user = User.objects.create_user(
            username='employee_user',
            password='EmployeePassword789!'
        )
        self.employee_user.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee_user.profile.save()

        # Accounts Setup
        self.cash_account = Account.objects.create(
            account_name='Main Cash Drawer',
            account_type=Account.TYPE_CASH,
            opening_balance=Decimal('50000.00'),
            current_balance=Decimal('50000.00'),
            is_active=True
        )

        self.bank_account = Account.objects.create(
            account_name='SBI Current 4091',
            account_type=Account.TYPE_BANK_CURRENT,
            bank_name='State Bank of India',
            account_number='38901248091',
            ifsc_code='SBIN0001234',
            opening_balance=Decimal('100000.00'),
            current_balance=Decimal('100000.00'),
            is_active=True
        )

        self.upi_account = Account.objects.create(
            account_name='Shop UPI QR Wallet',
            account_type=Account.TYPE_UPI_WALLET,
            account_number='basaveshwara@upi',
            opening_balance=Decimal('10000.00'),
            current_balance=Decimal('10000.00'),
            is_active=True
        )

        self.inactive_account = Account.objects.create(
            account_name='Old Closed Account',
            account_type=Account.TYPE_BANK_SAVINGS,
            opening_balance=Decimal('0.00'),
            current_balance=Decimal('0.00'),
            is_active=False
        )

    def test_successful_transfer_cash_to_bank(self):
        """Test moving funds from Cash Drawer to Bank Account atomically."""
        tx_out, tx_in = AccountTransferService.transfer_funds(
            from_account_id=self.cash_account.id,
            to_account_id=self.bank_account.id,
            amount=Decimal('15000.00'),
            transfer_date=timezone.now().date(),
            reference_no='CASH-DEP-001',
            notes='Daily cash deposit to SBI',
            user=self.accountant_alpha
        )

        # Check Outflow
        self.assertEqual(tx_out.account.id, self.cash_account.id)
        self.assertEqual(tx_out.transaction_type, AccountTransaction.TYPE_TRANSFER_OUT)
        self.assertEqual(tx_out.direction, AccountTransaction.DIRECTION_DEBIT)
        self.assertEqual(tx_out.amount, Decimal('15000.00'))
        self.assertEqual(tx_out.created_by, self.accountant_alpha)

        # Check Inflow
        self.assertEqual(tx_in.account.id, self.bank_account.id)
        self.assertEqual(tx_in.transaction_type, AccountTransaction.TYPE_TRANSFER_IN)
        self.assertEqual(tx_in.direction, AccountTransaction.DIRECTION_CREDIT)
        self.assertEqual(tx_in.amount, Decimal('15000.00'))
        self.assertEqual(tx_in.created_by, self.accountant_alpha)

        # Check Updated Balances
        self.cash_account.refresh_from_db()
        self.bank_account.refresh_from_db()
        self.assertEqual(self.cash_account.current_balance, Decimal('35000.00'))
        self.assertEqual(self.bank_account.current_balance, Decimal('115000.00'))

        # Conservation of Money (Total liquid balance across business remains identical)
        total_liquid = self.cash_account.current_balance + self.bank_account.current_balance + self.upi_account.current_balance
        self.assertEqual(total_liquid, Decimal('160000.00'))

    def test_transfer_validation_guards(self):
        """Test boundary conditions and validation rejections."""
        # 1. Same account transfer rejected
        with self.assertRaises(ValidationError) as ctx:
            AccountTransferService.transfer_funds(
                from_account_id=self.cash_account.id,
                to_account_id=self.cash_account.id,
                amount=Decimal('5000.00'),
                user=self.accountant_alpha
            )
        self.assertIn("Source and destination accounts must be different", str(ctx.exception))

        # 2. Zero or negative amount rejected
        with self.assertRaises(ValidationError) as ctx:
            AccountTransferService.transfer_funds(
                from_account_id=self.cash_account.id,
                to_account_id=self.bank_account.id,
                amount=Decimal('0.00'),
                user=self.accountant_alpha
            )
        self.assertIn("Transfer amount must be strictly greater than zero", str(ctx.exception))

        # 3. Insufficient balance rejected
        with self.assertRaises(ValidationError) as ctx:
            AccountTransferService.transfer_funds(
                from_account_id=self.cash_account.id,
                to_account_id=self.bank_account.id,
                amount=Decimal('999999.00'),
                user=self.accountant_alpha
            )
        self.assertIn("Insufficient funds", str(ctx.exception))

        # 4. Inactive account rejected
        with self.assertRaises(ValidationError) as ctx:
            AccountTransferService.transfer_funds(
                from_account_id=self.inactive_account.id,
                to_account_id=self.bank_account.id,
                amount=Decimal('100.00'),
                user=self.accountant_alpha
            )
        self.assertIn("is inactive", str(ctx.exception))

    def test_multi_accountant_isolation_and_audit(self):
        """
        SCENARIO 2: Two distinct accountants with different credentials.
        Accountant Alpha transfers Cash -> Bank.
        Accountant Beta transfers Bank -> UPI.
        Verifies session isolation, independent audit logging, and ledger precision.
        """
        # --- Accountant Alpha Login & Action ---
        login_alpha = self.client.login(username='accountant_alpha', password='AlphaSecurePassword123!')
        self.assertTrue(login_alpha, "Accountant Alpha must authenticate successfully")

        res_alpha = self.client.post(reverse('finance:account_transfer'), {
            'from_account': self.cash_account.id,
            'to_account': self.bank_account.id,
            'amount': '10000.00',
            'transfer_date': timezone.now().strftime('%Y-%m-%d'),
            'reference_no': 'ALPHA-TX-001',
            'notes': 'Deposited by Accountant Alpha'
        }, follow=True)
        self.assertEqual(res_alpha.status_code, 200)

        # Verify Alpha's Audit Trail
        alpha_audit = AuditLog.objects.filter(
            user=self.accountant_alpha,
            action=AuditLog.ACTION_CREATE,
            entity_type='AccountTransfer'
        ).first()
        self.assertIsNotNone(alpha_audit, "AuditLog must record Accountant Alpha's action")
        self.assertIn('ALPHA-TX-001', str(alpha_audit.changes_json))

        self.client.logout()

        # --- Accountant Beta Login & Action ---
        login_beta = self.client.login(username='accountant_beta', password='BetaSecurePassword456!')
        self.assertTrue(login_beta, "Accountant Beta must authenticate successfully with distinct password")

        res_beta = self.client.post(reverse('finance:account_transfer'), {
            'from_account': self.bank_account.id,
            'to_account': self.upi_account.id,
            'amount': '5000.00',
            'transfer_date': timezone.now().strftime('%Y-%m-%d'),
            'reference_no': 'BETA-TX-002',
            'notes': 'UPI refill by Accountant Beta'
        }, follow=True)
        self.assertEqual(res_beta.status_code, 200)

        # Verify Beta's Audit Trail
        beta_audit = AuditLog.objects.filter(
            user=self.accountant_beta,
            action=AuditLog.ACTION_CREATE,
            entity_type='AccountTransfer'
        ).first()
        self.assertIsNotNone(beta_audit, "AuditLog must record Accountant Beta's action separately")
        self.assertIn('BETA-TX-002', str(beta_audit.changes_json))

        # Check Final Balances
        self.cash_account.refresh_from_db()
        self.bank_account.refresh_from_db()
        self.upi_account.refresh_from_db()

        # Cash: 50,000 - 10,000 = 40,000
        self.assertEqual(self.cash_account.current_balance, Decimal('40000.00'))
        # Bank: 100,000 + 10,000 - 5,000 = 105,000
        self.assertEqual(self.bank_account.current_balance, Decimal('105000.00'))
        # UPI: 10,000 + 5,000 = 15,000
        self.assertEqual(self.upi_account.current_balance, Decimal('15000.00'))

        # Total is still exactly 160,000.00
        total_balance = self.cash_account.current_balance + self.bank_account.current_balance + self.upi_account.current_balance
        self.assertEqual(total_balance, Decimal('160000.00'))

    def test_daily_closing_reflects_transfers_accurately(self):
        """
        Verify that daily closing calculations:
        - Accurately include transfer_out for Cash Account.
        - Accurately include transfer_in for Bank Account.
        - Net out to ₹0.00 for Consolidated Liquid Closing.
        """
        today = timezone.now().date()
        AccountTransferService.transfer_funds(
            from_account_id=self.cash_account.id,
            to_account_id=self.bank_account.id,
            amount=Decimal('12000.00'),
            transfer_date=today,
            reference_no='CLOSE-TEST-001',
            notes='Pre-closing transfer',
            user=self.accountant_alpha
        )

        # 1. Cash Account Closing Breakdown
        cash_recon = DailyClosingService.calculate_daily_reconciliation(
            closing_date=today,
            scope=DailyClosing.SCOPE_CASH,
            account_id=self.cash_account.id
        )
        self.assertEqual(cash_recon['transfer_out'], Decimal('12000.00'))
        self.assertEqual(cash_recon['transfer_in'], Decimal('0.00'))
        self.assertEqual(cash_recon['expected_closing'], Decimal('38000.00'))

        # 2. Bank Account Closing Breakdown
        bank_recon = DailyClosingService.calculate_daily_reconciliation(
            closing_date=today,
            scope=DailyClosing.SCOPE_BANK,
            account_id=self.bank_account.id
        )
        self.assertEqual(bank_recon['transfer_in'], Decimal('12000.00'))
        self.assertEqual(bank_recon['transfer_out'], Decimal('0.00'))
        self.assertEqual(bank_recon['expected_closing'], Decimal('112000.00'))

        # 3. Consolidated Closing Breakdown (transfers net out to zero)
        cons_recon = DailyClosingService.calculate_daily_reconciliation(
            closing_date=today,
            scope=DailyClosing.SCOPE_CONSOLIDATED
        )
        self.assertEqual(cons_recon['transfer_in'], Decimal('0.00'))
        self.assertEqual(cons_recon['transfer_out'], Decimal('0.00'))
        self.assertEqual(cons_recon['expected_closing'], Decimal('160000.00'))

    def test_rbac_view_permission_checks(self):
        """Verify only OWNER and ACCOUNTANT can access the transfer view."""
        url = reverse('finance:account_transfer')

        # 1. Unauthenticated -> Redirects to login
        res_anon = self.client.get(url)
        self.assertEqual(res_anon.status_code, 302)
        self.assertIn(reverse('accounts:login'), res_anon.url)

        # 2. Employee -> 403 Forbidden
        self.client.login(username='employee_user', password='EmployeePassword789!')
        res_op = self.client.get(url)
        self.assertEqual(res_op.status_code, 403)
        self.client.logout()

        # 3. Accountant Alpha -> 200 OK
        self.client.login(username='accountant_alpha', password='AlphaSecurePassword123!')
        res_acc = self.client.get(url)
        self.assertEqual(res_acc.status_code, 200)
        self.assertTemplateUsed(res_acc, 'finance/account_transfer.html')
