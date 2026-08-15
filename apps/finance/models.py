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
    reference_type = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. Expense, CustomerPayment, SupplierPayment, FuelEntry")
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


class Receivable(models.Model):
    """
    Customer Billed Inflows (Money owed to the business by a customer).
    Defined in DATABASE_SCHEMA.md.
    """
    STATUS_UNPAID = 'UNPAID'
    STATUS_PARTIAL = 'PARTIAL'
    STATUS_PAID = 'PAID'

    STATUS_CHOICES = [
        (STATUS_UNPAID, 'Unpaid'),
        (STATUS_PARTIAL, 'Partially Paid'),
        (STATUS_PAID, 'Fully Paid / Settled'),
    ]

    receivable_code = models.CharField(max_length=30, unique=True, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.RESTRICT, related_name='receivables')
    invoice_no = models.CharField(max_length=50, blank=True, null=True, help_text="Bill / Invoice Number")
    bill_date = models.DateField(default=timezone.now, db_index=True)
    due_date = models.DateField(blank=True, null=True, db_index=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    received_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNPAID, db_index=True)
    notes = models.TextField(blank=True, null=True)
    is_reversed = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_receivables')
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'receivables'
        verbose_name = 'Customer Receivable'
        verbose_name_plural = 'Customer Receivables'
        ordering = ['-bill_date', '-id']

    def __str__(self):
        return f"{self.receivable_code} - {self.customer.name}: ₹{self.received_amount}/₹{self.total_amount} ({self.get_status_display()})"

    @property
    def outstanding_amount(self) -> Decimal:
        return (self.total_amount - self.received_amount).quantize(Decimal('0.01'))


class CustomerPayment(models.Model):
    """
    Customer Receivable Payment Settlement History.
    Credits business account; settles receivable; does NOT create duplicate revenue.
    Defined in DATABASE_SCHEMA.md.
    """
    METHOD_CASH = 'CASH'
    METHOD_BANK_TRANSFER = 'BANK_TRANSFER'
    METHOD_UPI = 'UPI'
    METHOD_CHEQUE = 'CHEQUE'

    PAYMENT_METHOD_CHOICES = [
        (METHOD_CASH, 'Cash'),
        (METHOD_BANK_TRANSFER, 'Bank Transfer / NEFT / RTGS'),
        (METHOD_UPI, 'UPI / QR Payment'),
        (METHOD_CHEQUE, 'Cheque'),
    ]

    payment_code = models.CharField(max_length=30, unique=True, db_index=True)
    receivable = models.ForeignKey(Receivable, on_delete=models.RESTRICT, related_name='payments')
    account = models.ForeignKey(Account, on_delete=models.RESTRICT, related_name='customer_receipts')
    payment_date = models.DateField(default=timezone.now, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default=METHOD_CASH, db_index=True)
    linked_ledger_transaction = models.OneToOneField(
        AccountTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_payment',
        help_text="Linked central ledger inflow entry"
    )
    reference_no = models.CharField(max_length=100, blank=True, null=True, help_text="UTR / Receipt / Cheque No.")
    notes = models.TextField(blank=True, null=True)
    is_reversed = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_customer_payments')
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customer_payments'
        verbose_name = 'Customer Payment'
        verbose_name_plural = 'Customer Payments'
        ordering = ['-payment_date', '-id']

    def __str__(self):
        return f"{self.payment_code} - {self.receivable.customer.name}: ₹{self.amount} via {self.account.account_name}"


class Payable(models.Model):
    """
    Supplier / Vendor Obligations (Money owed by the business to a supplier).
    Defined in DATABASE_SCHEMA.md.
    """
    STATUS_UNPAID = 'UNPAID'
    STATUS_PARTIAL = 'PARTIAL'
    STATUS_PAID = 'PAID'

    STATUS_CHOICES = [
        (STATUS_UNPAID, 'Unpaid'),
        (STATUS_PARTIAL, 'Partially Paid'),
        (STATUS_PAID, 'Fully Paid / Settled'),
    ]

    payable_code = models.CharField(max_length=30, unique=True, db_index=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.RESTRICT, related_name='payables')
    bill_no = models.CharField(max_length=50, blank=True, null=True, help_text="Vendor Invoice / Bill No.")
    bill_date = models.DateField(default=timezone.now, db_index=True)
    due_date = models.DateField(blank=True, null=True, db_index=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNPAID, db_index=True)
    linked_expense = models.ForeignKey(
        'expenses.Expense',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_payables',
        help_text="Originating credit expense (if created via credit purchase)"
    )
    notes = models.TextField(blank=True, null=True)
    is_reversed = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_payables')
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payables'
        verbose_name = 'Supplier Payable'
        verbose_name_plural = 'Supplier Payables'
        ordering = ['-bill_date', '-id']

    def __str__(self):
        return f"{self.payable_code} - {self.supplier.name}: ₹{self.paid_amount}/₹{self.total_amount} ({self.get_status_display()})"

    @property
    def outstanding_amount(self) -> Decimal:
        return (self.total_amount - self.paid_amount).quantize(Decimal('0.01'))


class SupplierPayment(models.Model):
    """
    Supplier Payable Payment Settlement History.
    Debits business account; settles payable; does NOT create duplicate expense.
    Defined in DATABASE_SCHEMA.md.
    """
    METHOD_CASH = 'CASH'
    METHOD_BANK_TRANSFER = 'BANK_TRANSFER'
    METHOD_UPI = 'UPI'
    METHOD_CHEQUE = 'CHEQUE'

    PAYMENT_METHOD_CHOICES = [
        (METHOD_CASH, 'Cash'),
        (METHOD_BANK_TRANSFER, 'Bank Transfer / NEFT / RTGS'),
        (METHOD_UPI, 'UPI Transfer'),
        (METHOD_CHEQUE, 'Cheque'),
    ]

    payment_code = models.CharField(max_length=30, unique=True, db_index=True)
    payable = models.ForeignKey(Payable, on_delete=models.RESTRICT, related_name='payments')
    account = models.ForeignKey(Account, on_delete=models.RESTRICT, related_name='supplier_payouts')
    payment_date = models.DateField(default=timezone.now, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default=METHOD_BANK_TRANSFER, db_index=True)
    linked_ledger_transaction = models.OneToOneField(
        AccountTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_payment',
        help_text="Linked central ledger debit entry"
    )
    reference_no = models.CharField(max_length=100, blank=True, null=True, help_text="UTR / Cheque / Voucher Ref")
    notes = models.TextField(blank=True, null=True)
    is_reversed = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_supplier_payments')
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'supplier_payments'
        verbose_name = 'Supplier Payment'
        verbose_name_plural = 'Supplier Payments'
        ordering = ['-payment_date', '-id']

    def __str__(self):
        return f"{self.payment_code} - {self.payable.supplier.name}: ₹{self.amount} from {self.account.account_name}"
