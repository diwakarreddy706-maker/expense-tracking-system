from django import forms
from .models import Account, Customer, Supplier


class AccountForm(forms.ModelForm):
    """Form for creating and editing Business Financial Accounts."""
    class Meta:
        model = Account
        fields = [
            'account_name', 'account_type', 'account_number',
            'bank_name', 'ifsc_code', 'opening_balance',
            'opening_balance_date', 'is_active'
        ]
        widgets = {
            'account_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. SBI Current 4091'}),
            'account_type': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Bank A/c or UPI ID'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'State Bank of India'}),
            'ifsc_code': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'SBIN0001234'}),
            'opening_balance': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01'}),
            'opening_balance_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CustomerForm(forms.ModelForm):
    """Form for Customer master records."""
    class Meta:
        model = Customer
        fields = ['customer_code', 'name', 'phone', 'location_address', 'status', 'notes']
        widgets = {
            'customer_code': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. CUST-001'}),
            'name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Customer / Farmer Full Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': '+91 9876543210'}),
            'location_address': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Village / Town'}),
            'status': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'notes': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2}),
        }


class SupplierForm(forms.ModelForm):
    """Form for Supplier / Vendor master records."""
    class Meta:
        model = Supplier
        fields = ['supplier_code', 'name', 'supplier_type', 'phone', 'location_address', 'payment_terms', 'status', 'notes']
        widgets = {
            'supplier_code': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. SUPP-001'}),
            'name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Vendor / Outlet Name'}),
            'supplier_type': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'phone': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': '+91 9876543210'}),
            'location_address': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Shop Address / City'}),
            'payment_terms': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Net 15, Weekly'}),
            'status': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'notes': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2}),
        }
