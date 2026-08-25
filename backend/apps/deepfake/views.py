"""Deepfake app views."""
from rest_framework import generics
from .models import DeepfakeScanSession
from .serializers import DeepfakeScanSessionSerializer


class DeepfakeScanSessionListView(generics.ListAPIView):
    """GET /api/deepfake/sessions/ — list all scan sessions (newest first)."""
    queryset = DeepfakeScanSession.objects.all()
    serializer_class = DeepfakeScanSessionSerializer


class DeepfakeScanSessionDetailView(generics.RetrieveAPIView):
    """GET /api/deepfake/sessions/<session_id>/ — retrieve a single session."""
    queryset = DeepfakeScanSession.objects.all()
    serializer_class = DeepfakeScanSessionSerializer
    lookup_field = "session_id"
