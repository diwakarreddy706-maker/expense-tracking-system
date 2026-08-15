from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal


class ExpenseCategory(models.Model):
    """
    Hierarchical classification of business expenses.
    Defined in DATABASE_SCHEMA.md.
    """
    name = models.CharField(max_length=100, unique=True, db_index=True)
    code = models.CharField(max_length=30, unique=True, db_index=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        help_text="Optional parent category for hierarchical grouping"
    )
    color_hex = models.CharField(max_length=7, default='#10B981', help_text="Hex color for UI charts")
    icon_class = models.CharField(max_length=50, default='bi-receipt', help_text="Bootstrap icon class")
    is_active = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'expense_categories'
        verbose_name = 'Expense Category'
        verbose_name_plural = 'Expense Categories'
        ordering = ['name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name} ({self.code})"
        return f"{self.name} ({self.code})"


class Expense(models.Model):
    """
    General & Operational Business Expenses.
    Defined in DATABASE_SCHEMA.md.
    """
    METHOD_CASH = 'CASH'
    METHOD_BANK_TRANSFER = 'BANK_TRANSFER'
    METHOD_UPI = 'UPI'
    METHOD_CHEQUE = 'CHEQUE'
    METHOD_CREDIT = 'CREDIT'

    PAYMENT_METHOD_CHOICES = [
        (METHOD_CASH, 'Cash'),
        (METHOD_BANK_TRANSFER, 'Bank Transfer / NEFT / RTGS'),
        (METHOD_UPI, 'UPI / QR Code'),
        (METHOD_CHEQUE, 'Cheque'),
        (METHOD_CREDIT, 'Credit / Pay Later (Payable)'),
    ]

    SEGMENT_GENERAL = 'GENERAL'
    SEGMENT_FARM_OPERATIONS = 'FARM_OPERATIONS'
    SEGMENT_MACHINERY_RENTAL = 'MACHINERY_RENTAL'
    SEGMENT_WORKSHOP_REPAIRS = 'WORKSHOP_REPAIRS'
    SEGMENT_SHOP_RETAIL = 'SHOP_RETAIL'
    SEGMENT_GENERAL_ADMIN = 'GENERAL_ADMIN'

    BUSINESS_SEGMENT_CHOICES = [
        (SEGMENT_GENERAL, 'General Business'),
        (SEGMENT_FARM_OPERATIONS, 'Farm Operations / Cultivation'),
        (SEGMENT_MACHINERY_RENTAL, 'Machinery Custom Hiring Hub'),
        (SEGMENT_WORKSHOP_REPAIRS, 'Workshop & Service Center'),
        (SEGMENT_SHOP_RETAIL, 'Agri Inputs Retail Store'),
        (SEGMENT_GENERAL_ADMIN, 'Administrative & Overhead'),
    ]

    expense_code = models.CharField(max_length=30, unique=True, db_index=True)
    expense_date = models.DateField(default=timezone.now, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.RESTRICT,
        related_name='expenses'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=METHOD_CASH,
        db_index=True
    )
    account = models.ForeignKey(
        'finance.Account',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name='expenses'
    )
    business_segment = models.CharField(
        max_length=30,
        choices=BUSINESS_SEGMENT_CHOICES,
        default=SEGMENT_GENERAL,
        db_index=True
    )
    machine = models.ForeignKey(
        'machines.Machine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tagged_expenses'
    )
    supplier = models.ForeignKey(
        'finance.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    reference_no = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_quick_expense = models.BooleanField(default=False)
    is_reversed = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_expenses'
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'expenses'
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'
        ordering = ['-expense_date', '-id']

    def __str__(self):
        return f"{self.expense_code} - ₹{self.amount} ({self.category.name})"
