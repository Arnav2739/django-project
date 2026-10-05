"""
Smart MedTrack — Celery Asynchronous Tasks

Periodic and background tasks for automated missed-dose evaluation,
multi-tier caregiver escalations, and daily dose generation.
"""
import datetime
import logging
from zoneinfo import ZoneInfo
from celery import shared_task
from django.utils import timezone

from .models import PatientProfile
from .services.escalation import process_missed_doses, process_secondary_escalations
from .services.scheduling import generate_daily_dose_events

logger = logging.getLogger(__name__)


@shared_task(name='medtrack.evaluate_missed_doses')
def evaluate_missed_doses():
    """
    Periodic task: Runs every minute.
    Scans for doses exceeding 30-minute and 60-minute windows, updates statuses,
    and dispatches Tier 1 & Tier 2 alerts.
    """
    logger.info("Executing periodic evaluation of missed doses...")
    tier1_events = process_missed_doses()
    tier2_events = process_secondary_escalations()

    summary = (
        f"Missed dose evaluation complete. "
        f"Tier 1 escalations: {len(tier1_events)}, Tier 2 escalations: {len(tier2_events)}."
    )
    logger.info(summary)
    return {
        'tier1_escalations': len(tier1_events),
        'tier2_escalations': len(tier2_events),
    }


@shared_task(name='medtrack.generate_daily_doses_for_all_patients')
def generate_daily_doses_for_all_patients(date_str=None):
    """
    Periodic task: Runs shortly after midnight.
    Generates DoseEvent instances for all registered active patients.
    """
    total_generated = 0
    profiles = PatientProfile.objects.select_related('user').all()

    for profile in profiles:
        try:
            tz = ZoneInfo(profile.timezone)
        except Exception:
            tz = ZoneInfo('UTC')

        if date_str:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            target_date = timezone.now().astimezone(tz).date()

        events = generate_daily_dose_events(profile, target_date)
        total_generated += len(events)

    logger.info(
        f"Daily dose generation completed for {profiles.count()} patients. "
        f"Generated {total_generated} events."
    )
    return {
        'patients_processed': profiles.count(),
        'events_generated': total_generated,
    }
