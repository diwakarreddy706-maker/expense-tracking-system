from django import forms
from decimal import Decimal
from .models import Employee, EmployeePayment, EmployeeCompensation
from apps.finance.models import Account


class EmployeeForm(forms.ModelForm):
    """Form for Employee Master Registry."""
    class Meta:
        model = Employee
        fields = [
            'employee_code', 'full_name', 'phone_number',
            'role', 'status', 'joining_date', 'emergency_contact'
        ]
        widgets = {
            'employee_code': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. EMP-001'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Staff Member Name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': '+91 9876543210'}),
            'role': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'status': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'joining_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Name & Contact'}),
        }


class EmployeeCompensationForm(forms.ModelForm):
    """Form for adding or editing individual Employee Compensation rates."""
    class Meta:
        model = EmployeeCompensation
        fields = [
            'wage_type', 'rate', 'effective_from', 'effective_to', 'is_active', 'notes'
        ]
        widgets = {
            'wage_type': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'rate': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '₹ Rate Amount'}),
            'effective_from': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'effective_to': forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Optional context (e.g. Standard Daily Allowance)'}),
        }

    def clean_rate(self):
        rate = self.cleaned_data.get('rate')
        if rate and rate <= Decimal('0.00'):
            raise forms.ValidationError("Compensation rate must be strictly greater than zero.")
        return rate


class SalaryAccrualForm(forms.Form):
    """Form for recording salary / daily wage / commission accruals (liability earned)."""
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_deleted=False, status=Employee.STATUS_ACTIVE),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'id_accrual_employee'})
    )
    compensation = forms.ModelChoiceField(
        queryset=EmployeeCompensation.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'id_accrual_compensation'})
    )
    units_logged = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': 'Units (e.g. 25 days / 50 acres)', 'id': 'id_units_logged'})
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '₹ Accrued Amount', 'id': 'id_accrual_amount'})
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

    def clean(self):
        cleaned_data = super().clean()
        compensation = cleaned_data.get('compensation')
        units = cleaned_data.get('units_logged')
        amount = cleaned_data.get('amount')
        employee = cleaned_data.get('employee')

        if compensation and employee and compensation.employee_id != employee.id:
            raise forms.ValidationError({"compensation": "Selected compensation does not belong to the chosen employee."})

        if compensation and units:
            if units <= Decimal('0.00'):
                raise forms.ValidationError({"units_logged": "Units logged must be strictly greater than zero."})
            calculated = (compensation.rate * units).quantize(Decimal('0.01'))
            if not amount:
                cleaned_data['amount'] = calculated
                amount = calculated

        if not amount or amount <= Decimal('0.00'):
            raise forms.ValidationError({"amount": "Please enter an amount or select a compensation rate with units logged."})

        return cleaned_data


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

