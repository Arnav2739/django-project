"""
Smart MedTrack — Inventory & Forecasting Service

Business logic for medication stock management:
    calculate_burn_rate()    → rolling 7-day daily consumption rate
    calculate_days_remaining() → estimated days until stockout
    check_reorder_needed()   → threshold alert evaluation
    record_dose_taken()      → atomic dose intake with concurrency-safe stock decrement
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..models import DoseEvent, Medication, Regimen
from .scheduling import should_generate_for_date


def calculate_burn_rate(medication):
    """
    Calculate the rolling 7-day burn rate for a medication.

    Prevents division-by-zero on alternate-day or cyclic regimens by
    distributing scheduled units across a 7-day lookahead window.

    Formula:
        burn_rate_daily = Σ(scheduled units over next 7 days) / 7

    Returns:
        Decimal — average daily consumption in dosage units.
    """
    today = timezone.now().date()
    total_scheduled = Decimal('0')

    active_regimens = Regimen.objects.filter(
        medication=medication,
        is_active=True,
    )

    for day_offset in range(7):
        check_date = today + timedelta(days=day_offset)
        for regimen in active_regimens:
            if should_generate_for_date(regimen, check_date):
                total_scheduled += regimen.dose_quantity

    if total_scheduled == 0:
        return Decimal('0')

    return total_scheduled / Decimal('7')


def calculate_days_remaining(medication):
    """
    Estimate days of stock remaining based on the rolling burn rate.

    Returns:
        int — estimated days, or None if burn rate is zero (no active regimens).
    """
    burn_rate = calculate_burn_rate(medication)

    if burn_rate <= 0:
        return None  # No consumption → infinite stock life

    return int(medication.current_stock / burn_rate)


def check_reorder_needed(medication):
    """
    Check whether a medication needs a reorder alert.

    Triggers when:
        days_remaining ≤ lead_time_days + buffer (3 days)

    Returns:
        bool — True if reorder alert should fire.
    """
    days_remaining = calculate_days_remaining(medication)

    if days_remaining is None:
        return False  # No consumption

    buffer_days = 3
    threshold = medication.lead_time_days + buffer_days
    return days_remaining <= threshold


def record_dose_taken(dose_event):
    """
    Atomically record a dose as taken and decrement medication stock.

    Uses select_for_update() inside transaction.atomic() to prevent
    race conditions from multi-clicks or concurrent devices.

    Logic:
        1. Lock the medication row and dose event row.
        2. If already processed (TAKEN/TAKEN_LATE/SKIPPED), return immediately.
        3. Determine TAKEN vs TAKEN_LATE based on 30-minute threshold.
        4. Decrement stock (clamped to zero).

    Returns:
        The updated DoseEvent instance.
    """
    with transaction.atomic():
        # Lock rows to prevent concurrent modifications
        medication = Medication.objects.select_for_update().get(
            pk=dose_event.medication_id,
        )
        dose = DoseEvent.objects.select_for_update().get(pk=dose_event.pk)

        # Idempotency guard — already processed
        if dose.status in ('TAKEN', 'TAKEN_LATE', 'SKIPPED'):
            return dose

        now = timezone.now()
        time_diff_seconds = (now - dose.scheduled_time).total_seconds()

        # More than 30 minutes late?
        if time_diff_seconds > 1800:
            dose.status = 'TAKEN_LATE'
        else:
            dose.status = 'TAKEN'

        dose.taken_at = now
        dose.save()

        # Decrement stock, never going below zero
        new_stock = medication.current_stock - dose.regimen.dose_quantity
        medication.current_stock = max(new_stock, Decimal('0'))
        medication.save()

    return dose
