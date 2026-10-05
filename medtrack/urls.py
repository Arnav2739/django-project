"""
Smart MedTrack — URL Configuration

Maps all view functions to their URL patterns.
Uses the 'medtrack' app namespace for reverse URL resolution.
"""
from django.urls import path

from . import views

app_name = 'medtrack'

urlpatterns = [
    # ── Authentication ────────────────────────
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/setup/', views.profile_setup_view, name='profile_setup'),

    # ── Dashboard ─────────────────────────────
    path('', views.dashboard_view, name='dashboard'),

    # ── Dose Actions (HTMX) ──────────────────
    path('dose/<int:pk>/take/', views.dose_take_view, name='dose_take'),
    path('dose/<int:pk>/skip/', views.dose_skip_view, name='dose_skip'),

    # ── Medications ───────────────────────────
    path('medications/', views.medication_list_view, name='medication_list'),
    path('medications/add/', views.medication_create_view, name='medication_create'),
    path('medications/<int:pk>/edit/', views.medication_update_view, name='medication_update'),
    path('medications/<int:pk>/delete/', views.medication_delete_view, name='medication_delete'),

    # ── Regimens ──────────────────────────────
    path('regimens/', views.regimen_list_view, name='regimen_list'),
    path('regimens/add/', views.regimen_create_view, name='regimen_create'),
    path('regimens/<int:pk>/edit/', views.regimen_update_view, name='regimen_update'),
    path('regimens/<int:pk>/delete/', views.regimen_delete_view, name='regimen_delete'),

    # ── Caregivers ────────────────────────────
    path('caregivers/', views.caregiver_list_view, name='caregiver_list'),
    path('caregivers/add/', views.caregiver_create_view, name='caregiver_create'),
    path('caregivers/<int:pk>/edit/', views.caregiver_update_view, name='caregiver_update'),
    path('caregivers/<int:pk>/delete/', views.caregiver_delete_view, name='caregiver_delete'),

    # ── Reports ───────────────────────────────
    path('reports/adherence/', views.adherence_report_view, name='adherence_report'),
]
