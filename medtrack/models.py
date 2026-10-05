"""
Smart MedTrack — Core Data Models

Defines the complete entity schema for the medication adherence system:
    PatientProfile  → Extended user profile with timezone
    PatientRoutine  → Daily anchor times (breakfast, lunch, dinner, bedtime)
    CaregiverContact → Escalation contacts with priority tiers
    Medication      → Drug inventory with stock tracking
    Regimen         → Prescription schedules (anchor-relative or fixed-time)
    DoseEvent       → Individual dose instances with state machine
"""
import datetime

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


# ──────────────────────────────────────────────
# Patient & Routine Models
# ──────────────────────────────────────────────

class PatientProfile(models.Model):
    """Extended user profile for patients."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_profile',
    )
    timezone = models.CharField(
        max_length=50,
        default='Asia/Kolkata',
        help_text='IANA timezone (e.g., Asia/Kolkata, America/New_York)',
    )
    emergency_phone = models.CharField(max_length=20, blank=True)
    primary_physician = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Patient Profile'
        verbose_name_plural = 'Patient Profiles'

    def __str__(self):
        return f"Patient: {self.user.get_full_name() or self.user.username}"


class PatientRoutine(models.Model):
    """Daily routine anchor times used for regimen scheduling."""

    patient = models.OneToOneField(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='routine',
    )
    breakfast_time = models.TimeField(
        default=datetime.time(8, 0),
        help_text='Usual breakfast time',
    )
    lunch_time = models.TimeField(
        default=datetime.time(13, 0),
        help_text='Usual lunch time',
    )
    dinner_time = models.TimeField(
        default=datetime.time(19, 30),
        help_text='Usual dinner time',
    )
    bedtime = models.TimeField(
        default=datetime.time(22, 0),
        help_text='Usual bedtime',
    )

    class Meta:
        verbose_name = 'Patient Routine'
        verbose_name_plural = 'Patient Routines'

    def __str__(self):
        return f"Routine for {self.patient}"

    def get_anchor_time(self, anchor):
        """Return the TimeField value for a given anchor name."""
        anchor_map = {
            'BREAKFAST': self.breakfast_time,
            'LUNCH': self.lunch_time,
            'DINNER': self.dinner_time,
            'BEDTIME': self.bedtime,
        }
        return anchor_map.get(anchor)


# ──────────────────────────────────────────────
# Caregiver Contact Model
# ──────────────────────────────────────────────

class CaregiverContact(models.Model):
    """Secondary contacts for the two-tier escalation engine."""

    RELATIONSHIP_CHOICES = [
        ('SPOUSE', 'Spouse'),
        ('CHILD', 'Son / Daughter'),
        ('PARENT', 'Parent'),
        ('SIBLING', 'Sibling'),
        ('NURSE', 'Home Nurse'),
        ('FRIEND', 'Friend'),
        ('OTHER', 'Other'),
    ]
    TIER_CHOICES = [
        (1, 'Tier 1 — Primary'),
        (2, 'Tier 2 — Secondary'),
    ]

    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='caregivers',
    )
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    priority_tier = models.PositiveSmallIntegerField(
        choices=TIER_CHOICES,
        default=1,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Caregiver Contact'
        verbose_name_plural = 'Caregiver Contacts'
        ordering = ['priority_tier', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_relationship_display()}) — Tier {self.priority_tier}"


# ──────────────────────────────────────────────
# Medication & Inventory Model
# ──────────────────────────────────────────────

class Medication(models.Model):
    """A drug in a patient's medication inventory."""

    UNIT_CHOICES = [
        ('TABLETS', 'Tablets'),
        ('CAPSULES', 'Capsules'),
        ('DROPS', 'Drops'),
        ('ML', 'Milliliters'),
        ('PUFFS', 'Puffs'),
        ('SACHETS', 'Sachets'),
    ]

    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='medications',
    )
    name = models.CharField(max_length=200, help_text='Trade / brand name')
    generic_name = models.CharField(
        max_length=200,
        blank=True,
        help_text='Chemical / generic formulation',
    )
    dosage_unit = models.CharField(max_length=20, choices=UNIT_CHOICES)
    current_stock = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    reorder_threshold = models.PositiveIntegerField(
        default=7,
        help_text='Reorder when days remaining ≤ threshold + buffer',
    )
    lead_time_days = models.PositiveIntegerField(
        default=3,
        help_text='Days needed to procure refill from pharmacy',
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Medication'
        verbose_name_plural = 'Medications'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_dosage_unit_display()})"


# ──────────────────────────────────────────────
# Regimen (Prescription Schedule)
# ──────────────────────────────────────────────

class Regimen(models.Model):
    """
    A prescription schedule linking a medication to a dosing pattern.

    Supports two timing modes:
      • Anchor-Relative: offset from a routine event (e.g., Breakfast -15 min)
      • Fixed Clock: strict static time (anchor = CUSTOM, fixed_time set)
    """

    ANCHOR_CHOICES = [
        ('BREAKFAST', 'Breakfast'),
        ('LUNCH', 'Lunch'),
        ('DINNER', 'Dinner'),
        ('BEDTIME', 'Bedtime'),
        ('CUSTOM', 'Fixed Time'),
    ]
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('ALTERNATE', 'Alternate Days'),
        ('WEEKLY', 'Specific Days of Week'),
    ]

    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='regimens',
    )
    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='regimens',
    )
    dose_quantity = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(0.25)],
        help_text='Number of units per dose',
    )
    anchor = models.CharField(max_length=20, choices=ANCHOR_CHOICES)
    offset_minutes = models.IntegerField(
        default=0,
        validators=[MinValueValidator(-60), MaxValueValidator(60)],
        help_text='Minutes before (−) or after (+) the anchor event',
    )
    fixed_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Used only when anchor is CUSTOM (Fixed Time)',
    )
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='DAILY',
    )
    specific_days = models.JSONField(
        null=True,
        blank=True,
        help_text='Weekday numbers [0=Mon … 6=Sun] for WEEKLY frequency',
    )
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Regimen'
        verbose_name_plural = 'Regimens'
        ordering = ['medication__name', 'anchor']

    def __str__(self):
        offset_str = ''
        if self.offset_minutes:
            sign = '+' if self.offset_minutes > 0 else ''
            offset_str = f' ({sign}{self.offset_minutes} min)'
        return (
            f"{self.medication.name} — {self.dose_quantity} "
            f"{self.medication.get_dosage_unit_display()} @ "
            f"{self.get_anchor_display()}{offset_str}"
        )


# ──────────────────────────────────────────────
# Dose Event (Scheduled Intake Instance)
# ──────────────────────────────────────────────

class DoseEvent(models.Model):
    """
    An individual scheduled dose instance with a state machine:

        SCHEDULED → REMINDED → TAKEN
                              → TAKEN_LATE
                              → SKIPPED
                              → MISSED
    """

    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('REMINDED', 'Reminded'),
        ('TAKEN', 'Taken'),
        ('TAKEN_LATE', 'Taken Late'),
        ('SKIPPED', 'Skipped'),
        ('MISSED', 'Missed'),
    ]

    regimen = models.ForeignKey(
        Regimen,
        on_delete=models.CASCADE,
        related_name='dose_events',
    )
    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='dose_events',
    )
    scheduled_time = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='SCHEDULED',
    )
    taken_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dose Event'
        verbose_name_plural = 'Dose Events'
        ordering = ['scheduled_time']
        constraints = [
            models.UniqueConstraint(
                fields=['regimen', 'scheduled_time'],
                name='unique_dose_per_slot',
            ),
        ]

    def __str__(self):
        return (
            f"{self.medication.name} — "
            f"{self.scheduled_time.strftime('%Y-%m-%d %H:%M')} — "
            f"{self.get_status_display()}"
        )

    @property
    def is_actionable(self):
        """Whether this dose can still be acted upon (taken or skipped)."""
        return self.status in ('SCHEDULED', 'REMINDED')
