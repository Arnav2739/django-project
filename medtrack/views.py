"""
Smart MedTrack — Views

All view functions for authentication, dashboard, dose tracking,
medication CRUD, regimen CRUD, and caregiver management.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    CaregiverContactForm,
    MedicationForm,
    PatientProfileForm,
    PatientRegistrationForm,
    PatientRoutineForm,
    RegimenForm,
)
from .models import (
    CaregiverContact,
    DoseEvent,
    Medication,
    PatientProfile,
    PatientRoutine,
    Regimen,
)
from .services.inventory import (
    calculate_burn_rate,
    calculate_days_remaining,
    check_reorder_needed,
    record_dose_taken,
)
from .services.reports import render_pdf_or_html
from .services.scheduling import generate_daily_dose_events


# ──────────────────────────────────────────────
# Helper: Get or create patient profile
# ──────────────────────────────────────────────

def _get_patient_profile(user):
    """Get or create the PatientProfile for a user."""
    profile, _ = PatientProfile.objects.get_or_create(user=user)
    return profile


# ──────────────────────────────────────────────
# Authentication Views
# ──────────────────────────────────────────────

def register_view(request):
    """Patient registration with automatic profile creation."""
    if request.user.is_authenticated:
        return redirect('medtrack:dashboard')

    if request.method == 'POST':
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile = PatientProfile.objects.create(user=user)
            PatientRoutine.objects.create(patient=profile)
            login(request, user)
            messages.success(
                request,
                f'Welcome, {user.first_name}! Please configure your daily routine.',
            )
            return redirect('medtrack:profile_setup')
    else:
        form = PatientRegistrationForm()

    return render(request, 'medtrack/register.html', {'form': form})


def login_view(request):
    """Patient login."""
    if request.user.is_authenticated:
        return redirect('medtrack:dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            next_url = request.GET.get('next', 'medtrack:dashboard')
            return redirect(next_url)
    else:
        form = AuthenticationForm()

    return render(request, 'medtrack/login.html', {'form': form})


def logout_view(request):
    """Logout and redirect to login."""
    logout(request)
    messages.info(request, 'You have been signed out.')
    return redirect('medtrack:login')


# ──────────────────────────────────────────────
# Profile & Routine Setup
# ──────────────────────────────────────────────

@login_required
def profile_setup_view(request):
    """Profile and daily routine configuration."""
    profile = _get_patient_profile(request.user)
    routine, _ = PatientRoutine.objects.get_or_create(patient=profile)

    if request.method == 'POST':
        profile_form = PatientProfileForm(request.POST, instance=profile)
        routine_form = PatientRoutineForm(request.POST, instance=routine)
        if profile_form.is_valid() and routine_form.is_valid():
            profile_form.save()
            routine_form.save()
            messages.success(request, 'Profile & routine updated successfully!')
            return redirect('medtrack:dashboard')
    else:
        profile_form = PatientProfileForm(instance=profile)
        routine_form = PatientRoutineForm(instance=routine)

    return render(request, 'medtrack/profile_setup.html', {
        'profile_form': profile_form,
        'routine_form': routine_form,
    })


# ──────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────

@login_required
def dashboard_view(request):
    """
    Main dashboard showing today's dose schedule, adherence stats,
    and low-stock medication alerts.
    """
    profile = _get_patient_profile(request.user)
    patient_tz = ZoneInfo(profile.timezone)
    today = timezone.now().astimezone(patient_tz).date()

    # Auto-generate today's dose events
    generate_daily_dose_events(profile, today)

    # Query today's events in patient's local day
    day_start = timezone.datetime.combine(
        today, timezone.datetime.min.time(), tzinfo=patient_tz,
    )
    day_end = day_start + timedelta(days=1)

    dose_events = (
        DoseEvent.objects
        .filter(
            regimen__patient=profile,
            scheduled_time__gte=day_start,
            scheduled_time__lt=day_end,
        )
        .select_related('medication', 'regimen')
        .order_by('scheduled_time')
    )

    # Adherence statistics
    total = dose_events.count()
    taken = dose_events.filter(status__in=['TAKEN', 'TAKEN_LATE']).count()
    pending = dose_events.filter(status__in=['SCHEDULED', 'REMINDED']).count()
    missed = dose_events.filter(status='MISSED').count()
    skipped = dose_events.filter(status='SKIPPED').count()

    # Low-stock alerts
    low_stock_meds = []
    for med in Medication.objects.filter(patient=profile, is_active=True):
        if check_reorder_needed(med):
            low_stock_meds.append({
                'medication': med,
                'days_remaining': calculate_days_remaining(med),
            })

    context = {
        'dose_events': dose_events,
        'today': today,
        'patient_tz': str(patient_tz),
        'stats': {
            'total': total,
            'taken': taken,
            'pending': pending,
            'missed': missed,
            'skipped': skipped,
            'adherence': round((taken / total * 100) if total > 0 else 0),
        },
        'low_stock_meds': low_stock_meds,
    }
    return render(request, 'medtrack/dashboard.html', context)


# ──────────────────────────────────────────────
# Dose Actions (HTMX endpoints)
# ──────────────────────────────────────────────

@login_required
@require_POST
def dose_take_view(request, pk):
    """Mark a dose as taken (atomic stock decrement)."""
    dose_event = get_object_or_404(
        DoseEvent.objects.select_related('medication', 'regimen', 'regimen__patient'),
        pk=pk,
        regimen__patient__user=request.user,
    )

    if dose_event.is_actionable:
        dose_event = record_dose_taken(dose_event)
        # Refresh related objects after atomic update
        dose_event.refresh_from_db()

    return render(request, 'medtrack/partials/dose_card.html', {
        'event': dose_event,
        'patient_tz': str(dose_event.regimen.patient.timezone),
    })


@login_required
@require_POST
def dose_skip_view(request, pk):
    """Mark a dose as skipped."""
    dose_event = get_object_or_404(
        DoseEvent.objects.select_related('medication', 'regimen', 'regimen__patient'),
        pk=pk,
        regimen__patient__user=request.user,
    )

    if dose_event.is_actionable:
        dose_event.status = 'SKIPPED'
        dose_event.save()

    return render(request, 'medtrack/partials/dose_card.html', {
        'event': dose_event,
        'patient_tz': str(dose_event.regimen.patient.timezone),
    })


# ──────────────────────────────────────────────
# Medication CRUD
# ──────────────────────────────────────────────

@login_required
def medication_list_view(request):
    """Medication inventory with burn rates and reorder alerts."""
    profile = _get_patient_profile(request.user)
    medications = Medication.objects.filter(patient=profile)

    med_data = []
    for med in medications:
        burn_rate = calculate_burn_rate(med)
        days_remaining = calculate_days_remaining(med)
        needs_reorder = check_reorder_needed(med)

        # Stock percentage for progress bar
        if days_remaining is not None and days_remaining > 0:
            max_days = max(
                days_remaining,
                med.reorder_threshold + med.lead_time_days + 10,
            )
            stock_pct = min(100, int((days_remaining / max_days) * 100))
        elif med.current_stock > 0 and days_remaining is None:
            stock_pct = 100
        else:
            stock_pct = 0

        med_data.append({
            'medication': med,
            'burn_rate': burn_rate,
            'days_remaining': days_remaining,
            'needs_reorder': needs_reorder,
            'stock_pct': stock_pct,
        })

    return render(request, 'medtrack/medication_list.html', {'med_data': med_data})


@login_required
def medication_create_view(request):
    """Add a new medication."""
    profile = _get_patient_profile(request.user)

    if request.method == 'POST':
        form = MedicationForm(request.POST)
        if form.is_valid():
            medication = form.save(commit=False)
            medication.patient = profile
            medication.save()
            messages.success(request, f'"{medication.name}" added to your inventory.')
            return redirect('medtrack:medication_list')
    else:
        form = MedicationForm()

    return render(request, 'medtrack/medication_form.html', {
        'form': form,
        'title': 'Add Medication',
    })


@login_required
def medication_update_view(request, pk):
    """Edit an existing medication."""
    profile = _get_patient_profile(request.user)
    medication = get_object_or_404(Medication, pk=pk, patient=profile)

    if request.method == 'POST':
        form = MedicationForm(request.POST, instance=medication)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{medication.name}" updated.')
            return redirect('medtrack:medication_list')
    else:
        form = MedicationForm(instance=medication)

    return render(request, 'medtrack/medication_form.html', {
        'form': form,
        'title': 'Edit Medication',
        'medication': medication,
    })


@login_required
def medication_delete_view(request, pk):
    """Delete a medication (with confirmation)."""
    profile = _get_patient_profile(request.user)
    medication = get_object_or_404(Medication, pk=pk, patient=profile)

    if request.method == 'POST':
        name = medication.name
        medication.delete()
        messages.success(request, f'"{name}" removed from inventory.')
        return redirect('medtrack:medication_list')

    return render(request, 'medtrack/medication_confirm_delete.html', {
        'medication': medication,
    })


# ──────────────────────────────────────────────
# Regimen CRUD
# ──────────────────────────────────────────────

@login_required
def regimen_list_view(request):
    """List all dosing regimens."""
    profile = _get_patient_profile(request.user)
    regimens = (
        Regimen.objects
        .filter(patient=profile)
        .select_related('medication')
    )
    return render(request, 'medtrack/regimen_list.html', {'regimens': regimens})


@login_required
def regimen_create_view(request):
    """Create a new dosing regimen."""
    profile = _get_patient_profile(request.user)

    if request.method == 'POST':
        form = RegimenForm(request.POST, patient=profile)
        if form.is_valid():
            regimen = form.save(commit=False)
            regimen.patient = profile
            regimen.save()
            messages.success(request, f'Regimen for "{regimen.medication.name}" created!')
            return redirect('medtrack:regimen_list')
    else:
        form = RegimenForm(patient=profile)

    return render(request, 'medtrack/regimen_form.html', {
        'form': form,
        'title': 'Add Regimen',
    })


@login_required
def regimen_update_view(request, pk):
    """Edit an existing regimen."""
    profile = _get_patient_profile(request.user)
    regimen = get_object_or_404(Regimen, pk=pk, patient=profile)

    if request.method == 'POST':
        form = RegimenForm(request.POST, instance=regimen, patient=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Regimen updated!')
            return redirect('medtrack:regimen_list')
    else:
        form = RegimenForm(instance=regimen, patient=profile)

    return render(request, 'medtrack/regimen_form.html', {
        'form': form,
        'title': 'Edit Regimen',
        'regimen': regimen,
    })


@login_required
def regimen_delete_view(request, pk):
    """Delete a regimen (with confirmation)."""
    profile = _get_patient_profile(request.user)
    regimen = get_object_or_404(Regimen, pk=pk, patient=profile)

    if request.method == 'POST':
        regimen.delete()
        messages.success(request, 'Regimen deleted.')
        return redirect('medtrack:regimen_list')

    return render(request, 'medtrack/regimen_confirm_delete.html', {
        'regimen': regimen,
    })


# ──────────────────────────────────────────────
# Caregiver CRUD
# ──────────────────────────────────────────────

@login_required
def caregiver_list_view(request):
    """List all caregiver contacts."""
    profile = _get_patient_profile(request.user)
    caregivers = CaregiverContact.objects.filter(patient=profile)
    return render(request, 'medtrack/caregiver_list.html', {
        'caregivers': caregivers,
    })


@login_required
def caregiver_create_view(request):
    """Add a new caregiver contact."""
    profile = _get_patient_profile(request.user)

    if request.method == 'POST':
        form = CaregiverContactForm(request.POST)
        if form.is_valid():
            caregiver = form.save(commit=False)
            caregiver.patient = profile
            caregiver.save()
            messages.success(request, f'"{caregiver.name}" added as caregiver.')
            return redirect('medtrack:caregiver_list')
    else:
        form = CaregiverContactForm()

    return render(request, 'medtrack/caregiver_form.html', {
        'form': form,
        'title': 'Add Caregiver',
    })


@login_required
def caregiver_update_view(request, pk):
    """Edit an existing caregiver contact."""
    profile = _get_patient_profile(request.user)
    caregiver = get_object_or_404(CaregiverContact, pk=pk, patient=profile)

    if request.method == 'POST':
        form = CaregiverContactForm(request.POST, instance=caregiver)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{caregiver.name}" updated.')
            return redirect('medtrack:caregiver_list')
    else:
        form = CaregiverContactForm(instance=caregiver)

    return render(request, 'medtrack/caregiver_form.html', {
        'form': form,
        'title': 'Edit Caregiver',
        'caregiver': caregiver,
    })


@login_required
def caregiver_delete_view(request, pk):
    """Delete a caregiver contact."""
    profile = _get_patient_profile(request.user)
    caregiver = get_object_or_404(CaregiverContact, pk=pk, patient=profile)

    if request.method == 'POST':
        name = caregiver.name
        caregiver.delete()
        messages.success(request, f'"{name}" removed from caregivers.')
        return redirect('medtrack:caregiver_list')

    return render(request, 'medtrack/caregiver_confirm_delete.html', {
        'caregiver': caregiver,
    })


# ──────────────────────────────────────────────
# Clinical Reports
# ──────────────────────────────────────────────

@login_required
def adherence_report_view(request):
    """View and print/download 30-day clinical adherence report."""
    profile = _get_patient_profile(request.user)
    as_pdf = request.GET.get('format') == 'pdf'
    content, content_type = render_pdf_or_html(profile, days=30, as_pdf=as_pdf)

    response = HttpResponse(content, content_type=content_type)
    if as_pdf and content_type == 'application/pdf':
        response['Content-Disposition'] = f'attachment; filename="adherence_report_{profile.user.username}.pdf"'
    return response
