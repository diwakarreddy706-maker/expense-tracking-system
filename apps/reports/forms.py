from django import forms
from apps.reports.models import CompanyProfile


class CompanyProfileForm(forms.ModelForm):
    """
    Form for editing Business Branding, Letterhead, and Invoice Header settings.
    """
    class Meta:
        model = CompanyProfile
        fields = [
            'business_name',
            'legal_name',
            'tagline',
            'phone',
            'email',
            'village',
            'taluk',
            'district',
            'state',
            'pin_code',
            'gst_number',
            'tax_id',
            'bank_name',
            'bank_account_no',
            'bank_ifsc',
            'upi_id',
            'authorized_signatory_name',
            'authorized_signatory_designation',
        ]
        widgets = {
            'business_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Sri Basaveshwara Harvesting & Co.'}),
            'legal_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Registered business entity name'}),
            'tagline': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Agricultural Harvesting & Heavy Equipment Fleet Hub'}),
            'phone': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': '+91 98801 99000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'contact@basaveshwara.co.in'}),
            'village': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Office / Workshop Village or Road'}),
            'taluk': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Gangavati'}),
            'district': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Koppal'}),
            'state': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Karnataka'}),
            'pin_code': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': '583227'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': '29ABCDE1234F1Z5'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'PAN or State Tax ID'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. State Bank of India'}),
            'bank_account_no': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Account number'}),
            'bank_ifsc': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'SBIN0001234'}),
            'upi_id': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'basaveshwara@sbi'}),
            'authorized_signatory_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'e.g. Doddana Gowda'}),
            'authorized_signatory_designation': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Managing Partner / Owner'}),
        }
