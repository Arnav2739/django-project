"""
Smart MedTrack — Scheduling Service

Core business logic for computing intake timestamps and generating
daily dose events from patient routines and regimen rules.

Key functions:
    calculate_intake_time()       → UTC datetime from anchor + offset
    should_generate_for_date()    → frequency-aware date filter
    generate_daily_dose_events()  → batch DoseEvent creation for a date
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..models import DoseEvent, PatientRoutine, Regimen


def calculate_intake_time(regimen, routine, target_date):
    """
    Compute the UTC datetime for a regimen's dose on target_date.

    For anchor-relative regimens (BREAKFAST, LUNCH, etc.), the anchor time
    is pulled from the patient's routine and adjusted by offset_minutes.
    For CUSTOM anchor, the regimen's fixed_time is used directly.

    Args:
        regimen:     Regimen instance
        routine:     PatientRoutine instance
        target_date: date object (in patient's local calendar)

    Returns:
        datetime in UTC

    Raises:
        ValueError: If no anchor time can be resolved.
    """
    if regimen.anchor == 'CUSTOM':
        anchor_time = regimen.fixed_time
    else:
        anchor_time = routine.get_anchor_time(regimen.anchor)

    if anchor_time is None:
        raise ValueError(
            f"Cannot resolve anchor time for anchor='{regimen.anchor}' "
            f"on regimen {regimen.pk}"
        )

    # Build a timezone-aware local datetime
    patient_tz = ZoneInfo(routine.patient.timezone)
    local_dt = datetime.combine(target_date, anchor_time, tzinfo=patient_tz)

    # Apply minute offset (e.g., -15 = "15 min before breakfast")
    local_dt += timedelta(minutes=regimen.offset_minutes)

    # Store as UTC
    return local_dt.astimezone(ZoneInfo('UTC'))


def should_generate_for_date(regimen, target_date):
    """
    Determine whether a regimen should produce a DoseEvent on target_date
    based on its frequency rule.

    Frequency modes:
        DAILY     → every day
        ALTERNATE → every other day since start_date
        WEEKLY    → only on specific weekdays (stored as JSON list)
    """
    if regimen.frequency == 'DAILY':
        return True

    if regimen.frequency == 'ALTERNATE':
        delta_days = (target_date - regimen.start_date).days
        return delta_days % 2 == 0

    if regimen.frequency == 'WEEKLY':
        if regimen.specific_days:
            return target_date.weekday() in regimen.specific_days
        return False

    return False


def generate_daily_dose_events(patient_profile, target_date):
    """
    Generate all DoseEvent records for a patient on target_date.

    Uses get_or_create to ensure idempotency — safe to call multiple
    times for the same date without creating duplicates.

    Args:
        patient_profile: PatientProfile instance
        target_date:     date object (in patient's local calendar)

    Returns:
        List of newly created DoseEvent instances.
    """
    try:
        routine = patient_profile.routine
    except PatientRoutine.DoesNotExist:
        return []

    active_regimens = Regimen.objects.filter(
        patient=patient_profile,
        is_active=True,
    ).select_related('medication')

    created_events = []

    for regimen in active_regimens:
        if not should_generate_for_date(regimen, target_date):
            continue

        try:
            scheduled_time = calculate_intake_time(regimen, routine, target_date)
        except ValueError:
            continue

        event, created = DoseEvent.objects.get_or_create(
            regimen=regimen,
            scheduled_time=scheduled_time,
            defaults={
                'medication': regimen.medication,
                'status': 'SCHEDULED',
            },
        )
        if created:
            created_events.append(event)

    return created_events
