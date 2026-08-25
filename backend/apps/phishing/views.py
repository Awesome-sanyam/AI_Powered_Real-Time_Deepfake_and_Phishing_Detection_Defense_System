"""Phishing app views."""
from rest_framework import generics
from .models import PhishingScan
from .serializers import PhishingScanSerializer


class PhishingScanListView(generics.ListAPIView):
    """GET /api/phishing/scans/ — list all phishing scan results."""
    queryset = PhishingScan.objects.all()
    serializer_class = PhishingScanSerializer


class PhishingScanDetailView(generics.RetrieveAPIView):
    """GET /api/phishing/scans/<pk>/ — retrieve a single scan result."""
    queryset = PhishingScan.objects.all()
    serializer_class = PhishingScanSerializer
