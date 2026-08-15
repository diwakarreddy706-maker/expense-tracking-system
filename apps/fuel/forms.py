from django import forms
from decimal import Decimal
from .models import FuelEntry
from apps.machines.models import Machine
from apps.finance.models import Account, Supplier
from apps.employees.models import Employee


class FuelEntryForm(forms.ModelForm):
    """Form for logging machinery fuel and lubricants."""
    machine = forms.ModelChoiceField(
        queryset=Machine.objects.filter(is_deleted=False).exclude(status=Machine.STATUS_DECOMMISSIONED),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'machineSelect'})
    )
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_deleted=False, status=Supplier.STATUS_ACTIVE),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_deleted=False, is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    operator = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_deleted=False, status=Employee.STATUS_ACTIVE),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )

    class Meta:
        model = FuelEntry
        fields = [
            'date', 'machine', 'fuel_type', 'quantity', 'unit_price',
            'meter_reading', 'payment_method', 'account', 'supplier',
            'operator', 'reference_no', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'fuel_type': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'fuelQuantity', 'placeholder': 'Litres'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'fuelUnitPrice', 'placeholder': 'Rate per Litre'}),
            'meter_reading': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'id': 'meterReadingInput', 'placeholder': 'Current Meter'}),
            'payment_method': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'reference_no': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Fuel Slip / Bill No.'}),
            'notes': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Optional remarks'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        qty = cleaned_data.get('quantity')
        price = cleaned_data.get('unit_price')
        meter = cleaned_data.get('meter_reading')
        machine = cleaned_data.get('machine')
        method = cleaned_data.get('payment_method')
        account = cleaned_data.get('account')

        if qty and qty <= Decimal('0.00'):
            self.add_error('quantity', "Fuel quantity must be strictly greater than zero.")

        if price and price <= Decimal('0.00'):
            self.add_error('unit_price', "Unit price must be strictly greater than zero.")

        if machine and meter is not None:
            if meter < machine.current_meter_reading:
                self.add_error('meter_reading', f"Meter reading cannot be lower than current machine reading ({machine.current_meter_reading} {machine.get_meter_unit_display()}).")

        if method and method != FuelEntry.METHOD_CREDIT and not account:
            self.add_error('account', "A valid account is required for non-credit fuel payments.")

        return cleaned_data
