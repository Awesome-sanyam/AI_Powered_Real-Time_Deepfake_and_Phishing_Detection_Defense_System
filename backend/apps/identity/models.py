"""Identity app models — ECDSA key pairs per verified user."""
from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import TimeStampedModel

User = get_user_model()


class IdentityKey(TimeStampedModel):
    """Stores the ECDSA public key for a verified user."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="identity_key")
    public_key_pem = models.TextField()
    fingerprint = models.CharField(max_length=64, unique=True)  # SHA-256 of public key bytes
    is_revoked = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Identity Key"

    def __str__(self) -> str:
        return f"{self.user.username} — {'REVOKED' if self.is_revoked else 'ACTIVE'}"
