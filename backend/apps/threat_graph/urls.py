"""Threat graph URL patterns."""
from django.urls import path
from .views import ThreatNodeListView, HighRiskNodesView

urlpatterns = [
    path("nodes/", ThreatNodeListView.as_view(), name="threat-node-list"),
    path("high-risk/", HighRiskNodesView.as_view(), name="threat-high-risk"),
]
