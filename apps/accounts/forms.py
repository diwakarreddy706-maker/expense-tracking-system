from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from .models import UserProfile


class LoginForm(AuthenticationForm):
    """
    Standard authentication form with dark-theme Bootstrap controls.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-dark text-white border-secondary',
            'placeholder': 'Enter username',
            'autofocus': True,
            'autocomplete': 'username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control bg-dark text-white border-secondary',
            'placeholder': 'Enter password',
            'autocomplete': 'current-password'
        })
    )


class UserProfileUpdateForm(forms.ModelForm):
    """
    Form for self profile update.
    """
    first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}))
    phone_number = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': '+91 9876543210'}))

    class Meta:
        model = UserProfile
        fields = ['phone_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.email = self.cleaned_data.get('email', '')
        if commit:
            user.save()
            profile.save()
        return profile


class UserCreateForm(forms.ModelForm):
    """
    Form for Owner to provision new system users.
    """
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Username'}))
    first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Temporary password'}))
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}))
    phone_number = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            role = self.cleaned_data.get('role', UserProfile.ROLE_EMPLOYEE)
            phone = self.cleaned_data.get('phone_number', '')
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.phone_number = phone
            profile.save()
        return user


class UserEditForm(forms.ModelForm):
    """
    Form for Owner to edit existing user role and status.
    """
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}))
    phone_number = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}))
    is_active = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'email': forms.EmailInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['role'].initial = self.instance.profile.role
            self.fields['phone_number'].initial = self.instance.profile.phone_number

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile = user.profile
            profile.role = self.cleaned_data.get('role')
            profile.phone_number = self.cleaned_data.get('phone_number')
            profile.save()
            from django.contrib.auth.models import Group
            group, _ = Group.objects.get_or_create(name=profile.role)
            user.groups.set([group])
        return user
