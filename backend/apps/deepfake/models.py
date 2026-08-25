"""Deepfake app models."""
from django.db import models
from apps.core.models import TimeStampedModel


class DeepfakeScanSession(TimeStampedModel):
    """Represents one deepfake scanning session (maps to a WebSocket connection)."""

    session_id = models.CharField(max_length=64, unique=True, db_index=True)
    is_deepfake = models.BooleanField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    frame_count = models.PositiveIntegerField(default=0)
    processing_time_ms = models.FloatField(null=True, blank=True)
    signed_verdict = models.TextField(blank=True, default="")
    public_key_pem = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Deepfake Scan Session"

    def __str__(self) -> str:
        status = "FAKE" if self.is_deepfake else "REAL" if self.is_deepfake is False else "PENDING"
        return f"[{status}] {self.session_id[:8]}… conf={self.confidence}"
