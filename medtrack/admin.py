"""
Smart MedTrack — Django Admin Configuration

Registers all core models with rich list displays, filters, and search
for administrative management and debugging.
"""
from django.contrib import admin

from .models import (
    CaregiverContact,
    DoseEvent,
    Medication,
    PatientProfile,
    PatientRoutine,
    Regimen,
)


# ──────────────────────────────────────────────
# Inline admins for nested relationships
# ──────────────────────────────────────────────

class PatientRoutineInline(admin.StackedInline):
    model = PatientRoutine
    can_delete = False
    verbose_name_plural = 'Patient Routine'


class CaregiverContactInline(admin.TabularInline):
    model = CaregiverContact
    extra = 0
    fields = ('name', 'relationship', 'phone_number', 'email', 'priority_tier', 'is_active')


# ──────────────────────────────────────────────
# Model admin registrations
# ──────────────────────────────────────────────

@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'timezone', 'emergency_phone', 'primary_physician', 'created_at')
    list_filter = ('timezone',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'emergency_phone')
    inlines = [PatientRoutineInline, CaregiverContactInline]


@admin.register(PatientRoutine)
class PatientRoutineAdmin(admin.ModelAdmin):
    list_display = ('patient', 'breakfast_time', 'lunch_time', 'dinner_time', 'bedtime')
    search_fields = ('patient__user__username',)


@admin.register(CaregiverContact)
class CaregiverContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'patient', 'relationship', 'phone_number', 'priority_tier', 'is_active')
    list_filter = ('priority_tier', 'relationship', 'is_active')
    search_fields = ('name', 'phone_number', 'email', 'patient__user__username')


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'generic_name', 'patient', 'dosage_unit', 'current_stock', 'is_active')
    list_filter = ('dosage_unit', 'is_active')
    search_fields = ('name', 'generic_name', 'patient__user__username')
    list_editable = ('current_stock',)


@admin.register(Regimen)
class RegimenAdmin(admin.ModelAdmin):
    list_display = (
        'medication', 'patient', 'dose_quantity', 'anchor',
        'offset_minutes', 'frequency', 'is_active',
    )
    list_filter = ('anchor', 'frequency', 'is_active')
    search_fields = ('medication__name', 'patient__user__username')
    raw_id_fields = ('medication',)


@admin.register(DoseEvent)
class DoseEventAdmin(admin.ModelAdmin):
    list_display = ('medication', 'scheduled_time', 'status', 'taken_at', 'escalated_at')
    list_filter = ('status', 'scheduled_time')
    search_fields = ('medication__name', 'regimen__patient__user__username')
    date_hierarchy = 'scheduled_time'
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('regimen', 'medication')
