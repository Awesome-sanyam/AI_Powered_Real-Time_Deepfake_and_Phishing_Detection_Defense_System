"""Identity app business logic — key management service."""
from __future__ import annotations

import hashlib
import logging

from .models import IdentityKey

logger = logging.getLogger(__name__)


def register_identity_key(user, public_key_pem: str) -> IdentityKey:
    """
    Register or update a user's ECDSA public key.

    Args:
        user:           Django User instance.
        public_key_pem: PEM-encoded ECDSA public key string.

    Returns:
        IdentityKey instance (created or updated).
    """
    fingerprint = hashlib.sha256(public_key_pem.encode()).hexdigest()

    key, created = IdentityKey.objects.update_or_create(
        user=user,
        defaults={"public_key_pem": public_key_pem, "fingerprint": fingerprint, "is_revoked": False},
    )
    action = "registered" if created else "updated"
    logger.info(f"Identity key {action} for user={user.username} fingerprint={fingerprint[:16]}…")
    return key


def revoke_identity_key(user) -> bool:
    """Revoke a user's identity key. Returns True if a key was found and revoked."""
    updated = IdentityKey.objects.filter(user=user, is_revoked=False).update(is_revoked=True)
    if updated:
        logger.warning(f"Identity key REVOKED for user={user.username}")
    return bool(updated)
