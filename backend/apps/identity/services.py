"""
Identity App — Business Logic Services
========================================
Django-level wrapper for ECDSA operations.
Bridges the ai_engine ECDSAService with Django's ORM (IdentityKey model).

Public API:
    generate_key_pair_for_user(user)             → (private_pem, IdentityKey)
    register_identity_key(user, public_key_pem)  → IdentityKey
    revoke_identity_key(user)                    → bool
    verify_verdict_signature(pub_pem, payload, sig_hex) → bool

Author: Sanyam Gehlot
"""
from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

from .models import IdentityKey

logger = logging.getLogger(__name__)


def generate_key_pair_for_user(user) -> tuple[str, IdentityKey]:
    """
    Generate a new ECDSA P-256 key pair for a user.

    Stores the public key in the IdentityKey model.
    Returns the private key PEM — the caller is responsible for secure
    delivery to the client. The private key is NEVER persisted by the server.

    Args:
        user: Django User instance.

    Returns:
        Tuple of (private_key_pem: str, identity_key: IdentityKey).
    """
    # Import here to avoid loading cryptography at Django startup
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    private_pem: str = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_pem: str = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    identity_key = register_identity_key(user, public_pem)
    logger.info(f"Generated ECDSA P-256 key pair for user={user.username}")
    return private_pem, identity_key


def register_identity_key(user, public_key_pem: str) -> IdentityKey:
    """
    Register or update a user's ECDSA public key in the database.

    Args:
        user:           Django User instance.
        public_key_pem: PEM-encoded ECDSA public key string.

    Returns:
        IdentityKey instance (created or updated, never revoked).
    """
    fingerprint = hashlib.sha256(public_key_pem.encode()).hexdigest()

    key, created = IdentityKey.objects.update_or_create(
        user=user,
        defaults={
            "public_key_pem": public_key_pem,
            "fingerprint": fingerprint,
            "is_revoked": False,
        },
    )
    action = "registered" if created else "updated"
    logger.info(
        f"Identity key {action} for user={user.username} "
        f"fingerprint={fingerprint[:16]}…"
    )
    return key


def revoke_identity_key(user) -> bool:
    """
    Revoke a user's active identity key.

    Returns:
        True if a key was found and revoked, False if already revoked or absent.
    """
    updated = IdentityKey.objects.filter(user=user, is_revoked=False).update(is_revoked=True)
    if updated:
        logger.warning(f"Identity key REVOKED for user={user.username}")
    else:
        logger.info(f"No active key to revoke for user={user.username}")
    return bool(updated)


def verify_verdict_signature(
    public_key_pem: str,
    payload: str,
    signature_hex: str,
) -> bool:
    """
    Verify an ECDSA-signed AI verdict payload.

    This is a Django-layer wrapper around ECDSAService.verify() that
    can be called from DRF views or Celery tasks without importing
    ai_engine directly (keeps the dependency boundary clean).

    Args:
        public_key_pem:  PEM public key string (from IdentityKey or verdict).
        payload:         The original plaintext string that was signed.
        signature_hex:   Hex-encoded DER signature bytes.

    Returns:
        True if signature is cryptographically valid, False otherwise.
    """
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.exceptions import InvalidSignature

        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        sig_bytes = bytes.fromhex(signature_hex)
        public_key.verify(sig_bytes, payload.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return True
    except Exception as exc:
        logger.warning(f"Verdict signature verification failed: {exc}")
        return False


def get_user_public_key(user) -> str | None:
    """
    Retrieve a user's active ECDSA public key PEM.

    Returns:
        PEM string, or None if no active key exists.
    """
    try:
        key = IdentityKey.objects.get(user=user, is_revoked=False)
        return key.public_key_pem
    except IdentityKey.DoesNotExist:
        return None
