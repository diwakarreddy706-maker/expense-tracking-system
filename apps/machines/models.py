import datetime
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


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


class MachineBooking(models.Model):
    """
    Machine Booking & Dispatch Lifecycle (Phase 12.5).
    Operational scheduling and assignment for agricultural machinery.
    Strictly isolated from financial ledgers until Phase 14.
    """
    STATUS_PENDING = 'PENDING'
    STATUS_CONFIRMED = 'CONFIRMED'
    STATUS_DISPATCHED = 'DISPATCHED'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Confirmation'),
        (STATUS_CONFIRMED, 'Confirmed & Scheduled'),
        (STATUS_DISPATCHED, 'Dispatched to Field'),
        (STATUS_IN_PROGRESS, 'Work In Progress'),
        (STATUS_COMPLETED, 'Work Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    BILLING_TIME_HOURLY = 'TIME_HOURLY'
    BILLING_ACRE = 'ACRE'
    BILLING_PIECE = 'PIECE'

    BILLING_TYPE_CHOICES = [
        (BILLING_TIME_HOURLY, 'Time-Based (Hourly) - Harvester'),
        (BILLING_ACRE, 'Acre-Based - Tractor'),
        (BILLING_PIECE, 'Piece-Based - Tractor'),
    ]

    booking_code = models.CharField(max_length=30, unique=True, db_index=True)
    customer = models.ForeignKey(
        'finance.Customer',
        on_delete=models.PROTECT,
        related_name='machine_bookings'
    )
    machine_type = models.ForeignKey(
        MachineType,
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    machine = models.ForeignKey(
        'machines.Machine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings'
    )
    operator = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='machine_bookings'
    )
    work_date = models.DateField(default=timezone.now, db_index=True)
    requested_start_time = models.TimeField(null=True, blank=True)
    expected_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Estimated quantity (Acres or Pieces)"
    )
    expected_duration_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Estimated duration in hours"
    )
    billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOICES,
        default=BILLING_TIME_HOURLY,
        db_index=True
    )
    work_location = models.CharField(max_length=200, blank=True, null=True)
    village = models.CharField(max_length=100, blank=True, null=True)
    crop_description = models.CharField(max_length=150, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )
    dispatched_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    dispatch_notes = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_machine_bookings'
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'machine_bookings'
        verbose_name = 'Machine Booking'
        verbose_name_plural = 'Machine Bookings'
        ordering = ['-work_date', '-id']

    def __str__(self):
        machine_name = self.machine.name if self.machine else f"Requested {self.machine_type.name}"
        return f"{self.booking_code} - {self.customer.name} ({machine_name}) [{self.get_status_display()}]"


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

    booking = models.ForeignKey(
        MachineBooking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='work_entries'
    )
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


class MachineMaintenanceSchedule(models.Model):
    """
    Preventive Maintenance & Service Interval Schedule (Phase 15).
    Tracks intervals by meter reading (hours/km), calendar days, or both.
    """
    BASIS_METER = 'METER'
    BASIS_DATE = 'DATE'
    BASIS_BOTH = 'BOTH'

    SERVICE_BASIS_CHOICES = [
        (BASIS_METER, 'Meter-Based (Hours/KM)'),
        (BASIS_DATE, 'Calendar Date-Based'),
        (BASIS_BOTH, 'Both (Whichever comes first)'),
    ]

    STATUS_OK = 'OK'
    STATUS_DUE_SOON = 'DUE_SOON'
    STATUS_DUE = 'DUE'
    STATUS_OVERDUE = 'OVERDUE'

    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name='maintenance_schedules'
    )
    schedule_name = models.CharField(
        max_length=150,
        help_text="Service schedule title (e.g. 250 Hour Engine Oil & Filter Change)"
    )
    service_basis = models.CharField(
        max_length=10,
        choices=SERVICE_BASIS_CHOICES,
        default=BASIS_METER,
        db_index=True
    )
    service_interval_meter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Service interval in meter units (e.g. 250.00 hours or 5000.00 km)"
    )
    service_interval_days = models.IntegerField(
        null=True,
        blank=True,
        help_text="Service interval in calendar days (e.g. 90 days)"
    )
    last_service_date = models.DateField(null=True, blank=True)
    last_service_meter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Meter reading at last completed service"
    )
    next_service_date = models.DateField(null=True, blank=True)
    next_service_meter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Calculated next service meter reading"
    )
    warning_meter_before = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('25.00'),
        help_text="Trigger 'Due Soon' this many meter units before next service"
    )
    warning_days_before = models.IntegerField(
        default=7,
        help_text="Trigger 'Due Soon' this many days before next service date"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_maintenance_schedules'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'machine_maintenance_schedules'
        verbose_name = 'Maintenance Schedule'
        verbose_name_plural = 'Maintenance Schedules'
        ordering = ['machine', 'schedule_name']

    def __str__(self):
        return f"{self.machine.name} - {self.schedule_name}"

    def evaluate_status(self, current_meter=None, current_date=None):
        """
        Dynamically calculates schedule status: OK, DUE_SOON, DUE, OVERDUE.
        Does not mutate model state.
        """
        if not self.is_active:
            return {
                'status': 'INACTIVE',
                'remaining_meter': None,
                'remaining_days': None,
                'badge_class': 'bg-secondary',
                'meter_status': 'INACTIVE',
                'date_status': 'INACTIVE',
            }

        curr_m = current_meter if current_meter is not None else (self.machine.current_meter_reading or Decimal('0.00'))
        curr_d = current_date or timezone.now().date()
        if isinstance(curr_d, datetime.datetime):
            curr_d = curr_d.date()

        meter_status = self.STATUS_OK
        date_status = self.STATUS_OK
        remaining_meter = None
        remaining_days = None

        if self.service_basis in [self.BASIS_METER, self.BASIS_BOTH] and self.next_service_meter is not None:
            remaining_meter = self.next_service_meter - curr_m
            warn_threshold = self.next_service_meter - (self.warning_meter_before or Decimal('0.00'))
            if curr_m > self.next_service_meter:
                meter_status = self.STATUS_OVERDUE
            elif curr_m == self.next_service_meter:
                meter_status = self.STATUS_DUE
            elif curr_m >= warn_threshold:
                meter_status = self.STATUS_DUE_SOON
            else:
                meter_status = self.STATUS_OK

        if self.service_basis in [self.BASIS_DATE, self.BASIS_BOTH] and self.next_service_date is not None:
            delta_days = (self.next_service_date - curr_d).days
            remaining_days = delta_days
            warn_days = self.warning_days_before or 7
            if delta_days < 0:
                date_status = self.STATUS_OVERDUE
            elif delta_days == 0:
                date_status = self.STATUS_DUE
            elif delta_days <= warn_days:
                date_status = self.STATUS_DUE_SOON
            else:
                date_status = self.STATUS_OK

        # Combine statuses based on basis (most severe wins)
        severity_rank = {
            self.STATUS_OVERDUE: 4,
            self.STATUS_DUE: 3,
            self.STATUS_DUE_SOON: 2,
            self.STATUS_OK: 1,
        }

        if self.service_basis == self.BASIS_METER:
            overall = meter_status
        elif self.service_basis == self.BASIS_DATE:
            overall = date_status
        else: # BOTH
            overall = meter_status if severity_rank[meter_status] >= severity_rank[date_status] else date_status

        badge_class = {
            self.STATUS_OK: 'bg-success',
            self.STATUS_DUE_SOON: 'bg-warning text-dark',
            self.STATUS_DUE: 'bg-danger text-white',
            self.STATUS_OVERDUE: 'bg-danger text-white',
        }.get(overall, 'bg-secondary')

        return {
            'status': overall,
            'remaining_meter': remaining_meter,
            'remaining_days': remaining_days,
            'badge_class': badge_class,
            'meter_status': meter_status,
            'date_status': date_status,
        }


class MaintenanceJob(models.Model):
    """
    Unified Machinery Maintenance & Breakdown Job (Phase 15).
    Operational job tracking for preventive service, corrective repairs, and field breakdowns.
    Isolated from financial ledger; optionally posts to Expense as explicit user action.
    """
    TYPE_PREVENTIVE_SERVICE = 'PREVENTIVE_SERVICE'
    TYPE_BREAKDOWN_REPAIR = 'BREAKDOWN_REPAIR'
    TYPE_CORRECTIVE_REPAIR = 'CORRECTIVE_REPAIR'
    TYPE_INSPECTION = 'INSPECTION'
    TYPE_TYRE_SERVICE = 'TYRE_SERVICE'
    TYPE_ELECTRICAL = 'ELECTRICAL'
    TYPE_ENGINE = 'ENGINE'
    TYPE_HYDRAULIC = 'HYDRAULIC'
    TYPE_TRANSMISSION = 'TRANSMISSION'
    TYPE_OTHER = 'OTHER'

    MAINTENANCE_TYPE_CHOICES = [
        (TYPE_PREVENTIVE_SERVICE, 'Preventive Periodic Service'),
        (TYPE_BREAKDOWN_REPAIR, 'Field Breakdown Repair'),
        (TYPE_CORRECTIVE_REPAIR, 'Corrective / Scheduled Repair'),
        (TYPE_INSPECTION, 'Safety / Seasonal Inspection'),
        (TYPE_TYRE_SERVICE, 'Tyre & Wheel Service'),
        (TYPE_ELECTRICAL, 'Electrical & Wiring Repair'),
        (TYPE_ENGINE, 'Engine Overhaul / Service'),
        (TYPE_HYDRAULIC, 'Hydraulic System Repair'),
        (TYPE_TRANSMISSION, 'Transmission & Clutch Service'),
        (TYPE_OTHER, 'Other Maintenance'),
    ]

    STATUS_OPEN = 'OPEN'
    STATUS_DIAGNOSING = 'DIAGNOSING'
    STATUS_WAITING_FOR_PARTS = 'WAITING_FOR_PARTS'
    STATUS_IN_REPAIR = 'IN_REPAIR'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Reported / Open'),
        (STATUS_DIAGNOSING, 'Diagnosing Problem'),
        (STATUS_WAITING_FOR_PARTS, 'Waiting for Spare Parts'),
        (STATUS_IN_REPAIR, 'In Repair / Workshop'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    SEVERITY_LOW = 'LOW'
    SEVERITY_MEDIUM = 'MEDIUM'
    SEVERITY_HIGH = 'HIGH'
    SEVERITY_CRITICAL = 'CRITICAL'

    SEVERITY_CHOICES = [
        (SEVERITY_LOW, 'Low (Minor / Cosmetic)'),
        (SEVERITY_MEDIUM, 'Medium (Needs Attention)'),
        (SEVERITY_HIGH, 'High (Operational Impact)'),
        (SEVERITY_CRITICAL, 'Critical (Machine Stopped / Field Emergency)'),
    ]

    maintenance_code = models.CharField(max_length=30, unique=True, db_index=True)
    machine = models.ForeignKey(
        Machine,
        on_delete=models.PROTECT,
        related_name='maintenance_jobs'
    )
    maintenance_schedule = models.ForeignKey(
        MachineMaintenanceSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_jobs',
        help_text="Optional link to preventive service schedule"
    )
    maintenance_type = models.CharField(
        max_length=30,
        choices=MAINTENANCE_TYPE_CHOICES,
        default=TYPE_PREVENTIVE_SERVICE,
        db_index=True
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        db_index=True
    )

    # Dates and Meter
    reported_date = models.DateField(default=timezone.now, db_index=True)
    started_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    meter_reading = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Current meter reading at time of maintenance/breakdown"
    )

    # Operational Descriptions
    problem_description = models.TextField(help_text="Reported issue or scheduled service reason")
    diagnosis = models.TextField(blank=True, null=True, help_text="Mechanic/Workshop diagnosis")
    work_performed = models.TextField(blank=True, null=True, help_text="Summary of repairs and services completed")

    # Breakdown-specific attributes
    breakdown_location = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Field / Village / Road location of breakdown"
    )
    breakdown_time = models.DateTimeField(null=True, blank=True)
    machine_stopped = models.BooleanField(
        default=False,
        db_index=True,
        help_text="If True, machine is halted and must be blocked from operational dispatch"
    )
    severity = models.CharField(
        max_length=15,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_MEDIUM
    )

    # External Supplier / Workshop
    supplier = models.ForeignKey(
        'finance.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_jobs',
        help_text="External workshop or parts vendor"
    )
    external_workshop_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Name of external repair workshop if not registered as Supplier"
    )

    # Authoritative Cost Tracking (Decimal arithmetic only)
    parts_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Sum of all spare parts used"
    )
    labor_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="In-house or external labor cost"
    )
    external_service_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="External workshop / lathe / specialist charges"
    )
    other_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Towing, transport, oils, misc expenses"
    )
    total_maintenance_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Authoritative total = parts + labor + external + other"
    )

    # Next Service metrics computed upon completion
    next_service_date = models.DateField(null=True, blank=True)
    next_service_meter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Explicit Financial Integration
    linked_expense = models.OneToOneField(
        'expenses.Expense',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_job',
        help_text="Linked financial Expense record if explicitly posted by Owner/Accountant"
    )

    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_maintenance_jobs'
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'machine_maintenance_jobs'
        verbose_name = 'Maintenance Job'
        verbose_name_plural = 'Maintenance Jobs'
        ordering = ['-reported_date', '-id']

    def __str__(self):
        return f"{self.maintenance_code} - {self.machine.name} ({self.get_maintenance_type_display()}) [{self.get_status_display()}]"

    @property
    def is_active_blocking(self) -> bool:
        """Returns True if this job represents an active unresolved repair that blocks machine operation."""
        if self.is_deleted or self.status in [self.STATUS_COMPLETED, self.STATUS_CANCELLED]:
            return False
        return self.machine_stopped or self.status in [
            self.STATUS_IN_REPAIR,
            self.STATUS_DIAGNOSING,
            self.STATUS_WAITING_FOR_PARTS
        ]


class MaintenancePartUsage(models.Model):
    """
    Spare parts and consumables consumed during machinery maintenance (Phase 15).
    Strictly machinery maintenance domain (NOT general retail/shop inventory).
    """
    maintenance_job = models.ForeignKey(
        MaintenanceJob,
        on_delete=models.CASCADE,
        related_name='part_usages'
    )
    part_name = models.CharField(max_length=150, db_index=True, help_text="Name/description of spare part (e.g. Engine Oil Filter)")
    part_number = models.CharField(max_length=100, blank=True, null=True, help_text="Manufacturer / OEM part number")
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        help_text="Quantity of parts/litres consumed"
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Cost per unit in INR"
    )
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Authoritative item total = quantity * unit_cost"
    )
    supplier = models.ForeignKey(
        'finance.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_part_usages',
        help_text="Vendor who supplied this spare part"
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'machine_maintenance_part_usages'
        verbose_name = 'Maintenance Part Usage'
        verbose_name_plural = 'Maintenance Part Usages'
        ordering = ['id']

    def __str__(self):
        return f"{self.part_name} ({self.quantity} @ ₹{self.unit_cost} = ₹{self.total_cost})"
