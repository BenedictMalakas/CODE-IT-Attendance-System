from django import forms


class StudentLoginForm(forms.Form):
    student_id = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 2024-00001',
            'autocomplete': 'username',
        }),
        label='Student ID',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your password',
            'autocomplete': 'current-password',
        }),
    )


import re
from myapp.models import Student

class StudentRegisterForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Juan',
        }),
        label='First Name',
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Dela Cruz',
        }),
        label='Last Name',
    )
    student_id = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 24-0001',
        }),
        label='Student ID',
    )
    section = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. BSIT-3A',
        }),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. juan@gmail.com',
        }),
        label='Email Address',
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min 8 chars, 1 special char',
        }),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Re-enter password',
        }),
        label='Confirm Password',
    )

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        if not re.match(r'^\d{2}-\d{4}$', student_id):
            raise forms.ValidationError("Student ID must be in the format xx-xxxx (e.g. 24-0001).")
        return student_id

    def clean_section(self):
        section = self.cleaned_data.get('section')
        if not re.match(r'^[A-Za-z0-9]+-[A-Za-z0-9]+$', section):
            raise forms.ValidationError("Section must be in the format x-x (e.g. BSIT-3A).")
        return section

    def clean_email(self):
        email = self.cleaned_data.get('email')
        allowed_domains = ['@gmail.com', '@outlook.com', '@yahoo.com']
        if not any(email.endswith(domain) for domain in allowed_domains):
            raise forms.ValidationError("Email must be a @gmail.com, @outlook.com, or @yahoo.com address.")
        if Student.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password(self):
        pw = self.cleaned_data.get('password')
        if pw and len(pw) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")
        if pw and not re.search(r'[!@#$%^&*(),.?":{}|<>]', pw):
            raise forms.ValidationError("Password must contain at least one special character.")
        return pw

    def clean(self):
        cleaned = super().clean()
        pw  = cleaned.get('password')
        cpw = cleaned.get('confirm_password')
        if pw and cpw and pw != cpw:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned
