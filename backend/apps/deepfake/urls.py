"""Deepfake app URL patterns."""
from django.urls import path
from .views import DeepfakeScanSessionListView, DeepfakeScanSessionDetailView

urlpatterns = [
    path("sessions/", DeepfakeScanSessionListView.as_view(), name="deepfake-session-list"),
    path("sessions/<str:session_id>/", DeepfakeScanSessionDetailView.as_view(), name="deepfake-session-detail"),
]
