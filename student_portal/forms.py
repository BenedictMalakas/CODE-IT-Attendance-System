import re
from django import forms
from myapp.models import Section, Student


class StudentLoginForm(forms.Form):
    student_id = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class':        'form-control',
            'placeholder':  'e.g. 24-0001',
            'autocomplete': 'username',
        }),
        label='Student ID',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class':        'form-control',
            'placeholder':  'Your password',
            'autocomplete': 'current-password',
        }),
    )


class StudentRegisterForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Juan'}),
        label='First Name',
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Dela Cruz'}),
        label='Last Name',
    )
    student_id = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': 'e.g. 24-0001',
            'maxlength':   '7',
        }),
        label='Student ID',
    )
    year_level = forms.ChoiceField(
        choices=[
            ('', '— Select Year Level —'),
            ('1', '1st Year'),
            ('2', '2nd Year'),
            ('3', '3rd Year'),
            ('4', '4th Year'),
        ],
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_year_level'}),
        label='Year Level',
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.none(),
        empty_label='— Select Section —',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_section'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'e.g. juan@gmail.com'}),
        label='Email Address',
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class':       'form-control',
            'placeholder': 'Min 8 chars, 1 special char',
        }),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Re-enter password'}),
        label='Confirm Password',
    )
    id_photo = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.png,.jpg,.jpeg,.webp'}),
        label='ID Photo (optional)',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = Section.objects.all().order_by('year_level', 'name')

    def clean_first_name(self):
        val = self.cleaned_data.get('first_name', '').strip()
        if not re.match(r'^[A-Za-z\s]+$', val):
            raise forms.ValidationError('First name must contain letters only. No special characters or numbers.')
        return val

    def clean_last_name(self):
        val = self.cleaned_data.get('last_name', '').strip()
        if not re.match(r'^[A-Za-z\s]+$', val):
            raise forms.ValidationError('Last name must contain letters only. No special characters or numbers.')
        return val

    def clean_student_id(self):
        sid = self.cleaned_data.get('student_id', '')
        if not re.match(r'^\d{2}-\d{4}$', sid):
            raise forms.ValidationError('Student ID must be in the format xx-xxxx (e.g. 24-0001).')
        if Student.objects.filter(student_id=sid).exists():
            raise forms.ValidationError('A student with that ID already exists.')
        return sid

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
            raise forms.ValidationError('Please enter a valid email address.')
        allowed = [
            '@gmail.com', '@outlook.com', '@yahoo.com',
            '@hotmail.com', '@icloud.com', '@protonmail.com',
        ]
        if not (any(email.endswith(d) for d in allowed) or '.edu' in email):
            raise forms.ValidationError(
                'Please use a recognized email provider (Gmail, Outlook, Yahoo, etc.) or an .edu address.'
            )
        if Student.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_password(self):
        pw = self.cleaned_data.get('password', '')
        if len(pw) < 8:
            raise forms.ValidationError('Password must be at least 8 characters long.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', pw):
            raise forms.ValidationError('Password must contain at least one special character.')
        return pw

    def clean(self):
        cleaned = super().clean()
        pw  = cleaned.get('password')
        cpw = cleaned.get('confirm_password')
        if pw and cpw and pw != cpw:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned
