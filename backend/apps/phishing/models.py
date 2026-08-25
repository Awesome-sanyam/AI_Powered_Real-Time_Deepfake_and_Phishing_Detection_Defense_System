"""Phishing app models."""
from django.db import models
from apps.core.models import TimeStampedModel


class PhishingScan(TimeStampedModel):
    """Records a single phishing analysis result."""

    session_id = models.CharField(max_length=64, db_index=True)
    content_hash = models.CharField(max_length=64, blank=True)  # SHA-256 of scanned content
    is_phishing = models.BooleanField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    risk_level = models.CharField(
        max_length=16, blank=True,
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
    )
    signals = models.JSONField(default=list)
    explanation = models.TextField(blank=True)
    url = models.URLField(max_length=2000, blank=True)
    signed_verdict = models.TextField(blank=True)
    public_key_pem = models.TextField(blank=True)
    processing_time_ms = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Phishing Scan"

    def __str__(self) -> str:
        status = "PHISH" if self.is_phishing else "CLEAN" if self.is_phishing is False else "PENDING"
        return f"[{status}] {self.session_id[:8]}… conf={self.confidence}"
