"""Threat graph serializers."""
from rest_framework import serializers
from .models import ThreatNode


class ThreatNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThreatNode
        fields = ["id", "neo4j_id", "node_type", "label", "risk_score", "metadata", "created_at"]
        read_only_fields = fields
