"""Threat graph URL patterns."""
from django.urls import path
from .views import GraphHealthView, HighRiskNodesView, ThreatNodeListView

urlpatterns = [
    path("nodes/",     ThreatNodeListView.as_view(), name="threat-node-list"),
    path("high-risk/", HighRiskNodesView.as_view(),  name="threat-high-risk"),
    path("health/",    GraphHealthView.as_view(),     name="threat-graph-health"),
]
