"""Identity app serializers."""
from rest_framework import serializers
from .models import IdentityKey


class IdentityKeySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = IdentityKey
        fields = ["id", "username", "public_key_pem", "fingerprint", "is_revoked", "created_at"]
        read_only_fields = fields
