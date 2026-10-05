"""
Smart MedTrack — Django Forms

Forms for authentication, profile setup, medication management,
regimen configuration, and caregiver contact management.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    CaregiverContact,
    Medication,
    PatientProfile,
    PatientRoutine,
    Regimen,
)


# ──────────────────────────────────────────────
# Shared Tailwind widget styling
# ──────────────────────────────────────────────

FORM_INPUT_CLASSES = (
    'w-full px-4 py-2.5 rounded-lg border border-slate-300 '
    'bg-white text-slate-800 placeholder-slate-400 '
    'focus:ring-2 focus:ring-teal-500 focus:border-teal-500 '
    'transition duration-200 outline-none'
)

FORM_SELECT_CLASSES = (
    'w-full px-4 py-2.5 rounded-lg border border-slate-300 '
    'bg-white text-slate-800 '
    'focus:ring-2 focus:ring-teal-500 focus:border-teal-500 '
    'transition duration-200 outline-none'
)

FORM_CHECKBOX_CLASSES = (
    'h-4 w-4 rounded border-slate-300 text-teal-600 '
    'focus:ring-teal-500 transition duration-200'
)


def _apply_widget_classes(form_instance):
    """Apply consistent Tailwind styling to all form widgets."""
    for field_name, field in form_instance.fields.items():
        widget = field.widget
        if isinstance(widget, forms.CheckboxSelectMultiple):
            continue  # Handled separately in template
        elif isinstance(widget, (forms.CheckboxInput,)):
            widget.attrs.setdefault('class', FORM_CHECKBOX_CLASSES)
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault('class', FORM_SELECT_CLASSES)
        else:
            widget.attrs.setdefault('class', FORM_INPUT_CLASSES)


# ──────────────────────────────────────────────
# Authentication Forms
# ──────────────────────────────────────────────

class PatientRegistrationForm(UserCreationForm):
    """Registration form for new patient accounts."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'First Name'}),
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Last Name'}),
    )

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password1', 'password2',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['placeholder'] = 'Choose a username'
        self.fields['password1'].widget.attrs['placeholder'] = 'Create a password'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirm password'
        _apply_widget_classes(self)


# ──────────────────────────────────────────────
# Profile & Routine Forms
# ──────────────────────────────────────────────

class PatientProfileForm(forms.ModelForm):
    """Profile settings form (timezone, emergency contact, physician)."""

    class Meta:
        model = PatientProfile
        fields = ['timezone', 'emergency_phone', 'primary_physician']
        widgets = {
            'timezone': forms.Select(
                choices=[
                    ('Asia/Kolkata', 'Asia/Kolkata (IST)'),
                    ('America/New_York', 'America/New_York (EST)'),
                    ('America/Chicago', 'America/Chicago (CST)'),
                    ('America/Los_Angeles', 'America/Los_Angeles (PST)'),
                    ('Europe/London', 'Europe/London (GMT)'),
                    ('Europe/Berlin', 'Europe/Berlin (CET)'),
                    ('Asia/Tokyo', 'Asia/Tokyo (JST)'),
                    ('Asia/Dubai', 'Asia/Dubai (GST)'),
                    ('Australia/Sydney', 'Australia/Sydney (AEST)'),
                    ('UTC', 'UTC'),
                ],
            ),
            'emergency_phone': forms.TextInput(
                attrs={'placeholder': '+91 98765 43210'},
            ),
            'primary_physician': forms.TextInput(
                attrs={'placeholder': 'Dr. Smith'},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_widget_classes(self)


class PatientRoutineForm(forms.ModelForm):
    """Daily routine anchor times configuration."""

    class Meta:
        model = PatientRoutine
        fields = ['breakfast_time', 'lunch_time', 'dinner_time', 'bedtime']
        widgets = {
            'breakfast_time': forms.TimeInput(
                attrs={'type': 'time'},
                format='%H:%M',
            ),
            'lunch_time': forms.TimeInput(
                attrs={'type': 'time'},
                format='%H:%M',
            ),
            'dinner_time': forms.TimeInput(
                attrs={'type': 'time'},
                format='%H:%M',
            ),
            'bedtime': forms.TimeInput(
                attrs={'type': 'time'},
                format='%H:%M',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_widget_classes(self)


# ──────────────────────────────────────────────
# Medication Form
# ──────────────────────────────────────────────

class MedicationForm(forms.ModelForm):
    """Add / edit a medication in the patient's inventory."""

    class Meta:
        model = Medication
        fields = [
            'name', 'generic_name', 'dosage_unit',
            'current_stock', 'reorder_threshold', 'lead_time_days', 'notes',
        ]
        widgets = {
            'name': forms.TextInput(
                attrs={'placeholder': 'e.g., Metformin 500mg'},
            ),
            'generic_name': forms.TextInput(
                attrs={'placeholder': 'e.g., Metformin Hydrochloride'},
            ),
            'notes': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Special instructions…'},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_widget_classes(self)


# ──────────────────────────────────────────────
# Regimen Form
# ──────────────────────────────────────────────

class RegimenForm(forms.ModelForm):
    """
    Add / edit a dosing regimen.

    Handles the specific_days JSONField via a MultipleChoiceField
    with checkbox widgets for weekday selection.
    """

    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    specific_days_field = forms.MultipleChoiceField(
        choices=DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': FORM_CHECKBOX_CLASSES},
        ),
        required=False,
        label='Specific Days',
        help_text='Select days for WEEKLY frequency',
    )

    class Meta:
        model = Regimen
        fields = [
            'medication', 'dose_quantity', 'anchor',
            'offset_minutes', 'fixed_time', 'frequency',
        ]
        widgets = {
            'fixed_time': forms.TimeInput(
                attrs={'type': 'time'},
                format='%H:%M',
            ),
            'offset_minutes': forms.NumberInput(
                attrs={'min': -60, 'max': 60, 'step': 5},
            ),
        }

    def __init__(self, *args, patient=None, **kwargs):
        super().__init__(*args, **kwargs)
        if patient:
            self.fields['medication'].queryset = Medication.objects.filter(
                patient=patient, is_active=True,
            )
        # Pre-populate weekday checkboxes from existing instance
        if self.instance and self.instance.pk and self.instance.specific_days:
            self.initial['specific_days_field'] = [
                str(d) for d in self.instance.specific_days
            ]
        _apply_widget_classes(self)

    def clean(self):
        cleaned_data = super().clean()
        anchor = cleaned_data.get('anchor')
        frequency = cleaned_data.get('frequency')

        # Validate CUSTOM anchor requires fixed_time
        if anchor == 'CUSTOM' and not cleaned_data.get('fixed_time'):
            self.add_error(
                'fixed_time',
                'Fixed time is required when anchor is set to "Fixed Time".',
            )

        # Validate WEEKLY frequency requires at least one day
        if frequency == 'WEEKLY':
            days = cleaned_data.get('specific_days_field')
            if not days:
                self.add_error(
                    'specific_days_field',
                    'Select at least one day for weekly frequency.',
                )
            else:
                cleaned_data['specific_days'] = [int(d) for d in days]
        else:
            cleaned_data['specific_days'] = None

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.specific_days = self.cleaned_data.get('specific_days')
        if commit:
            instance.save()
        return instance


# ──────────────────────────────────────────────
# Caregiver Contact Form
# ──────────────────────────────────────────────

class CaregiverContactForm(forms.ModelForm):
    """Add / edit a caregiver escalation contact."""

    class Meta:
        model = CaregiverContact
        fields = [
            'name', 'relationship', 'phone_number',
            'email', 'priority_tier',
        ]
        widgets = {
            'name': forms.TextInput(
                attrs={'placeholder': 'Contact name'},
            ),
            'phone_number': forms.TextInput(
                attrs={'placeholder': '+91 98765 43210'},
            ),
            'email': forms.EmailInput(
                attrs={'placeholder': 'caregiver@example.com'},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_widget_classes(self)
