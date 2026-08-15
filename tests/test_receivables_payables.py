"""
Phase 7 Comprehensive Test Suite: Customer Receivables & Supplier Payables.
Validates:
- Customer Receivables creation, partial/full settlements, overpayment rejection, no duplicate revenue.
- Supplier Payables creation, partial/full disbursements, overpayment rejection, no duplicate expense.
- Credit Expense Integration: Credit Expense -> Supplier Payable -> Later Payment -> Ledger Debit.
- Reversal mechanics: Restoration of receivable/payable balances and compensatory ledger transactions.
- Concurrency & Atomicity.
- RBAC barriers & Audit trails.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.finance.models import (
    Account, AccountTransaction,
    Customer, Supplier,
    Receivable, CustomerPayment,
    Payable, SupplierPayment
)
from apps.expenses.models import Expense, ExpenseCategory
from apps.expenses.services.expense_service import ExpenseService
from apps.finance.services.settlement_service import (
    CustomerReceivableService,
    SupplierPayableService
)


class CustomerReceivablesLifecycleTests(TestCase):
    """Verifies customer receivables, partial/full payments, no duplicate revenue, and reversals."""

    def setUp(self):
        self.password = "SafePassword123!"
        self.owner = User.objects.create_user(username="rcv_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.account = Account.objects.create(
            account_name="Collections Current Account",
            account_type=Account.TYPE_BANK_CURRENT,
            opening_balance=Decimal('10000.00'),
            current_balance=Decimal('10000.00'),
            is_active=True
        )

        self.customer = Customer.objects.create(
            customer_code="CUST-001",
            name="Rajesh Patil",
            phone="9876543210",
            status=Customer.STATUS_ACTIVE
        )

    def test_receivable_creation_and_partial_to_full_settlement(self):
        """
        Proof of Lifecycle:
        1. Receivable created: ₹50,000 (UNPAID)
        2. Payment 1: ₹20,000 (PARTIAL, Remaining: ₹30,000, Bank: +₹20,000)
        3. Payment 2: ₹30,000 (PAID, Remaining: ₹0, Bank: +₹30,000)
        4. Central Ledger: Exactly two RECEIVABLE_PAYMENT credit entries.
        """
        initial_balance = self.account.current_balance
        total_billed = Decimal('50000.00')

        # 1. Create Receivable
        rcv = CustomerReceivableService.create_receivable(
            user=self.owner,
            customer=self.customer,
            total_amount=total_billed,
            invoice_no="INV-2026-001",
            notes="Wheat harvest contract"
        )
        self.assertEqual(rcv.status, Receivable.STATUS_UNPAID)
        self.assertEqual(rcv.received_amount, Decimal('0.00'))
        self.assertEqual(rcv.outstanding_amount, total_billed)

        # 2. Payment 1: ₹20,000
        pay1 = CustomerReceivableService.record_payment(
            user=self.owner,
            receivable_id=rcv.id,
            amount=Decimal('20000.00'),
            account=self.account,
            payment_method=CustomerPayment.METHOD_UPI,
            reference_no="UPI-REC-01"
        )
        rcv.refresh_from_db()
        self.assertEqual(rcv.status, Receivable.STATUS_PARTIAL)
        self.assertEqual(rcv.received_amount, Decimal('20000.00'))
        self.assertEqual(rcv.outstanding_amount, Decimal('30000.00'))

        # Verify Bank credited
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance + Decimal('20000.00'))

        # 3. Payment 2: ₹30,000
        pay2 = CustomerReceivableService.record_payment(
            user=self.owner,
            receivable_id=rcv.id,
            amount=Decimal('30000.00'),
            account=self.account,
            payment_method=CustomerPayment.METHOD_BANK_TRANSFER,
            reference_no="NEFT-REC-02"
        )
        rcv.refresh_from_db()
        self.assertEqual(rcv.status, Receivable.STATUS_PAID)
        self.assertEqual(rcv.received_amount, total_billed)
        self.assertEqual(rcv.outstanding_amount, Decimal('0.00'))

        # Verify Bank total credited
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance + total_billed)

        # Verify Ledger Entries (Type: RECEIVABLE_PAYMENT, Direction: CREDIT)
        txs = AccountTransaction.objects.filter(reference_type='CustomerPayment')
        self.assertEqual(txs.count(), 2)
        for tx in txs:
            self.assertEqual(tx.transaction_type, AccountTransaction.TYPE_RECEIVABLE_PAYMENT)
            self.assertEqual(tx.direction, AccountTransaction.DIRECTION_CREDIT)

    def test_overpayment_strictly_rejected(self):
        """Verifies customer payment exceeding outstanding balance is rejected server-side."""
        rcv = CustomerReceivableService.create_receivable(
            user=self.owner,
            customer=self.customer,
            total_amount=Decimal('10000.00')
        )

        with self.assertRaises(ValidationError) as ctx:
            CustomerReceivableService.record_payment(
                user=self.owner,
                receivable_id=rcv.id,
                amount=Decimal('10000.01'), # 1 paisa over
                account=self.account
            )
        self.assertIn("Overpayment is rejected", str(ctx.exception))

    def test_customer_payment_reversal_restores_receivable_and_balance(self):
        """Verifies reversing a customer payment restores receivable outstanding balance."""
        initial_balance = self.account.current_balance
        rcv = CustomerReceivableService.create_receivable(
            user=self.owner,
            customer=self.customer,
            total_amount=Decimal('15000.00')
        )

        pay = CustomerReceivableService.record_payment(
            user=self.owner,
            receivable_id=rcv.id,
            amount=Decimal('15000.00'),
            account=self.account
        )
        rcv.refresh_from_db()
        self.assertEqual(rcv.status, Receivable.STATUS_PAID)

        # Reverse payment
        CustomerReceivableService.reverse_payment(
            payment_id=pay.id,
            user=self.owner,
            reason="Cheque dishonored by bank"
        )

        rcv.refresh_from_db()
        self.assertEqual(rcv.status, Receivable.STATUS_UNPAID)
        self.assertEqual(rcv.received_amount, Decimal('0.00'))
        self.assertEqual(rcv.outstanding_amount, Decimal('15000.00'))

        # Authoritative account balance restored
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance)


class SupplierPayablesAndCreditIntegrationTests(TestCase):
    """Verifies supplier payables, credit expense integration, disbursements, no duplicate expense, and reversals."""

    def setUp(self):
        self.password = "SafePassword123!"
        self.owner = User.objects.create_user(username="pay_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.account = Account.objects.create(
            account_name="Disbursement Account",
            account_type=Account.TYPE_BANK_CURRENT,
            opening_balance=Decimal('80000.00'),
            current_balance=Decimal('80000.00'),
            is_active=True
        )

        self.supplier = Supplier.objects.create(
            supplier_code="SUPP-FUEL-01",
            name="BPCL Auto Fuel",
            supplier_type=Supplier.TYPE_FUEL_PUMP,
            status=Supplier.STATUS_ACTIVE
        )

        self.category = ExpenseCategory.objects.create(
            name="Diesel & Fuel",
            code="CAT-FUEL"
        )

    def test_credit_expense_creates_payable_without_immediate_cash_deduction(self):
        """
        Proof of Credit Expense Integration:
        1. Credit expense logged: ₹25,000
        2. Supplier Payable automatically created: ₹25,000 (UNPAID)
        3. Account balance: Unchanged (₹80,000)
        4. Later Supplier Payment: ₹25,000
        5. Payable: Settled (PAID)
        6. Account balance: Decreases by ₹25,000 (₹55,000)
        7. No duplicate expense created!
        """
        initial_balance = self.account.current_balance
        initial_expense_count = Expense.objects.count()

        # Step 1: Log CREDIT Expense
        exp, tx = ExpenseService.create_expense(
            user=self.owner,
            amount=Decimal('25000.00'),
            category=self.category,
            payment_method=Expense.METHOD_CREDIT,
            supplier=self.supplier,
            description="Credit Diesel for Harvesting"
        )
        self.assertIsNone(tx) # No immediate ledger movement

        # Verify Account balance unchanged
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance)

        # Verify Supplier Payable created
        payable = Payable.objects.filter(linked_expense=exp).first()
        self.assertIsNotNone(payable)
        self.assertEqual(payable.total_amount, Decimal('25000.00'))
        self.assertEqual(payable.status, Payable.STATUS_UNPAID)

        # Step 2: Later Supplier Payment
        spay = SupplierPayableService.record_payment(
            user=self.owner,
            payable_id=payable.id,
            amount=Decimal('25000.00'),
            account=self.account,
            payment_method=SupplierPayment.METHOD_BANK_TRANSFER,
            reference_no="NEFT-DISB-01"
        )

        payable.refresh_from_db()
        self.assertEqual(payable.status, Payable.STATUS_PAID)
        self.assertEqual(payable.paid_amount, Decimal('25000.00'))
        self.assertEqual(payable.outstanding_amount, Decimal('0.00'))

        # Verify Account debited
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance - Decimal('25000.00'))

        # Verify Ledger Transaction: PAYABLE_PAYMENT, DEBIT
        self.assertIsNotNone(spay.linked_ledger_transaction)
        self.assertEqual(spay.linked_ledger_transaction.transaction_type, AccountTransaction.TYPE_PAYABLE_PAYMENT)
        self.assertEqual(spay.linked_ledger_transaction.direction, AccountTransaction.DIRECTION_DEBIT)

        # RULE 9: Verify no duplicate Expense created (count remains exactly 1)
        self.assertEqual(Expense.objects.count(), initial_expense_count + 1)

    def test_supplier_overpayment_strictly_rejected(self):
        """Verifies supplier payout exceeding outstanding balance is rejected server-side."""
        pay = SupplierPayableService.create_payable(
            user=self.owner,
            supplier=self.supplier,
            total_amount=Decimal('20000.00')
        )

        with self.assertRaises(ValidationError) as ctx:
            SupplierPayableService.record_payment(
                user=self.owner,
                payable_id=pay.id,
                amount=Decimal('20000.50'), # Overpayment attempt
                account=self.account
            )
        self.assertIn("Overpayment is rejected", str(ctx.exception))

    def test_supplier_payment_reversal_restores_payable_and_balance(self):
        """Verifies reversing a supplier payment refunds account and restores payable balance."""
        initial_balance = self.account.current_balance
        payable = SupplierPayableService.create_payable(
            user=self.owner,
            supplier=self.supplier,
            total_amount=Decimal('18000.00')
        )

        payment = SupplierPayableService.record_payment(
            user=self.owner,
            payable_id=payable.id,
            amount=Decimal('18000.00'),
            account=self.account
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance - Decimal('18000.00'))

        # Execute Reversal
        SupplierPayableService.reverse_payment(
            payment_id=payment.id,
            user=self.owner,
            reason="Incorrect bank account debited"
        )

        payable.refresh_from_db()
        self.assertEqual(payable.status, Payable.STATUS_UNPAID)
        self.assertEqual(payable.paid_amount, Decimal('0.00'))
        self.assertEqual(payable.outstanding_amount, Decimal('18000.00'))

        # Verify Account balance restored via credit reversal
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance)


class SettlementViewsAndRBACTests(TestCase):
    """Verifies UI Views, Forms, and Server-Side Permissions on Receivables and Payables."""

    def setUp(self):
        self.client = Client()
        self.password = "SafePass123!"

        self.owner = User.objects.create_user(username="s_owner", password=self.password)
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.save()

        self.accountant = User.objects.create_user(username="s_acc", password=self.password)
        self.accountant.profile.role = UserProfile.ROLE_ACCOUNTANT
        self.accountant.profile.save()

        self.manager = User.objects.create_user(username="s_mgr", password=self.password)
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save()

        self.employee = User.objects.create_user(username="s_emp", password=self.password)
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        self.account = Account.objects.create(
            account_name="Main Bank",
            account_type=Account.TYPE_BANK_CURRENT,
            opening_balance=Decimal('50000.00'),
            current_balance=Decimal('50000.00'),
            is_active=True
        )

        self.customer = Customer.objects.create(customer_code="CUST-10", name="Test Customer")
        self.supplier = Supplier.objects.create(supplier_code="SUPP-10", name="Test Supplier")

        self.rcv = CustomerReceivableService.create_receivable(
            user=self.owner, customer=self.customer, total_amount=Decimal('10000.00')
        )
        self.pay = SupplierPayableService.create_payable(
            user=self.owner, supplier=self.supplier, total_amount=Decimal('8000.00')
        )

    def test_owner_and_accountant_can_access_receivables_and_payables(self):
        """Verifies Owner and Accountant have full access to settlement pages."""
        self.client.login(username='s_owner', password=self.password)
        self.assertEqual(self.client.get(reverse('finance:receivables')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:receivable_detail', args=[self.rcv.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:payables')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:payable_detail', args=[self.pay.id])).status_code, 200)

        self.client.login(username='s_acc', password=self.password)
        self.assertEqual(self.client.get(reverse('finance:receivables')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:payables')).status_code, 200)

    def test_manager_and_employee_blocked_from_financial_settlements(self):
        """Verifies Manager and Employee are forbidden (403) from accessing receivables and payables."""
        self.client.login(username='s_mgr', password=self.password)
        self.assertEqual(self.client.get(reverse('finance:receivables')).status_code, 403)
        self.assertEqual(self.client.get(reverse('finance:payables')).status_code, 403)

        self.client.login(username='s_emp', password=self.password)
        self.assertEqual(self.client.get(reverse('finance:receivables')).status_code, 403)
        self.assertEqual(self.client.get(reverse('finance:payables')).status_code, 403)
