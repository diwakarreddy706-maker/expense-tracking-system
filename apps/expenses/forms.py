from django import forms
from decimal import Decimal
from .models import Expense, ExpenseCategory
from apps.finance.models import Account, Supplier
from apps.machines.models import Machine
from apps.employees.models import Employee


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


class ExpenseForm(forms.ModelForm):
    """Full Expense Entry Form."""
    category = forms.ModelChoiceField(
        queryset=ExpenseCategory.objects.filter(is_deleted=False, is_active=True),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_deleted=False, is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    machine = forms.ModelChoiceField(
        queryset=Machine.objects.filter(is_deleted=False).exclude(status=Machine.STATUS_DECOMMISSIONED),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_deleted=False, status=Employee.STATUS_ACTIVE),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_deleted=False, status=Supplier.STATUS_ACTIVE),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )

    class Meta:
        model = Expense
        fields = [
            'expense_date', 'amount', 'category', 'payment_method',
            'account', 'business_segment', 'machine', 'employee',
            'supplier', 'reference_no', 'description'
        ]
        widgets = {
            'expense_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '0.00'}),
            'payment_method': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'business_segment': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'reference_no': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Bill / Receipt / UTR No.'}),
            'description': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 3, 'placeholder': 'Narrative notes / purpose'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        method = cleaned_data.get('payment_method')
        account = cleaned_data.get('account')

        if amount and amount <= Decimal('0.00'):
            self.add_error('amount', "Expense amount must be strictly greater than zero.")

        if method and method != Expense.METHOD_CREDIT and not account:
            self.add_error('account', "An active account must be selected for non-credit payment methods.")

        return cleaned_data


class QuickExpenseForm(forms.Form):
    """Minimal Quick Expense Form for fast mobile field entry (< 20s)."""
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '₹ Amount'})
    )
    category = forms.ModelChoiceField(
        queryset=ExpenseCategory.objects.filter(is_deleted=False, is_active=True),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_deleted=False, is_active=True),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    payment_method = forms.ChoiceField(
        choices=[
            (Expense.METHOD_CASH, 'Cash'),
            (Expense.METHOD_UPI, 'UPI'),
            (Expense.METHOD_BANK_TRANSFER, 'Bank Transfer')
        ],
        initial=Expense.METHOD_CASH,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    machine = forms.ModelChoiceField(
        queryset=Machine.objects.filter(is_deleted=False).exclude(status=Machine.STATUS_DECOMMISSIONED),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    description = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Quick note / item (optional)'})
    )
