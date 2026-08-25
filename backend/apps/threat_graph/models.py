"""Threat graph models — Neo4j node/relationship metadata mirrored in Postgres."""
from django.db import models
from apps.core.models import TimeStampedModel


class ThreatNode(TimeStampedModel):
    """Represents a threat entity (IP, domain, actor, session) in the Neo4j graph."""

    NODE_TYPES = [
        ("ip", "IP Address"),
        ("domain", "Domain"),
        ("email", "Email Address"),
        ("session", "Scan Session"),
        ("actor", "Threat Actor"),
    ]

    neo4j_id = models.CharField(max_length=64, unique=True, db_index=True)
    node_type = models.CharField(max_length=16, choices=NODE_TYPES)
    label = models.CharField(max_length=256)
    risk_score = models.FloatField(default=0.0)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ["-risk_score", "-created_at"]
        verbose_name = "Threat Node"

    def __str__(self) -> str:
        return f"[{self.node_type.upper()}] {self.label} (risk={self.risk_score:.2f})"
