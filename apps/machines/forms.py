from django import forms
from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import Machine, MachineType, MachineWorkEntry
from apps.finance.models import Customer
from apps.employees.models import Employee
from .services.work_service import WorkService


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


class MachineWorkEntryForm(forms.ModelForm):
    """
    Form for Machine Work Entry & Billing Workflow (Phase 12.4).
    Dynamically captures Harvester time-based operations and Tractor unit-based operations
    with authoritative backend calculation and validation.
    """
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
            'work_date', 'customer', 'machine', 'operator', 'billing_type',
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
