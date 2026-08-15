from django import forms
from .models import ExpenseCategory


class ExpenseCategoryForm(forms.ModelForm):
    """Form for creating and editing Expense Categories."""
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'code', 'parent', 'color_hex', 'icon_class', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Fuel & Diesel'}),
            'code': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. CAT-FUEL'}),
            'parent': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'color_hex': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'color'}),
            'icon_class': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'bi-fuel-pump-fill'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
