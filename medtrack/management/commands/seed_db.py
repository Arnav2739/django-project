"""
Smart MedTrack — Seed Database Command

Creates deterministic test data for development and demonstration.

Usage:
    python manage.py seed_db
    python manage.py seed_db --flush   # Clear existing data first
"""
import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from medtrack.models import (
    CaregiverContact,
    DoseEvent,
    Medication,
    PatientProfile,
    PatientRoutine,
    Regimen,
)
from medtrack.services.scheduling import generate_daily_dose_events


class Command(BaseCommand):
    help = 'Seed the database with sample patient data for development.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete all existing medtrack data before seeding.',
        )

    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write(self.style.WARNING('Flushing existing data...'))
            DoseEvent.objects.all().delete()
            Regimen.objects.all().delete()
            Medication.objects.all().delete()
            CaregiverContact.objects.all().delete()
            PatientRoutine.objects.all().delete()
            PatientProfile.objects.all().delete()
            User.objects.filter(username__in=['patient1', 'patient2']).delete()

        self.stdout.write('Creating test users...')

        # ── Patient 1: Ramesh Patel ──────────────
        user1, created = User.objects.get_or_create(
            username='patient1',
            defaults={
                'first_name': 'Ramesh',
                'last_name': 'Patel',
                'email': 'ramesh.patel@example.com',
            },
        )
        if created:
            user1.set_password('medtrack123')
            user1.save()

        profile1, _ = PatientProfile.objects.get_or_create(
            user=user1,
            defaults={
                'timezone': 'Asia/Kolkata',
                'emergency_phone': '+91 98765 43210',
                'primary_physician': 'Dr. Anjali Sharma',
            },
        )

        routine1, _ = PatientRoutine.objects.get_or_create(
            patient=profile1,
            defaults={
                'breakfast_time': datetime.time(8, 0),
                'lunch_time': datetime.time(13, 0),
                'dinner_time': datetime.time(19, 30),
                'bedtime': datetime.time(22, 0),
            },
        )

        # Medications for Patient 1
        med1, _ = Medication.objects.get_or_create(
            patient=profile1,
            name='Metformin 500mg',
            defaults={
                'generic_name': 'Metformin Hydrochloride',
                'dosage_unit': 'TABLETS',
                'current_stock': 45,
                'reorder_threshold': 7,
                'lead_time_days': 3,
                'notes': 'Take with meals. Avoid alcohol.',
            },
        )

        med2, _ = Medication.objects.get_or_create(
            patient=profile1,
            name='Amlodipine 5mg',
            defaults={
                'generic_name': 'Amlodipine Besylate',
                'dosage_unit': 'TABLETS',
                'current_stock': 12,
                'reorder_threshold': 7,
                'lead_time_days': 2,
                'notes': 'For blood pressure management.',
            },
        )

        med3, _ = Medication.objects.get_or_create(
            patient=profile1,
            name='Vitamin D3 60K',
            defaults={
                'generic_name': 'Cholecalciferol',
                'dosage_unit': 'SACHETS',
                'current_stock': 4,
                'reorder_threshold': 4,
                'lead_time_days': 5,
                'notes': 'Weekly dose, take after lunch.',
            },
        )

        med4, _ = Medication.objects.get_or_create(
            patient=profile1,
            name='Pantoprazole 40mg',
            defaults={
                'generic_name': 'Pantoprazole Sodium',
                'dosage_unit': 'TABLETS',
                'current_stock': 30,
                'reorder_threshold': 7,
                'lead_time_days': 2,
                'notes': 'Take 30 minutes before breakfast on empty stomach.',
            },
        )

        # Regimens for Patient 1
        Regimen.objects.get_or_create(
            patient=profile1,
            medication=med1,
            anchor='BREAKFAST',
            defaults={
                'dose_quantity': 1,
                'offset_minutes': 0,
                'frequency': 'DAILY',
                'is_active': True,
            },
        )
        Regimen.objects.get_or_create(
            patient=profile1,
            medication=med1,
            anchor='DINNER',
            defaults={
                'dose_quantity': 1,
                'offset_minutes': 0,
                'frequency': 'DAILY',
                'is_active': True,
            },
        )
        Regimen.objects.get_or_create(
            patient=profile1,
            medication=med2,
            anchor='BEDTIME',
            defaults={
                'dose_quantity': 1,
                'offset_minutes': 0,
                'frequency': 'DAILY',
                'is_active': True,
            },
        )
        Regimen.objects.get_or_create(
            patient=profile1,
            medication=med3,
            anchor='LUNCH',
            defaults={
                'dose_quantity': 1,
                'offset_minutes': 30,
                'frequency': 'WEEKLY',
                'specific_days': [6],  # Sunday
                'is_active': True,
            },
        )
        Regimen.objects.get_or_create(
            patient=profile1,
            medication=med4,
            anchor='BREAKFAST',
            defaults={
                'dose_quantity': 1,
                'offset_minutes': -30,
                'frequency': 'DAILY',
                'is_active': True,
            },
        )

        # Caregivers for Patient 1
        CaregiverContact.objects.get_or_create(
            patient=profile1,
            name='Priya Patel',
            defaults={
                'relationship': 'CHILD',
                'phone_number': '+91 98765 11111',
                'email': 'priya.patel@example.com',
                'priority_tier': 1,
            },
        )
        CaregiverContact.objects.get_or_create(
            patient=profile1,
            name='Nurse Kavita',
            defaults={
                'relationship': 'NURSE',
                'phone_number': '+91 98765 22222',
                'email': 'kavita.nurse@example.com',
                'priority_tier': 2,
            },
        )

        # ── Patient 2: Sarah Johnson ──────────────
        user2, created = User.objects.get_or_create(
            username='patient2',
            defaults={
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'email': 'sarah.johnson@example.com',
            },
        )
        if created:
            user2.set_password('medtrack123')
            user2.save()

        profile2, _ = PatientProfile.objects.get_or_create(
            user=user2,
            defaults={
                'timezone': 'America/New_York',
                'emergency_phone': '+1 555-0123',
                'primary_physician': 'Dr. Michael Chen',
            },
        )

        routine2, _ = PatientRoutine.objects.get_or_create(
            patient=profile2,
            defaults={
                'breakfast_time': datetime.time(7, 30),
                'lunch_time': datetime.time(12, 0),
                'dinner_time': datetime.time(18, 30),
                'bedtime': datetime.time(22, 30),
            },
        )

        med5, _ = Medication.objects.get_or_create(
            patient=profile2,
            name='Lisinopril 10mg',
            defaults={
                'generic_name': 'Lisinopril',
                'dosage_unit': 'TABLETS',
                'current_stock': 28,
                'reorder_threshold': 7,
                'lead_time_days': 3,
            },
        )

        med6, _ = Medication.objects.get_or_create(
            patient=profile2,
            name='Albuterol Inhaler',
            defaults={
                'generic_name': 'Albuterol Sulfate',
                'dosage_unit': 'PUFFS',
                'current_stock': 80,
                'reorder_threshold': 10,
                'lead_time_days': 5,
                'notes': '2 puffs as needed. Max 8 puffs/day.',
            },
        )

        Regimen.objects.get_or_create(
            patient=profile2,
            medication=med5,
            anchor='BREAKFAST',
            defaults={
                'dose_quantity': 1,
                'offset_minutes': -15,
                'frequency': 'DAILY',
                'is_active': True,
            },
        )

        Regimen.objects.get_or_create(
            patient=profile2,
            medication=med6,
            anchor='CUSTOM',
            defaults={
                'dose_quantity': 2,
                'offset_minutes': 0,
                'fixed_time': datetime.time(9, 0),
                'frequency': 'ALTERNATE',
                'is_active': True,
            },
        )

        CaregiverContact.objects.get_or_create(
            patient=profile2,
            name='Tom Johnson',
            defaults={
                'relationship': 'SPOUSE',
                'phone_number': '+1 555-0456',
                'email': 'tom.johnson@example.com',
                'priority_tier': 1,
            },
        )

        # Generate today's dose events for both patients
        from django.utils import timezone as tz
        from zoneinfo import ZoneInfo

        for profile in [profile1, profile2]:
            patient_tz = ZoneInfo(profile.timezone)
            today = tz.now().astimezone(patient_tz).date()
            events = generate_daily_dose_events(profile, today)
            self.stdout.write(
                f'  Generated {len(events)} dose events for '
                f'{profile.user.get_full_name()} on {today}'
            )

        self.stdout.write(self.style.SUCCESS(
            '\n[OK] Database seeded successfully!\n'
            '\n  Test accounts:'
            '\n  ---------------------------------'
            '\n  Username: patient1'
            '\n  Password: medtrack123'
            '\n  (Ramesh Patel - IST timezone)'
            '\n'
            '\n  Username: patient2'
            '\n  Password: medtrack123'
            '\n  (Sarah Johnson - EST timezone)'
            '\n  ---------------------------------'
        ))
