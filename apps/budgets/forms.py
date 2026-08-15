from django import forms
from decimal import Decimal
from django.utils import timezone
from .models import Budget, BudgetItem
from apps.expenses.models import ExpenseCategory
from apps.machines.models import Machine


class BudgetForm(forms.ModelForm):
    """Form for creating and editing Budgets."""
    MONTH_CHOICES = [
        (1, '01 - January'), (2, '02 - February'), (3, '03 - March'),
        (4, '04 - April'), (5, '05 - May'), (6, '06 - June'),
        (7, '07 - July'), (8, '08 - August'), (9, '09 - September'),
        (10, '10 - October'), (11, '11 - November'), (12, '12 - December')
    ]

    period_month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )

    class Meta:
        model = Budget
        fields = ['title', 'period_month', 'period_year', 'business_segment', 'status', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. August 2026 Fleet Operations Budget'}),
            'period_year': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'min': 2020, 'max': 2035}),
            'business_segment': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'status': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'notes': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Budget objectives and operational context'}),
        }


class BudgetItemForm(forms.Form):
    """Form for allocating category / machine budget item."""
    category = forms.ModelChoiceField(
        queryset=ExpenseCategory.objects.filter(is_deleted=False),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    machine = forms.ModelChoiceField(
        queryset=Machine.objects.filter(is_deleted=False, status=Machine.STATUS_ACTIVE),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    allocated_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '₹ Allocated Limit'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Item notes'})
    )

    def clean_allocated_amount(self):
        amount = self.cleaned_data.get('allocated_amount')
        if amount and amount <= Decimal('0.00'):
            raise forms.ValidationError("Allocation limit must be strictly greater than zero.")
        return amount
