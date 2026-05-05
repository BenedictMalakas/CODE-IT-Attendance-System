from django import forms
from myapp.models import Admin, Event


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Admin email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'date', 'start_time', 'end_time', 'late_cutoff_mins']
        widgets = {
            'name':             forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Foundation Week Day 1'}),
            'date':             forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time':       forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time':         forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'late_cutoff_mins': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
        labels = {
            'late_cutoff_mins': 'Late cutoff (minutes after start)',
            'end_time':         'End time',
        }

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        start_time = cleaned_data.get('start_time')

        if date and start_time:
            from django.utils import timezone
            from datetime import datetime
            
            event_datetime = timezone.make_aware(datetime.combine(date, start_time))
            if event_datetime < timezone.now():
                raise forms.ValidationError('You cannot create an event that has already started or is in the past.')

        return cleaned_data


class AdminRegisterForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Juan Dela Cruz'}),
        label='Full Name',
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'e.g. admin@school.edu'}),
    )
    role = forms.ChoiceField(
        choices=[
            (Admin.Role.VITS, 'VITS Officer'),
            (Admin.Role.REPRESENTATIVE, 'Representative'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Min 6 characters'}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Re-enter password'}),
        label='Confirm Password',
    )

    def clean(self):
        cleaned = super().clean()
        pw  = cleaned.get('password')
        cpw = cleaned.get('confirm_password')
        if pw and cpw and pw != cpw:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned

