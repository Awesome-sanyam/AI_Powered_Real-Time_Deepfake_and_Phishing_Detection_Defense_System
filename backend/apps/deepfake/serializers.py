"""Deepfake app serializers."""
from rest_framework import serializers
from .models import DeepfakeScanSession


class DeepfakeScanSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeepfakeScanSession
        fields = [
            "id", "session_id", "is_deepfake", "confidence",
            "frame_count", "processing_time_ms",
            "signed_verdict", "public_key_pem",
            "created_at", "updated_at",
        ]
        read_only_fields = fields
