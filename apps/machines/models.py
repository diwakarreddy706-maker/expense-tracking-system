from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal


class MachineType(models.Model):
    """
    Equipment classification categories (e.g. Tractor, Combine Harvester).
    Defined in DATABASE_SCHEMA.md.
    """
    name = models.CharField(max_length=50, unique=True, db_index=True)
    code = models.CharField(max_length=30, unique=True, db_index=True)

    class Meta:
        db_table = 'machine_types'
        verbose_name = 'Machine Type'
        verbose_name_plural = 'Machine Types'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Machine(models.Model):
    """
    Agricultural Machinery & Equipment Master.
    Defined in DATABASE_SCHEMA.md.
    """
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_UNDER_MAINTENANCE = 'UNDER_MAINTENANCE'
    STATUS_IDLE = 'IDLE'
    STATUS_DECOMMISSIONED = 'DECOMMISSIONED'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active / Ready for Work'),
        (STATUS_UNDER_MAINTENANCE, 'Under Maintenance / In Workshop'),
        (STATUS_IDLE, 'Idle / Parked'),
        (STATUS_DECOMMISSIONED, 'Decommissioned / Retired'),
    ]

    METER_HOURS = 'HOURS'
    METER_KM = 'KM'

    METER_UNIT_CHOICES = [
        (METER_HOURS, 'Hour Meter (Hours)'),
        (METER_KM, 'Odometer (Kilometers)'),
    ]

    machine_code = models.CharField(max_length=30, unique=True, db_index=True)
    name = models.CharField(max_length=100, help_text="Equipment name / Model (e.g. John Deere 5310)")
    machine_type = models.ForeignKey(
        MachineType,
        on_delete=models.PROTECT,
        related_name='machines'
    )
    registration_no = models.CharField(max_length=50, blank=True, null=True, unique=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True
    )
    default_operator = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_machines'
    )
    current_meter_reading = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Current meter reading (Hour meter or Odometer)"
    )
    meter_unit = models.CharField(
        max_length=10,
        choices=METER_UNIT_CHOICES,
        default=METER_HOURS,
        db_index=True
    )
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'machines'
        verbose_name = 'Machine'
        verbose_name_plural = 'Machines'
        ordering = ['machine_code']

    def __str__(self):
        return f"{self.machine_code} - {self.name} ({self.get_status_display()})"


class MachineWorkEntry(models.Model):
    """
    Machine Work & Billing Entry (Phase 12.4).
    Operational and commercial field work log for Harvesters (hourly/time-based)
    and Tractors (acre/piece-based).
    Strictly isolated from central ledger and invoicing.
    """
    BILLING_TIME_HOURLY = 'TIME_HOURLY'
    BILLING_ACRE = 'ACRE'
    BILLING_PIECE = 'PIECE'

    BILLING_TYPE_CHOICES = [
        (BILLING_TIME_HOURLY, 'Time-Based (Hourly) - Harvester'),
        (BILLING_ACRE, 'Acre-Based - Tractor'),
        (BILLING_PIECE, 'Piece-Based - Tractor'),
    ]

    work_code = models.CharField(max_length=30, unique=True, db_index=True)
    work_date = models.DateField(default=timezone.now, db_index=True)
    machine = models.ForeignKey(
        'machines.Machine',
        on_delete=models.PROTECT,
        related_name='work_entries'
    )
    customer = models.ForeignKey(
        'finance.Customer',
        on_delete=models.PROTECT,
        related_name='machine_work_entries'
    )
    operator = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='machine_work_entries'
    )
    billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOICES,
        default=BILLING_TIME_HOURLY,
        db_index=True
    )

    # Harvester Time-Based Fields
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    break_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Break duration in hours"
    )
    net_working_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Calculated net working hours = (end_time - start_time) - break_hours"
    )
    hourly_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Commercial rate per hour in INR"
    )

    # Tractor Unit-Based Fields
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Number of Acres or Pieces"
    )
    unit_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Rate per unit (Acre/Piece) in INR"
    )

    # Commercial Total
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Authoritative total bill amount in INR"
    )

    # Machine Hour-Meter Tracking (Equipment & Service Usage - Independent of Billing)
    start_meter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Machine meter reading at start of work"
    )
    end_meter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Machine meter reading at end of work"
    )
    meter_difference = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Machine usage delta = end_meter - start_meter (for service/maintenance only)"
    )

    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_machine_work_entries'
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'machine_work_entries'
        verbose_name = 'Machine Work Entry'
        verbose_name_plural = 'Machine Work Entries'
        ordering = ['-work_date', '-id']

    def __str__(self):
        return f"{self.work_code} - {self.machine.name} ({self.customer.name}) - ₹{self.total_amount}"
