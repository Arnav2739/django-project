"""
Core URL Configuration for Smart MedTrack.

Routes the admin interface and includes all medtrack app URLs at root.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('medtrack.urls')),
]
