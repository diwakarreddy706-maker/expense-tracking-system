from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal


class Employee(models.Model):
    """
    Agricultural Staff and Operator Registry.
    Defined in DATABASE_SCHEMA.md.
    """
    ROLE_TRACTOR_DRIVER = 'TRACTOR_DRIVER'
    ROLE_HARVESTER_OPERATOR = 'HARVESTER_OPERATOR'
    ROLE_WORKSHOP_MECHANIC = 'WORKSHOP_MECHANIC'
    ROLE_SHOP_STAFF = 'SHOP_STAFF'
    ROLE_ACCOUNTANT = 'ACCOUNTANT'
    ROLE_MANAGER = 'MANAGER'
    ROLE_DAILY_LABOR = 'DAILY_LABOR'

    ROLE_CHOICES = [
        (ROLE_TRACTOR_DRIVER, 'Tractor Driver / Machine Operator'),
        (ROLE_HARVESTER_OPERATOR, 'Harvester Specialist'),
        (ROLE_WORKSHOP_MECHANIC, 'Workshop Mechanic / Technician'),
        (ROLE_SHOP_STAFF, 'Retail & Shop Staff'),
        (ROLE_ACCOUNTANT, 'Accountant / Cashier'),
        (ROLE_MANAGER, 'Operations Manager / Supervisor'),
        (ROLE_DAILY_LABOR, 'Daily Field Labor'),
    ]

    WAGE_MONTHLY = 'MONTHLY_SALARY'
    WAGE_DAILY = 'DAILY_WAGE'
    WAGE_PER_ACRE = 'PER_ACRE_COMMISSION'

    WAGE_TYPE_CHOICES = [
        (WAGE_MONTHLY, 'Monthly Fixed Salary'),
        (WAGE_DAILY, 'Daily Wage (Per Day Rate)'),
        (WAGE_PER_ACRE, 'Per Acre Commission'),
    ]

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_ON_LEAVE = 'ON_LEAVE'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_ON_LEAVE, 'On Leave'),
    ]

    employee_code = models.CharField(max_length=30, unique=True, db_index=True)
    full_name = models.CharField(max_length=100, db_index=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default=ROLE_TRACTOR_DRIVER,
        db_index=True
    )
    wage_type = models.CharField(
        max_length=20,
        choices=WAGE_TYPE_CHOICES,
        default=WAGE_DAILY,
        db_index=True
    )
    base_rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Base rate in INR (Monthly salary, daily wage, or per-acre rate)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True
    )
    joining_date = models.DateField(default=timezone.now)
    emergency_contact = models.CharField(max_length=50, blank=True, null=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employees'
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        ordering = ['full_name']

    def __str__(self):
        return f"{self.employee_code} - {self.full_name} ({self.get_role_display()})"


class EmployeePayment(models.Model):
    """
    Employee Wage Accruals, Advance Payouts, Salary Settlements, and Bonuses.
    Defined in DATABASE_SCHEMA.md.
    """
    TYPE_SALARY_ACCRUAL = 'SALARY_ACCRUAL'
    TYPE_ADVANCE_PAYOUT = 'ADVANCE_PAYOUT'
    TYPE_SALARY_SETTLEMENT = 'SALARY_SETTLEMENT'
    TYPE_BONUS = 'BONUS'

    PAYMENT_TYPE_CHOICES = [
        (TYPE_SALARY_ACCRUAL, 'Salary / Wage Accrual (Liability Earned)'),
        (TYPE_ADVANCE_PAYOUT, 'Advance Payout (Money Out)'),
        (TYPE_SALARY_SETTLEMENT, 'Salary Settlement Payout (Money Out)'),
        (TYPE_BONUS, 'Performance Bonus / Festival Payout (Money Out)'),
    ]

    METHOD_CASH = 'CASH'
    METHOD_BANK_TRANSFER = 'BANK_TRANSFER'
    METHOD_UPI = 'UPI'
    METHOD_CHEQUE = 'CHEQUE'

    PAYMENT_METHOD_CHOICES = [
        (METHOD_CASH, 'Cash'),
        (METHOD_BANK_TRANSFER, 'Bank Transfer / NEFT'),
        (METHOD_UPI, 'UPI Transfer'),
        (METHOD_CHEQUE, 'Cheque'),
    ]

    payment_code = models.CharField(max_length=30, unique=True, db_index=True)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    payment_type = models.CharField(
        max_length=30,
        choices=PAYMENT_TYPE_CHOICES,
        db_index=True
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Financial amount in INR"
    )
    date = models.DateField(default=timezone.now, db_index=True)
    account = models.ForeignKey(
        'finance.Account',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name='employee_payouts'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=METHOD_CASH,
        db_index=True
    )
    linked_ledger_transaction = models.OneToOneField(
        'finance.AccountTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_payment',
        help_text="Linked central ledger entry for actual bank/cash movements"
    )
    reference_no = models.CharField(max_length=100, blank=True, null=True, help_text="Voucher / Bank UTR / Receipt No.")
    notes = models.TextField(blank=True, null=True)
    is_reversed = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_employee_payments'
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employee_payments'
        verbose_name = 'Employee Wage / Payment'
        verbose_name_plural = 'Employee Wages & Payments'
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.payment_code} - {self.employee.full_name} ({self.get_payment_type_display()}): ₹{self.amount}"
