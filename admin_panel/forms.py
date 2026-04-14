from django import forms
from myapp.models import Event


class LoginForm(forms.Form):
    ROLE_CHOICES = [
        ('vits', 'VITS Officer'),
        ('representative', 'Representative'),
    ]
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Admin email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password', 'id': 'id_password'})
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Login as',
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
            'start_time':       'Start time (optional — auto-starts if set)',
            'late_cutoff_mins': 'Late cutoff (minutes after start)',
            'end_time':         'End time (optional — auto-ends if set)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_time'].required = False
        self.fields['end_time'].required = False

