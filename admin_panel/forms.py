from django import forms
from myapp.models import Event
from myapp.services import sorted_sections


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Admin email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )


class EventForm(forms.ModelForm):
    expected_year_section = forms.ChoiceField(
        choices=[],  # Built dynamically in __init__
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Expected Year/Section'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from myapp.models import Section

        # Build grouped choices: All → Year levels → Individual sections
        choices = [('', 'All (Open to everyone)')]

        # Year-level choices
        year_labels = {1: '1st Year', 2: '2nd Year', 3: '3rd Year', 4: '4th Year'}
        year_choices = [(f'year_{y}', label) for y, label in year_labels.items()]
        choices.append(('By Year Level', year_choices))

        # Individual section choices
        sections = sorted_sections(Section.objects.all())
        section_choices = [(f'section_{s.id}', s.name) for s in sections]
        if section_choices:
            choices.append(('By Section', section_choices))

        self.fields['expected_year_section'].choices = choices

        # Pre-select current value when editing
        if self.instance and self.instance.pk:
            selected_sections = self.instance.expected_sections.all()
            if selected_sections.exists():
                # Check if it matches a full year level
                year_levels = selected_sections.values_list('year_level', flat=True).distinct()
                if year_levels.count() == 1:
                    year = year_levels.first()
                    all_sections_for_year = Section.objects.filter(year_level=year)
                    if set(selected_sections.values_list('id', flat=True)) == set(all_sections_for_year.values_list('id', flat=True)):
                        self.initial['expected_year_section'] = f'year_{year}'
                    else:
                        # Single specific section
                        if selected_sections.count() == 1:
                            self.initial['expected_year_section'] = f'section_{selected_sections.first().id}'
                else:
                    # Multiple sections from different years — pick first section
                    if selected_sections.count() == 1:
                        self.initial['expected_year_section'] = f'section_{selected_sections.first().id}'

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
        end_time = cleaned_data.get('end_time')

        if date and start_time:
            from django.utils import timezone
            from datetime import datetime, timedelta
            
            # Current time in the project's timezone (Asia/Manila)
            now_local = timezone.localtime(timezone.now())
            
            # Event start time in the project's timezone
            event_start_dt = timezone.make_aware(datetime.combine(date, start_time))
            
            # Allow a small 2-minute buffer for form submission time
            if event_start_dt < (now_local - timedelta(minutes=2)):
                self.add_error('start_time', 'You cannot create an event with a start time that has already passed.')

        if start_time and end_time:
            if end_time <= start_time:
                self.add_error('end_time', 'The end time must be later than the start time.')
            
            # If it's today, also check if end time is already in the past
            if date and date == timezone.localtime(timezone.now()).date():
                event_end_dt = timezone.make_aware(datetime.combine(date, end_time))
                if event_end_dt < timezone.localtime(timezone.now()):
                    self.add_error('end_time', 'The end time cannot be in the past.')

        return cleaned_data


