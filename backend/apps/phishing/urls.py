"""Phishing app URL patterns."""
from django.urls import path
from .views import PhishingScanDetailView, PhishingScanListView, PhishingScanSubmitView

urlpatterns = [
    path("scans/",        PhishingScanListView.as_view(),   name="phishing-scan-list"),
    path("scans/<int:pk>/", PhishingScanDetailView.as_view(), name="phishing-scan-detail"),
    path("scan/",         PhishingScanSubmitView.as_view(),  name="phishing-scan-submit"),
]
