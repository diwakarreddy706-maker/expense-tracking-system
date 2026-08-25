from django import forms
from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import (
    Machine, MachineType, MachineBooking, MachineWorkEntry,
    MachineMaintenanceSchedule, MaintenanceJob, MaintenancePartUsage
)
from apps.finance.models import Customer, Supplier, Account
from apps.expenses.models import ExpenseCategory, Expense
from apps.employees.models import Employee
from .services.work_service import WorkService
from .services.booking_service import BookingService
from .services.maintenance_service import MaintenanceService


class MachineForm(forms.ModelForm):
    """Form for Agricultural Machinery & Equipment master."""
    class Meta:
        model = Machine
        fields = [
            'machine_code', 'name', 'machine_type', 'registration_no',
            'status', 'default_operator', 'current_meter_reading',
            'meter_unit', 'purchase_date', 'purchase_price', 'is_active'
        ]
        widgets = {
            'machine_code': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. MCH-TRAC-01'}),
            'name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Model Name (e.g. John Deere 5310)'}),
            'machine_type': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'registration_no': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'RTO Registration No.'}),
            'status': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'default_operator': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'current_meter_reading': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01'}),
            'meter_unit': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MachineTypeForm(forms.ModelForm):
    """Form for Equipment Types."""
    class Meta:
        model = MachineType
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Tractor, Combine Harvester'}),
            'code': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. TRACTOR'}),
        }


class MachineBookingForm(forms.ModelForm):
    """
    Form for Creating and Editing Machine Bookings (Phase 12.5).
    """
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.filter(is_deleted=False, status=Customer.STATUS_ACTIVE),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'customerSelect'})
    )
    machine_type = forms.ModelChoiceField(
        queryset=MachineType.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'machineTypeSelect'})
    )
    machine = forms.ModelChoiceField(
        queryset=Machine.objects.filter(is_deleted=False, is_active=True).exclude(
            status__in=[Machine.STATUS_UNDER_MAINTENANCE, Machine.STATUS_DECOMMISSIONED]
        ),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'machineSelect'})
    )
    operator = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_deleted=False, status=Employee.STATUS_ACTIVE),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'operatorSelect'})
    )
    requested_start_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'time', 'id': 'requestedStartTime'})
    )
    expected_quantity = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'expectedQuantity', 'placeholder': '0.00'})
    )
    expected_duration_hours = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'expectedDurationHours', 'placeholder': '0.00'})
    )

    class Meta:
        model = MachineBooking
        fields = [
            'customer', 'machine_type', 'machine', 'operator', 'work_date',
            'requested_start_time', 'expected_quantity', 'expected_duration_hours',
            'billing_type', 'work_location', 'village', 'crop_description', 'notes'
        ]
        widgets = {
            'work_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date', 'id': 'workDate'}),
            'billing_type': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'billingTypeSelect'}),
            'work_location': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Farm / Field address'}),
            'village': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Village Name'}),
            'crop_description': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Paddy Harvesting, Cotton Tillage'}),
            'notes': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Special customer requirements or equipment instructions...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data:
            return cleaned_data

        machine = cleaned_data.get('machine')
        operator = cleaned_data.get('operator')
        work_date = cleaned_data.get('work_date')
        machine_type = cleaned_data.get('machine_type')

        # Validate machine if provided
        if machine and work_date:
            try:
                BookingService.validate_machine_availability(
                    machine=machine,
                    work_date=work_date,
                    exclude_booking_id=self.instance.id if self.instance else None
                )
                if machine.machine_type != machine_type:
                    self.add_error('machine', f"Selected machine '{machine.name}' is not of type '{machine_type.name}'.")
            except ValidationError as e:
                self.add_error('machine', e.message if hasattr(e, 'message') else str(e))

        # Validate operator if provided
        if operator and machine_type:
            try:
                BookingService.validate_operator(operator, machine_type)
            except ValidationError as e:
                self.add_error('operator', e.message if hasattr(e, 'message') else str(e))

        return cleaned_data


class BookingConfirmForm(forms.Form):
    """Form to confirm and assign machine and operator to a pending booking."""
    machine = forms.ModelChoiceField(
        queryset=Machine.objects.filter(is_deleted=False, is_active=True).exclude(
            status__in=[Machine.STATUS_UNDER_MAINTENANCE, Machine.STATUS_DECOMMISSIONED]
        ),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    operator = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_deleted=False, status=Employee.STATUS_ACTIVE),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )


class BookingDispatchForm(forms.Form):
    """Form to dispatch a confirmed booking to the field."""
    dispatch_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Dispatch notes, route, or equipment condition...'})
    )


class BookingCancelForm(forms.Form):
    """Form to cancel a booking."""
    cancellation_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 3, 'placeholder': 'Reason for cancellation...'})
    )


class MachineWorkEntryForm(forms.ModelForm):
    """
    Form for Machine Work Entry & Billing Workflow (Phase 12.4 & 12.5).
    Dynamically captures Harvester time-based operations and Tractor unit-based operations
    with authoritative backend calculation, independent meter tracking, and optional booking link.
    """
    booking = forms.ModelChoiceField(
        queryset=MachineBooking.objects.filter(is_deleted=False),
        required=False,
        widget=forms.HiddenInput()
    )
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.filter(is_deleted=False, status=Customer.STATUS_ACTIVE),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'customerSelect'})
    )
    machine = forms.ModelChoiceField(
        queryset=Machine.objects.filter(is_deleted=False).exclude(status=Machine.STATUS_DECOMMISSIONED).select_related('machine_type'),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'machineSelect'})
    )
    operator = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_deleted=False, status=Employee.STATUS_ACTIVE),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'operatorSelect'})
    )

    # Explicitly set conditional fields to required=False so clean() authoritatively validates per billing_type
    start_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'time', 'id': 'startTime'})
    )
    end_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'time', 'id': 'endTime'})
    )
    break_hours = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'breakHours', 'placeholder': '0.00'})
    )
    hourly_rate = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'hourlyRate', 'placeholder': 'Rate per Hour (₹)'})
    )
    quantity = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'quantityInput', 'placeholder': 'Acres or Pieces'})
    )
    unit_rate = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'unitRateInput', 'placeholder': 'Rate per Unit (₹)'})
    )
    start_meter = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'startMeter', 'placeholder': 'Start Meter Reading'})
    )
    end_meter = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'endMeter', 'placeholder': 'End Meter Reading'})
    )

    class Meta:
        model = MachineWorkEntry
        fields = [
            'booking', 'work_date', 'customer', 'machine', 'operator', 'billing_type',
            'start_time', 'end_time', 'break_hours', 'hourly_rate',
            'quantity', 'unit_rate',
            'start_meter', 'end_meter',
            'notes'
        ]
        widgets = {
            'work_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date', 'id': 'workDate'}),
            'billing_type': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'billingTypeSelect'}),
            'notes': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Optional field work notes...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data:
            return cleaned_data

        billing_type = cleaned_data.get('billing_type')

        # 1. Authoritative Billing Validation & Server-Side Math
        if billing_type == MachineWorkEntry.BILLING_TIME_HOURLY:
            start_time = cleaned_data.get('start_time')
            end_time = cleaned_data.get('end_time')
            break_hours = cleaned_data.get('break_hours')
            if break_hours is None:
                break_hours = Decimal('0.00')
                cleaned_data['break_hours'] = break_hours

            hourly_rate = cleaned_data.get('hourly_rate')
            if hourly_rate is None:
                hourly_rate = Decimal('0.00')
                cleaned_data['hourly_rate'] = hourly_rate

            if not start_time:
                self.add_error('start_time', 'Start time is required for Harvester time-based billing.')
            if not end_time:
                self.add_error('end_time', 'End time is required for Harvester time-based billing.')

            if start_time and end_time:
                try:
                    calc = WorkService.calculate_harvester_billing(
                        start_time=start_time,
                        end_time=end_time,
                        break_hours=break_hours,
                        hourly_rate=hourly_rate
                    )
                    cleaned_data['net_working_hours'] = calc['net_working_hours']
                    cleaned_data['total_amount'] = calc['total_amount']
                except ValidationError as e:
                    self.add_error(None, e.message if hasattr(e, 'message') else str(e))

        elif billing_type in [MachineWorkEntry.BILLING_ACRE, MachineWorkEntry.BILLING_PIECE]:
            quantity = cleaned_data.get('quantity')
            unit_rate = cleaned_data.get('unit_rate')
            if unit_rate is None:
                unit_rate = Decimal('0.00')
                cleaned_data['unit_rate'] = unit_rate

            if quantity is None:
                self.add_error('quantity', 'Quantity is required for Tractor unit-based billing.')
            else:
                try:
                    calc = WorkService.calculate_tractor_billing(
                        quantity=quantity,
                        unit_rate=unit_rate
                    )
                    cleaned_data['total_amount'] = calc['total_amount']
                except ValidationError as e:
                    self.add_error(None, e.message if hasattr(e, 'message') else str(e))

        # 2. Independent Machine Meter Validation (Equipment tracking only)
        start_meter = cleaned_data.get('start_meter')
        end_meter = cleaned_data.get('end_meter')

        if start_meter is not None and end_meter is not None:
            try:
                diff = WorkService.calculate_meter_difference(start_meter, end_meter)
                cleaned_data['meter_difference'] = diff
            except ValidationError as e:
                self.add_error('end_meter', e.message if hasattr(e, 'message') else str(e))
        else:
            cleaned_data['meter_difference'] = Decimal('0.00')

        return cleaned_data


class MachineMaintenanceScheduleForm(forms.ModelForm):
    """Form for setting up and editing Preventive Maintenance Schedules."""
    machine = forms.ModelChoiceField(
        queryset=Machine.objects.filter(is_deleted=False, is_active=True),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'scheduleMachineSelect'})
    )

    class Meta:
        model = MachineMaintenanceSchedule
        fields = [
            'machine', 'schedule_name', 'service_basis',
            'service_interval_meter', 'service_interval_days',
            'last_service_date', 'last_service_meter',
            'warning_meter_before', 'warning_days_before',
            'is_active', 'notes'
        ]
        widgets = {
            'schedule_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. 250 Hour Engine Oil & Filter Service'}),
            'service_basis': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'serviceBasisSelect'}),
            'service_interval_meter': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': 'e.g. 250.00'}),
            'service_interval_days': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. 90'}),
            'last_service_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'last_service_meter': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': 'e.g. 450.00'}),
            'warning_meter_before': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01'}),
            'warning_days_before': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        basis = cleaned_data.get('service_basis')
        interval_meter = cleaned_data.get('service_interval_meter')
        interval_days = cleaned_data.get('service_interval_days')

        if basis in [MachineMaintenanceSchedule.BASIS_METER, MachineMaintenanceSchedule.BASIS_BOTH]:
            if not interval_meter or interval_meter <= Decimal('0.00'):
                self.add_error('service_interval_meter', 'Meter interval must be greater than zero.')

        if basis in [MachineMaintenanceSchedule.BASIS_DATE, MachineMaintenanceSchedule.BASIS_BOTH]:
            if not interval_days or interval_days <= 0:
                self.add_error('service_interval_days', 'Days interval must be greater than zero.')

        return cleaned_data


class MaintenanceJobForm(forms.ModelForm):
    """
    Form for reporting Maintenance & Breakdown Jobs.
    Dynamically renders breakdown-specific fields when breakdown type is selected.
    """
    machine = forms.ModelChoiceField(
        queryset=Machine.objects.filter(is_deleted=False, is_active=True).exclude(status=Machine.STATUS_DECOMMISSIONED),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'jobMachineSelect'})
    )
    maintenance_schedule = forms.ModelChoiceField(
        queryset=MachineMaintenanceSchedule.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'jobScheduleSelect'})
    )
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_deleted=False, status=Supplier.STATUS_ACTIVE),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )

    class Meta:
        model = MaintenanceJob
        fields = [
            'machine', 'maintenance_type', 'maintenance_schedule', 'reported_date',
            'meter_reading', 'problem_description', 'diagnosis', 'severity',
            'breakdown_location', 'breakdown_time', 'machine_stopped',
            'supplier', 'external_workshop_name',
            'labor_cost', 'external_service_cost', 'other_cost',
            'notes'
        ]
        widgets = {
            'maintenance_type': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'maintenanceTypeSelect'}),
            'reported_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'meter_reading': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01'}),
            'problem_description': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 3, 'placeholder': 'Describe the issue, symptoms, or scheduled maintenance reason'}),
            'diagnosis': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Initial mechanic / workshop diagnosis'}),
            'severity': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'breakdown_location': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Field #4, North Farm / Highway 44'}),
            'breakdown_time': forms.DateTimeInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'datetime-local'}),
            'machine_stopped': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'machineStoppedCheck'}),
            'external_workshop_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'External workshop name (if not in supplier list)'}),
            'labor_cost': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary cost-input', 'step': '0.01'}),
            'external_service_cost': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary cost-input', 'step': '0.01'}),
            'other_cost': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary cost-input', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        labor = cleaned_data.get('labor_cost') or Decimal('0.00')
        external = cleaned_data.get('external_service_cost') or Decimal('0.00')
        other = cleaned_data.get('other_cost') or Decimal('0.00')

        if labor < Decimal('0.00') or external < Decimal('0.00') or other < Decimal('0.00'):
            self.add_error(None, 'Costs cannot be negative.')

        meter = cleaned_data.get('meter_reading')
        if meter is not None and meter < Decimal('0.00'):
            self.add_error('meter_reading', 'Meter reading cannot be negative.')

        return cleaned_data


class MaintenancePartUsageForm(forms.ModelForm):
    """Form for logging a spare part item consumed during maintenance."""
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_deleted=False, status=Supplier.STATUS_ACTIVE),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )

    class Meta:
        model = MaintenancePartUsage
        fields = ['part_name', 'part_number', 'quantity', 'unit_cost', 'supplier', 'notes']
        widgets = {
            'part_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Engine Oil Filter / 15W40 Oil'}),
            'part_number': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'OEM Part #'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary part-qty', 'step': '0.01', 'value': '1.00'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary part-unit-cost', 'step': '0.01', 'placeholder': 'Cost per unit in INR'}),
            'notes': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Optional remarks'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        qty = cleaned_data.get('quantity')
        cost = cleaned_data.get('unit_cost')

        if qty is not None and qty <= Decimal('0.00'):
            self.add_error('quantity', 'Quantity must be greater than zero.')
        if cost is not None and cost < Decimal('0.00'):
            self.add_error('unit_cost', 'Unit cost cannot be negative.')

        return cleaned_data


class MaintenanceCompleteForm(forms.Form):
    """Form for completing a maintenance job."""
    completed_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'datetime-local'})
    )
    meter_reading = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01'})
    )
    work_performed = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 4, 'placeholder': 'Comprehensive details of service and repairs completed'}),
        required=True
    )
    labor_cost = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01'})
    )
    external_service_cost = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01'})
    )
    other_cost = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01'})
    )


class MaintenanceExpensePostForm(forms.Form):
    """Form for Owner/Accountant to explicitly post completed maintenance to Expenses."""
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_deleted=False, is_active=True),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    category = forms.ModelChoiceField(
        queryset=ExpenseCategory.objects.filter(is_deleted=False, is_active=True),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    payment_method = forms.ChoiceField(
        choices=Expense.PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
