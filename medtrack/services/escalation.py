"""
Smart MedTrack — Escalation Engine

Implements the clinical two-tier escalation protocol:
  Tier 1: Dispatched at +30 minutes past scheduled time if unconfirmed.
  Tier 2: Dispatched at +60 minutes past scheduled time (30m after Tier 1) if still unconfirmed.
"""
from datetime import timedelta
import logging
from django.db import transaction
from django.utils import timezone

from ..models import CaregiverContact, DoseEvent
from .notifications import dispatch_caregiver_alert

logger = logging.getLogger(__name__)

# Configurable clinical thresholds
GRACE_PERIOD_MINUTES = 30
TIER_2_DELAY_MINUTES = 30


def process_missed_doses():
    """
    Scan for doses exceeding the 30-minute grace period without confirmation.
    Transitions status to MISSED and alerts Tier 1 contacts.

    Returns:
        List of newly escalated DoseEvent instances.
    """
    now = timezone.now()
    threshold = now - timedelta(minutes=GRACE_PERIOD_MINUTES)

    # Doses scheduled before threshold that have not been taken/skipped/missed
    overdue_events = (
        DoseEvent.objects
        .filter(
            status__in=['SCHEDULED', 'REMINDED'],
            scheduled_time__lte=threshold,
        )
        .select_related('medication', 'regimen', 'regimen__patient', 'regimen__patient__user')
    )

    escalated = []
    for event in overdue_events:
        with transaction.atomic():
            locked_event = DoseEvent.objects.select_for_update().get(pk=event.pk)
            if locked_event.status not in ('SCHEDULED', 'REMINDED'):
                continue

            locked_event.status = 'MISSED'
            locked_event.escalated_at = now
            note_entry = f"[{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] Status marked MISSED. Tier 1 escalation dispatched."
            locked_event.notes = (f"{locked_event.notes}\n{note_entry}" if locked_event.notes else note_entry).strip()
            locked_event.save()

            # Find active Tier 1 caregivers for this patient
            tier_1_caregivers = CaregiverContact.objects.filter(
                patient=locked_event.regimen.patient,
                priority_tier=1,
                is_active=True,
            )

            for caregiver in tier_1_caregivers:
                dispatch_caregiver_alert(locked_event, caregiver, tier=1)

            escalated.append(locked_event)

    return escalated


def process_secondary_escalations():
    """
    Scan for MISSED doses that were escalated to Tier 1 over 30 minutes ago,
    and escalate to Tier 2 contacts.

    Returns:
        List of secondary escalated DoseEvent instances.
    """
    now = timezone.now()
    tier_2_threshold = now - timedelta(minutes=TIER_2_DELAY_MINUTES)

    # Missed events where Tier 1 was triggered over 30 min ago and Tier 2 hasn't fired yet
    events = (
        DoseEvent.objects
        .filter(
            status='MISSED',
            escalated_at__lte=tier_2_threshold,
        )
        .exclude(notes__contains='Tier 2 escalation dispatched')
        .select_related('medication', 'regimen', 'regimen__patient', 'regimen__patient__user')
    )

    escalated = []
    for event in events:
        with transaction.atomic():
            locked_event = DoseEvent.objects.select_for_update().get(pk=event.pk)
            if 'Tier 2 escalation dispatched' in locked_event.notes:
                continue

            note_entry = f"[{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] Tier 2 escalation dispatched (unresolved after 60 min)."
            locked_event.notes = (f"{locked_event.notes}\n{note_entry}" if locked_event.notes else note_entry).strip()
            locked_event.save()

            # Find active Tier 2 caregivers
            tier_2_caregivers = CaregiverContact.objects.filter(
                patient=locked_event.regimen.patient,
                priority_tier=2,
                is_active=True,
            )

            for caregiver in tier_2_caregivers:
                dispatch_caregiver_alert(locked_event, caregiver, tier=2)

            escalated.append(locked_event)

    return escalated
