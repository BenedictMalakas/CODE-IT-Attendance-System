from django import forms
import re
from myapp.models import Student


class StudentLoginForm(forms.Form):
    student_id = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 24-0001',
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


class StudentRegisterForm(forms.Form):
    YEAR_CHOICES = [
        ('', '— Select Year Level —'),
        ('1', '1st Year'),
        ('2', '2nd Year'),
        ('3', '3rd Year'),
        ('4', '4th Year'),
    ]

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
            'maxlength': '7',
        }),
        label='Student ID',
    )
    year_level = forms.ChoiceField(
        choices=YEAR_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_year_level',
        }),
        label='Year Level',
    )
    section = forms.CharField(
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_section',
            'disabled': 'disabled',
        }),
        label='Section',
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

    def clean_first_name(self):
        name = self.cleaned_data.get('first_name', '').strip()
        if not re.match(r'^[A-Za-z\s]+$', name):
            raise forms.ValidationError("First name must contain letters only. No special characters or numbers.")
        return name

    def clean_last_name(self):
        name = self.cleaned_data.get('last_name', '').strip()
        if not re.match(r'^[A-Za-z\s]+$', name):
            raise forms.ValidationError("Last name must contain letters only. No special characters or numbers.")
        return name

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        if not re.match(r'^\d{2}-\d{4}$', student_id):
            raise forms.ValidationError("Student ID must be in the format xx-xxxx (e.g. 24-0001).")
        return student_id

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        # Must have valid structure
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise forms.ValidationError("Please enter a valid email address.")
        # Allow common providers + edu domains
        allowed_patterns = [
            '@gmail.com', '@outlook.com', '@yahoo.com', '@hotmail.com',
            '@icloud.com', '@protonmail.com',
        ]
        is_edu = email.endswith('.edu') or email.endswith('.edu.ph')
        if not is_edu and not any(email.endswith(p) for p in allowed_patterns):
            raise forms.ValidationError("Please use a recognized email provider (Gmail, Outlook, Yahoo, etc.) or an .edu address.")
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
