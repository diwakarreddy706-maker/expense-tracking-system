from django import forms
from .models import Employee


class EmployeeForm(forms.ModelForm):
    """Form for Employee Master Registry."""
    class Meta:
        model = Employee
        fields = [
            'employee_code', 'full_name', 'phone_number',
            'role', 'wage_type', 'base_rate',
            'status', 'joining_date', 'emergency_contact'
        ]
        widgets = {
            'employee_code': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. EMP-001'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Staff Member Name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': '+91 9876543210'}),
            'role': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'wage_type': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'base_rate': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'joining_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Name & Contact'}),
        }
