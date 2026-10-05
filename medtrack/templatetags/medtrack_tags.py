"""
Smart MedTrack — Template Tags & Filters

Custom template filters for timezone conversion and display formatting.
"""
from django import template
from zoneinfo import ZoneInfo

register = template.Library()


@register.filter
def to_patient_tz(dt, timezone_str):
    """
    Convert a UTC datetime to the patient's local timezone.

    Usage in template:
        {{ event.scheduled_time|to_patient_tz:patient_tz_name }}
    """
    if dt is None:
        return None
    try:
        tz = ZoneInfo(timezone_str)
        return dt.astimezone(tz)
    except (KeyError, AttributeError):
        return dt


@register.filter
def status_color(status):
    """Return Tailwind color classes for a dose event status."""
    color_map = {
        'SCHEDULED': 'bg-blue-100 text-blue-800 border-blue-200',
        'REMINDED': 'bg-sky-100 text-sky-800 border-sky-200',
        'TAKEN': 'bg-emerald-100 text-emerald-800 border-emerald-200',
        'TAKEN_LATE': 'bg-amber-100 text-amber-800 border-amber-200',
        'SKIPPED': 'bg-slate-100 text-slate-600 border-slate-200',
        'MISSED': 'bg-rose-100 text-rose-800 border-rose-200',
    }
    return color_map.get(status, 'bg-gray-100 text-gray-800')


@register.filter
def status_icon(status):
    """Return an emoji icon for a dose event status."""
    icon_map = {
        'SCHEDULED': '🕐',
        'REMINDED': '🔔',
        'TAKEN': '✅',
        'TAKEN_LATE': '⚠️',
        'SKIPPED': '⏭️',
        'MISSED': '❌',
    }
    return icon_map.get(status, '❓')


@register.filter
def stock_color(percentage):
    """Return Tailwind color class for stock level percentage."""
    try:
        pct = int(percentage)
    except (ValueError, TypeError):
        return 'bg-gray-400'

    if pct >= 60:
        return 'bg-emerald-500'
    elif pct >= 30:
        return 'bg-amber-500'
    else:
        return 'bg-rose-500'
