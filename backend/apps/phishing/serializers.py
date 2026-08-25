"""Phishing app serializers."""
from rest_framework import serializers
from .models import PhishingScan


class PhishingScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhishingScan
        fields = [
            "id", "session_id", "is_phishing", "confidence", "risk_level",
            "signals", "explanation", "url",
            "signed_verdict", "public_key_pem",
            "processing_time_ms", "created_at",
        ]
        read_only_fields = fields
