"""Deepfake app URL patterns."""
from django.urls import path
from .views import (
    DeepfakeScanSessionListView,
    DeepfakeScanSessionDetailView,
    DeepfakeFileUploadView,
    DeepfakeFileScanResultView,
    DeepfakeUploadScanView,
)

urlpatterns = [
    # Live-stream session records
    path("sessions/",                   DeepfakeScanSessionListView.as_view(),   name="deepfake-session-list"),
    path("sessions/<str:session_id>/",  DeepfakeScanSessionDetailView.as_view(), name="deepfake-session-detail"),
    # File upload analysis
    path("upload/",                     DeepfakeFileUploadView.as_view(),        name="deepfake-file-upload"),
    path("upload-scan/",                DeepfakeUploadScanView.as_view(),        name="deepfake-upload-scan"),
    path("file-scan/<str:session_id>/", DeepfakeFileScanResultView.as_view(),    name="deepfake-file-scan-result"),
]
