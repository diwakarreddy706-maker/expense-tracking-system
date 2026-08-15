from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal


class FuelEntry(models.Model):
    """
    Fuel & Lubricant Log for Agricultural Machinery & Equipment.
    Enforces Rule 1 (Decimal precision) and Rule 9 (Every Fuel Entry has a 1:1 linked Expense).
    Defined in DATABASE_SCHEMA.md.
    """
    TYPE_DIESEL = 'DIESEL'
    TYPE_PETROL = 'PETROL'
    TYPE_ENGINE_OIL = 'ENGINE_OIL'
    TYPE_HYDRAULIC_OIL = 'HYDRAULIC_OIL'

    FUEL_TYPE_CHOICES = [
        (TYPE_DIESEL, 'Diesel (High-Speed Diesel)'),
        (TYPE_PETROL, 'Petrol / Gasoline'),
        (TYPE_ENGINE_OIL, 'Engine Oil (Lubricant)'),
        (TYPE_HYDRAULIC_OIL, 'Hydraulic Oil / Transmission Fluid'),
    ]

    METHOD_CASH = 'CASH'
    METHOD_BANK_TRANSFER = 'BANK_TRANSFER'
    METHOD_UPI = 'UPI'
    METHOD_CHEQUE = 'CHEQUE'
    METHOD_CREDIT = 'CREDIT'

    PAYMENT_METHOD_CHOICES = [
        (METHOD_CASH, 'Cash'),
        (METHOD_BANK_TRANSFER, 'Bank Transfer / NEFT'),
        (METHOD_UPI, 'UPI / QR Code'),
        (METHOD_CHEQUE, 'Cheque'),
        (METHOD_CREDIT, 'Credit / Pay Later (Supplier Payable)'),
    ]

    fuel_code = models.CharField(max_length=30, unique=True, db_index=True)
    date = models.DateField(default=timezone.now, db_index=True)
    machine = models.ForeignKey(
        'machines.Machine',
        on_delete=models.PROTECT,
        related_name='fuel_entries'
    )
    fuel_type = models.CharField(
        max_length=20,
        choices=FUEL_TYPE_CHOICES,
        default=TYPE_DIESEL,
        db_index=True
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Volume in Litres"
    )
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Rate per Litre in INR"
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Authoritative total = quantity * unit_price (calculated server-side)"
    )
    supplier = models.ForeignKey(
        'finance.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fuel_entries'
    )
    account = models.ForeignKey(
        'finance.Account',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name='fuel_entries'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=METHOD_CASH,
        db_index=True
    )
    operator = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fuel_entries'
    )
    meter_reading = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Machine meter reading at refueling (Hours or KM)"
    )
    linked_expense = models.OneToOneField(
        'expenses.Expense',
        on_delete=models.RESTRICT,
        related_name='fuel_entry',
        help_text="Enforces 1:1 database constraint between Fuel Entry and Expense"
    )
    reference_no = models.CharField(max_length=100, blank=True, null=True, help_text="Bill / Slip / Invoice No.")
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_fuel_entries'
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fuel_entries'
        verbose_name = 'Fuel & Lubricant Entry'
        verbose_name_plural = 'Fuel & Lubricant Entries'
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.fuel_code} - {self.machine.name} ({self.quantity}L {self.get_fuel_type_display()}) - ₹{self.total_amount}"
