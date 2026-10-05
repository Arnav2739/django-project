"""
Smart MedTrack — Clinical Adherence Reporting Service

Generates comprehensive adherence data and renders either binary PDF (via WeasyPrint
when GTK/Pango libraries are available) or print-optimized HTML reports.
"""
from datetime import timedelta
import logging
from zoneinfo import ZoneInfo
from django.template.loader import render_to_string
from django.utils import timezone

from ..models import DoseEvent, Medication

logger = logging.getLogger(__name__)


def generate_adherence_report_data(patient_profile, days=30):
    """
    Compile 30-day clinical adherence statistics and event history for a patient.

    Returns:
        dict: Complete report context including metrics, breakdown, and dose log.
    """
    try:
        tz = ZoneInfo(patient_profile.timezone)
    except Exception:
        tz = ZoneInfo('UTC')

    now = timezone.now()
    end_date = now.astimezone(tz).date()
    start_date = end_date - timedelta(days=days)

    start_dt = timezone.datetime.combine(start_date, timezone.datetime.min.time(), tzinfo=tz)
    end_dt = timezone.datetime.combine(end_date, timezone.datetime.max.time(), tzinfo=tz)

    events = (
        DoseEvent.objects
        .filter(
            regimen__patient=patient_profile,
            scheduled_time__gte=start_dt,
            scheduled_time__lte=end_dt,
        )
        .select_related('medication', 'regimen')
        .order_by('-scheduled_time')
    )

    total_doses = events.count()
    taken_ontime = events.filter(status='TAKEN').count()
    taken_late = events.filter(status='TAKEN_LATE').count()
    total_taken = taken_ontime + taken_late
    skipped = events.filter(status='SKIPPED').count()
    missed = events.filter(status='MISSED').count()

    adherence_pct = round((total_taken / total_doses * 100) if total_doses > 0 else 0, 1)

    # Per-medication breakdown
    medications = Medication.objects.filter(patient=patient_profile)
    med_stats = []
    for med in medications:
        med_events = events.filter(medication=med)
        med_total = med_events.count()
        med_taken = med_events.filter(status__in=['TAKEN', 'TAKEN_LATE']).count()
        med_missed = med_events.filter(status='MISSED').count()
        med_pct = round((med_taken / med_total * 100) if med_total > 0 else 0, 1)

        med_stats.append({
            'medication': med,
            'total': med_total,
            'taken': med_taken,
            'missed': med_missed,
            'adherence_pct': med_pct,
        })

    return {
        'patient': patient_profile,
        'user': patient_profile.user,
        'start_date': start_date,
        'end_date': end_date,
        'generated_at': now.astimezone(tz),
        'days': days,
        'total_doses': total_doses,
        'taken_ontime': taken_ontime,
        'taken_late': taken_late,
        'total_taken': total_taken,
        'skipped': skipped,
        'missed': missed,
        'adherence_pct': adherence_pct,
        'med_stats': med_stats,
        'events': events,
    }


def render_pdf_or_html(patient_profile, days=30, as_pdf=False):
    """
    Render clinical adherence report. If as_pdf is True and WeasyPrint is available,
    returns binary PDF bytes; otherwise returns HTML string.
    """
    context = generate_adherence_report_data(patient_profile, days=days)
    html_content = render_to_string('medtrack/reports/adherence_report.html', context)

    if as_pdf:
        try:
            import weasyprint
            pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
            return pdf_bytes, 'application/pdf'
        except Exception as e:
            logger.warning(
                f"WeasyPrint rendering unavailable ({e}); falling back to print-optimized HTML."
            )

    return html_content, 'text/html'
