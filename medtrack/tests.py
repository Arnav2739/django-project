"""
Smart MedTrack — Test Suite

Unit and integration tests for models, scheduling engine, inventory
tracking, and views.
"""
import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

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
from .services.scheduling import (
    calculate_intake_time,
    generate_daily_dose_events,
)


class MedTrackTestCase(TestCase):
    """Base setup for MedTrack tests with an authenticated patient user."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testpatient',
            password='testpassword123',
            first_name='John',
            last_name='Doe',
            email='john@example.com',
        )
        self.profile = PatientProfile.objects.create(
            user=self.user,
            timezone='Asia/Kolkata',
            emergency_phone='+91 99999 88888',
        )
        self.routine = PatientRoutine.objects.create(
            patient=self.profile,
            breakfast_time=datetime.time(8, 0),
            lunch_time=datetime.time(13, 0),
            dinner_time=datetime.time(20, 0),
            bedtime=datetime.time(22, 30),
        )
        self.medication = Medication.objects.create(
            patient=self.profile,
            name='Metformin 500mg',
            dosage_unit='TABLETS',
            current_stock=60,
            reorder_threshold=14,
            lead_time_days=3,
        )
        self.regimen = Regimen.objects.create(
            patient=self.profile,
            medication=self.medication,
            dose_quantity=1,
            anchor='BREAKFAST',
            offset_minutes=15,  # 15 min after breakfast
            frequency='DAILY',
        )
        self.client = Client()
        self.client.login(username='testpatient', password='testpassword123')


class SchedulingServiceTests(MedTrackTestCase):
    """Tests for dose calculation and event generation."""

    def test_calculate_intake_time_breakfast_offset(self):
        target_date = datetime.date(2026, 10, 5)
        # Breakfast is 08:00 IST + 15 min offset = 08:15 IST
        intake_utc = calculate_intake_time(self.regimen, self.routine, target_date)
        # Convert to IST to verify
        ist = ZoneInfo('Asia/Kolkata')
        intake_ist = intake_utc.astimezone(ist)
        self.assertEqual(intake_ist.hour, 8)
        self.assertEqual(intake_ist.minute, 15)
        self.assertEqual(intake_ist.date(), target_date)

    def test_calculate_intake_time_custom_fixed(self):
        custom_regimen = Regimen.objects.create(
            patient=self.profile,
            medication=self.medication,
            dose_quantity=2,
            anchor='CUSTOM',
            fixed_time=datetime.time(14, 45),
            frequency='DAILY',
        )
        target_date = datetime.date(2026, 10, 5)
        intake_utc = calculate_intake_time(custom_regimen, self.routine, target_date)
        ist = ZoneInfo('Asia/Kolkata')
        intake_ist = intake_utc.astimezone(ist)
        self.assertEqual(intake_ist.hour, 14)
        self.assertEqual(intake_ist.minute, 45)

    def test_generate_daily_dose_events_idempotent(self):
        target_date = datetime.date(2026, 10, 5)
        events_1 = generate_daily_dose_events(self.profile, target_date)
        self.assertEqual(len(events_1), 1)

        # Generating again should not create duplicates
        events_2 = generate_daily_dose_events(self.profile, target_date)
        self.assertEqual(len(events_2), 0)
        self.assertEqual(DoseEvent.objects.filter(regimen=self.regimen).count(), 1)


class InventoryServiceTests(MedTrackTestCase):
    """Tests for burn rate, days remaining, and atomic stock decrement."""

    def test_record_dose_taken_decrements_stock(self):
        target_date = datetime.date(2026, 10, 5)
        generate_daily_dose_events(self.profile, target_date)
        event = DoseEvent.objects.get(regimen=self.regimen)
        # Set scheduled_time to current time so it is recorded as TAKEN (not late)
        event.scheduled_time = timezone.now()
        event.save()

        initial_stock = self.medication.current_stock
        updated_event = record_dose_taken(event)

        self.assertEqual(updated_event.status, 'TAKEN')
        self.assertIsNotNone(updated_event.taken_at)
        self.medication.refresh_from_db()
        self.assertEqual(self.medication.current_stock, initial_stock - self.regimen.dose_quantity)

    def test_burn_rate_and_reorder_calculation(self):
        # 1 dose per day
        burn_rate = calculate_burn_rate(self.medication)
        self.assertEqual(burn_rate, 1.0)

        # 60 stock / 1 per day = 60 days
        days = calculate_days_remaining(self.medication)
        self.assertEqual(days, 60)
        self.assertFalse(check_reorder_needed(self.medication))

        # Drop stock below reorder threshold (lead_time_days (3) + buffer (3) = 6 days)
        self.medication.current_stock = 5
        self.medication.save()
        self.assertTrue(check_reorder_needed(self.medication))


class ViewsAndTemplateTests(MedTrackTestCase):
    """Tests for all endpoints and rendering of UI templates."""

    def test_dashboard_renders(self):
        response = self.client.get(reverse('medtrack:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'Metformin 500mg')

    def test_dose_take_endpoint(self):
        target_date = timezone.now().astimezone(ZoneInfo(self.profile.timezone)).date()
        generate_daily_dose_events(self.profile, target_date)
        event = DoseEvent.objects.get(regimen=self.regimen)
        event.scheduled_time = timezone.now()
        event.save()

        response = self.client.post(reverse('medtrack:dose_take', args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.status, 'TAKEN')

    def test_dose_skip_endpoint(self):
        target_date = timezone.now().astimezone(ZoneInfo(self.profile.timezone)).date()
        generate_daily_dose_events(self.profile, target_date)
        event = DoseEvent.objects.get(regimen=self.regimen)

        response = self.client.post(reverse('medtrack:dose_skip', args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.status, 'SKIPPED')

    def test_medication_crud_views(self):
        # List
        resp = self.client.get(reverse('medtrack:medication_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Metformin 500mg')

        # Create
        create_resp = self.client.post(reverse('medtrack:medication_create'), {
            'name': 'Lisinopril 10mg',
            'generic_name': 'Lisinopril',
            'dosage_unit': 'TABLETS',
            'current_stock': 30,
            'reorder_threshold': 7,
            'lead_time_days': 2,
            'notes': 'Take in the morning',
        })
        self.assertRedirects(create_resp, reverse('medtrack:medication_list'))
        self.assertTrue(Medication.objects.filter(name='Lisinopril 10mg').exists())

        # Update
        new_med = Medication.objects.get(name='Lisinopril 10mg')
        update_resp = self.client.post(reverse('medtrack:medication_update', args=[new_med.pk]), {
            'name': 'Lisinopril 20mg',
            'generic_name': 'Lisinopril',
            'dosage_unit': 'TABLETS',
            'current_stock': 45,
            'reorder_threshold': 7,
            'lead_time_days': 2,
        })
        self.assertRedirects(update_resp, reverse('medtrack:medication_list'))
        new_med.refresh_from_db()
        self.assertEqual(new_med.name, 'Lisinopril 20mg')

        # Delete confirmation page
        del_confirm = self.client.get(reverse('medtrack:medication_delete', args=[new_med.pk]))
        self.assertEqual(del_confirm.status_code, 200)

        # Delete POST
        del_resp = self.client.post(reverse('medtrack:medication_delete', args=[new_med.pk]))
        self.assertRedirects(del_resp, reverse('medtrack:medication_list'))
        self.assertFalse(Medication.objects.filter(name='Lisinopril 20mg').exists())

    def test_regimen_crud_views(self):
        # List
        resp = self.client.get(reverse('medtrack:regimen_list'))
        self.assertEqual(resp.status_code, 200)

        # Create
        create_resp = self.client.post(reverse('medtrack:regimen_create'), {
            'medication': self.medication.pk,
            'dose_quantity': 1,
            'anchor': 'DINNER',
            'offset_minutes': 0,
            'frequency': 'DAILY',
        })
        self.assertRedirects(create_resp, reverse('medtrack:regimen_list'))
        self.assertEqual(Regimen.objects.filter(patient=self.profile).count(), 2)

        # Delete
        regimen2 = Regimen.objects.filter(anchor='DINNER').first()
        del_resp = self.client.post(reverse('medtrack:regimen_delete', args=[regimen2.pk]))
        self.assertRedirects(del_resp, reverse('medtrack:regimen_list'))
        self.assertEqual(Regimen.objects.filter(patient=self.profile).count(), 1)

    def test_caregiver_crud_views(self):
        # Create
        create_resp = self.client.post(reverse('medtrack:caregiver_create'), {
            'name': 'Dr. Priya Sharma',
            'relationship': 'NURSE',
            'phone_number': '+91 98765 00000',
            'email': 'priya@example.com',
            'priority_tier': 1,
        })
        self.assertRedirects(create_resp, reverse('medtrack:caregiver_list'))
        self.assertEqual(CaregiverContact.objects.filter(patient=self.profile).count(), 1)

        # List
        resp = self.client.get(reverse('medtrack:caregiver_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Dr. Priya Sharma')

        # Profile Setup
        prof_resp = self.client.get(reverse('medtrack:profile_setup'))
        self.assertEqual(prof_resp.status_code, 200)
        self.assertContains(prof_resp, 'Routine & Patient Profile')

        # Adherence Report
        report_resp = self.client.get(reverse('medtrack:adherence_report'))
        self.assertEqual(report_resp.status_code, 200)
        self.assertContains(report_resp, 'Clinical Medication Adherence Report')
        self.assertContains(report_resp, 'Metformin 500mg')


class EscalationEngineTests(MedTrackTestCase):
    """Tests for two-tier clinical escalation and Celery background tasks."""

    def setUp(self):
        super().setUp()
        self.caregiver1 = CaregiverContact.objects.create(
            patient=self.profile,
            name='Rajesh Doe',
            relationship='SPOUSE',
            phone_number='+91 98765 11111',
            email='rajesh@example.com',
            priority_tier=1,
        )
        self.caregiver2 = CaregiverContact.objects.create(
            patient=self.profile,
            name='Anita Doe',
            relationship='CHILD',
            phone_number='+91 98765 22222',
            email='anita@example.com',
            priority_tier=2,
        )

    def test_tier1_escalation_on_overdue_dose(self):
        from .services.escalation import process_missed_doses

        # Create an event scheduled 45 minutes ago
        past_time = timezone.now() - datetime.timedelta(minutes=45)
        event = DoseEvent.objects.create(
            regimen=self.regimen,
            medication=self.medication,
            scheduled_time=past_time,
            status='SCHEDULED',
        )

        escalated_events = process_missed_doses()
        self.assertIn(event, escalated_events)

        event.refresh_from_db()
        self.assertEqual(event.status, 'MISSED')
        self.assertIsNotNone(event.escalated_at)
        self.assertIn('Tier 1 escalation dispatched', event.notes)

    def test_tier2_escalation_after_unresolved_delay(self):
        from .services.escalation import process_secondary_escalations

        # Create a missed event escalated 35 minutes ago
        past_time = timezone.now() - datetime.timedelta(minutes=70)
        past_escalated = timezone.now() - datetime.timedelta(minutes=35)

        event = DoseEvent.objects.create(
            regimen=self.regimen,
            medication=self.medication,
            scheduled_time=past_time,
            status='MISSED',
            escalated_at=past_escalated,
            notes='Tier 1 escalation dispatched.',
        )

        tier2_escalated = process_secondary_escalations()
        self.assertIn(event, tier2_escalated)

        event.refresh_from_db()
        self.assertIn('Tier 2 escalation dispatched', event.notes)

    def test_celery_evaluate_missed_doses_task(self):
        from .tasks import evaluate_missed_doses

        result = evaluate_missed_doses()
        self.assertIn('tier1_escalations', result)
        self.assertIn('tier2_escalations', result)

