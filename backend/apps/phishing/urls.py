"""Phishing app URL patterns."""
from django.urls import path
from .views import PhishingScanListView, PhishingScanDetailView

urlpatterns = [
    path("scans/", PhishingScanListView.as_view(), name="phishing-scan-list"),
    path("scans/<int:pk>/", PhishingScanDetailView.as_view(), name="phishing-scan-detail"),
]
