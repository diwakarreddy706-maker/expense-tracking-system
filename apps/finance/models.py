from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal


class Account(models.Model):
    """
    Business Financial Account master (Cash boxes, Bank accounts, UPI wallets).
    Defined in DATABASE_SCHEMA.md.
    """
    TYPE_CASH = 'CASH'
    TYPE_BANK_SAVINGS = 'BANK_SAVINGS'
    TYPE_BANK_CURRENT = 'BANK_CURRENT'
    TYPE_UPI_WALLET = 'UPI_WALLET'
    TYPE_PETTY_CASH = 'PETTY_CASH'

    ACCOUNT_TYPE_CHOICES = [
        (TYPE_CASH, 'Cash In Hand / Cash Box'),
        (TYPE_BANK_SAVINGS, 'Bank Savings Account'),
        (TYPE_BANK_CURRENT, 'Bank Current Account'),
        (TYPE_UPI_WALLET, 'UPI / Digital Wallet'),
        (TYPE_PETTY_CASH, 'Petty Cash Box'),
    ]

    account_name = models.CharField(max_length=100, unique=True, db_index=True)
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        default=TYPE_BANK_CURRENT,
        db_index=True
    )
    account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    opening_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    opening_balance_date = models.DateField(default=timezone.now)
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Derived cached balance. Single source of truth is account_transactions."
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts'
        verbose_name = 'Business Account'
        verbose_name_plural = 'Business Accounts'
        ordering = ['account_name']

    def __str__(self):
        return f"{self.account_name} ({self.get_account_type_display()})"

    @property
    def masked_account_number(self):
        """Returns masked account number for general UI presentation (e.g. XXXX XXXX 4091)."""
        if not self.account_number:
            return "--"
        clean = self.account_number.strip()
        if len(clean) <= 4:
            return clean
        masked = 'X' * (len(clean) - 4) + clean[-4:]
        if clean.isdigit():
            chunks = [masked[i:i+4] for i in range(0, len(masked), 4)]
            return ' '.join(chunks)
        return masked


class Customer(models.Model):
    """
    Customer master entity for agricultural services and machinery rental clients.
    Defined in DATABASE_SCHEMA.md.
    """
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]

    customer_code = models.CharField(max_length=30, unique=True, db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    location_address = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['name']

    def __str__(self):
        return f"{self.customer_code} - {self.name}"


class Supplier(models.Model):
    """
    Supplier / Vendor master entity for fuel pumps, spare parts, and workshops.
    Defined in DATABASE_SCHEMA.md.
    """
    TYPE_FUEL_PUMP = 'FUEL_PUMP'
    TYPE_SPARE_PARTS = 'SPARE_PARTS'
    TYPE_WORKSHOP = 'WORKSHOP'
    TYPE_FERTILIZER = 'FERTILIZER'
    TYPE_OTHER = 'OTHER'

    SUPPLIER_TYPE_CHOICES = [
        (TYPE_FUEL_PUMP, 'Fuel Pump / Petroleum Outlet'),
        (TYPE_SPARE_PARTS, 'Spare Parts Vendor'),
        (TYPE_WORKSHOP, 'Repair Workshop'),
        (TYPE_FERTILIZER, 'Fertilizer & Seeds Dealer'),
        (TYPE_OTHER, 'General Supplier'),
    ]

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]

    supplier_code = models.CharField(max_length=30, unique=True, db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    supplier_type = models.CharField(
        max_length=30,
        choices=SUPPLIER_TYPE_CHOICES,
        default=TYPE_SPARE_PARTS,
        db_index=True
    )
    phone = models.CharField(max_length=15, blank=True, null=True)
    location_address = models.CharField(max_length=255, blank=True, null=True)
    payment_terms = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suppliers'
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'
        ordering = ['name']

    def __str__(self):
        return f"{self.supplier_code} - {self.name} ({self.get_supplier_type_display()})"


class AccountTransaction(models.Model):
    """
    CENTRAL FINANCIAL LEDGER.
    The single authoritative source of truth for all account balance movements.
    Defined in DATABASE_SCHEMA.md.
    """
    TYPE_OPENING_BALANCE = 'OPENING_BALANCE'
    TYPE_INCOME = 'INCOME'
    TYPE_EXPENSE = 'EXPENSE'
    TYPE_RECEIVABLE_PAYMENT = 'RECEIVABLE_PAYMENT'
    TYPE_PAYABLE_PAYMENT = 'PAYABLE_PAYMENT'
    TYPE_EMPLOYEE_PAYMENT = 'EMPLOYEE_PAYMENT'
    TYPE_TRANSFER_IN = 'TRANSFER_IN'
    TYPE_TRANSFER_OUT = 'TRANSFER_OUT'
    TYPE_ADJUSTMENT = 'ADJUSTMENT'
    TYPE_REVERSAL = 'REVERSAL'

    TRANSACTION_TYPE_CHOICES = [
        (TYPE_OPENING_BALANCE, 'Opening Balance Setup'),
        (TYPE_INCOME, 'Direct Income / Revenue'),
        (TYPE_EXPENSE, 'Operational / General Expense'),
        (TYPE_RECEIVABLE_PAYMENT, 'Customer Receivable Payment'),
        (TYPE_PAYABLE_PAYMENT, 'Supplier Payable Payment'),
        (TYPE_EMPLOYEE_PAYMENT, 'Employee Wage / Advance Payout'),
        (TYPE_TRANSFER_IN, 'Inter-Account Transfer (Inflow)'),
        (TYPE_TRANSFER_OUT, 'Inter-Account Transfer (Outflow)'),
        (TYPE_ADJUSTMENT, 'Audit / Ledger Adjustment'),
        (TYPE_REVERSAL, 'Transaction Reversal / Correction'),
    ]

    DIRECTION_DEBIT = 'DEBIT'   # Outflow from account
    DIRECTION_CREDIT = 'CREDIT' # Inflow into account

    DIRECTION_CHOICES = [
        (DIRECTION_DEBIT, 'Debit (Money Out)'),
        (DIRECTION_CREDIT, 'Credit (Money In)'),
    ]

    account = models.ForeignKey(Account, on_delete=models.RESTRICT, related_name='ledger_transactions')
    transaction_date = models.DateField(default=timezone.now, db_index=True)
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPE_CHOICES, db_index=True)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    reference_type = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. Expense, CustomerPayment, FuelEntry")
    reference_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_transactions')
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'account_transactions'
        verbose_name = 'Account Ledger Transaction'
        verbose_name_plural = 'Account Ledger Transactions'
        ordering = ['-transaction_date', '-id']

    def __str__(self):
        return f"[{self.transaction_date}] {self.direction} ₹{self.amount} ({self.transaction_type}) on {self.account.account_name}"
