from django import forms
from .models import Machine, MachineType


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
