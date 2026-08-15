from django import forms
from decimal import Decimal
from .models import (
    Account, Customer, Supplier,
    Receivable, CustomerPayment,
    Payable, SupplierPayment
)


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


class ReceivableForm(forms.Form):
    """Form for creating a customer receivable obligation."""
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.filter(is_deleted=False, status=Customer.STATUS_ACTIVE),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    invoice_no = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Bill / Invoice No.'})
    )
    bill_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'})
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'})
    )
    total_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '₹ Total Billed Amount'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Receivable remarks'})
    )

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get('total_amount')
        bill = cleaned_data.get('bill_date')
        due = cleaned_data.get('due_date')

        if total and total <= Decimal('0.00'):
            self.add_error('total_amount', "Billed amount must be strictly greater than zero.")

        if bill and due and due < bill:
            self.add_error('due_date', "Payment due date cannot be before bill date.")

        return cleaned_data


class CustomerPaymentForm(forms.Form):
    """Form for settling a customer receivable (receipt of funds)."""
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '₹ Receipt Amount'})
    )
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_deleted=False, is_active=True),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    payment_method = forms.ChoiceField(
        choices=CustomerPayment.PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    reference_no = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'UTR / Cheque / Receipt Reference'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Payment notes'})
    )

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= Decimal('0.00'):
            raise forms.ValidationError("Receipt amount must be strictly greater than zero.")
        return amount


class PayableForm(forms.Form):
    """Form for creating a supplier payable obligation."""
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_deleted=False, status=Supplier.STATUS_ACTIVE),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    bill_no = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Supplier Invoice / Bill No.'})
    )
    bill_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'})
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'})
    )
    total_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '₹ Payable Amount'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Payable remarks'})
    )

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get('total_amount')
        bill = cleaned_data.get('bill_date')
        due = cleaned_data.get('due_date')

        if total and total <= Decimal('0.00'):
            self.add_error('total_amount', "Payable amount must be strictly greater than zero.")

        if bill and due and due < bill:
            self.add_error('due_date', "Due date cannot be before bill date.")

        return cleaned_data


class SupplierPaymentForm(forms.Form):
    """Form for settling a supplier payable (disbursement of funds)."""
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'type': 'date'})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'step': '0.01', 'placeholder': '₹ Disbursement Amount'})
    )
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_deleted=False, is_active=True),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    payment_method = forms.ChoiceField(
        choices=SupplierPayment.PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
    )
    reference_no = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'UTR / Cheque / Voucher Reference'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 2, 'placeholder': 'Payment notes'})
    )

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= Decimal('0.00'):
            raise forms.ValidationError("Disbursement amount must be strictly greater than zero.")
        return amount
