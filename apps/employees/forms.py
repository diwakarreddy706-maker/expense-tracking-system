from django import forms
from decimal import Decimal
from .models import Employee, EmployeePayment
from apps.finance.models import Account


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


class SalaryAccrualForm(forms.Form):
    """Form for recording salary / daily wage / commission accruals (liability earned)."""
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_deleted=False, status=Employee.STATUS_ACTIVE),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '₹ Accrued Amount'})
    )
    reference_no = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Muster Roll / Acres Logged'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Accrual remarks (e.g. Aug 2026 Monthly Salary / 25 Days Tillage)'})
    )

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= Decimal('0.00'):
            raise forms.ValidationError("Accrual amount must be strictly greater than zero.")
        return amount


class EmployeePayoutForm(forms.Form):
    """Form for actual monetary disbursements (Advances, Settlements, Bonuses)."""
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_deleted=False, status=Employee.STATUS_ACTIVE),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    payment_type = forms.ChoiceField(
        choices=[
            (EmployeePayment.TYPE_ADVANCE_PAYOUT, 'Advance Payout'),
            (EmployeePayment.TYPE_SALARY_SETTLEMENT, 'Salary Settlement'),
            (EmployeePayment.TYPE_BONUS, 'Performance Bonus / Festival Reward'),
        ],
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '₹ Payout Amount'})
    )
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_deleted=False, is_active=True),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    payment_method = forms.ChoiceField(
        choices=EmployeePayment.PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    reference_no = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Payment Voucher / UTR Ref'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Disbursement purpose / notes'})
    )

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= Decimal('0.00'):
            raise forms.ValidationError("Payout amount must be strictly greater than zero.")
        return amount
