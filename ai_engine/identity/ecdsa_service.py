"""
ECDSA Service
=============
Handles key generation, signing, and verification for tamper-proof
AI verdicts. Uses NIST P-256 (secp256r1) curve.

All AI verdicts (deepfake and phishing) are signed with the system's
private key. Clients can verify using the exported public key PEM.
"""
from __future__ import annotations

import logging
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)


class ECDSAService:
    """
    Manages ECDSA key lifecycle for signing AI verdicts.

    Usage:
        service = ECDSAService()
        signature_hex, public_key_pem = service.sign("verdict payload")
        is_valid = ECDSAService.verify(public_key_pem, "verdict payload", signature_hex)
    """

    CURVE = ec.SECP256R1()   # NIST P-256

    def __init__(self, private_key_pem: Optional[str] = None) -> None:
        if private_key_pem:
            self._private_key = serialization.load_pem_private_key(
                private_key_pem.encode(), password=None
            )
            logger.info("Loaded ECDSA private key from PEM")
        else:
            self._private_key = ec.generate_private_key(self.CURVE)
            logger.info("Generated new ECDSA P-256 key pair")

        self._public_key = self._private_key.public_key()

    def export_private_key_pem(self) -> str:
        """Export private key as PEM string (store securely!)."""
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

    def export_public_key_pem(self) -> str:
        """Export public key as PEM string (safe to share)."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def sign(self, payload: str) -> tuple[str, str]:
        """
        Sign a string payload.

        Returns:
            (signature_hex, public_key_pem)
        """
        signature_bytes = self._private_key.sign(
            payload.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )
        signature_hex = signature_bytes.hex()
        return signature_hex, self.export_public_key_pem()

    @staticmethod
    def verify(public_key_pem: str, payload: str, signature_hex: str) -> bool:
        """
        Verify a signed payload against a PEM public key.

        Returns:
            True if signature is valid, False otherwise.
        """
        try:
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode()
            )
            signature_bytes = bytes.fromhex(signature_hex)
            public_key.verify(
                signature_bytes,
                payload.encode("utf-8"),
                ec.ECDSA(hashes.SHA256()),
            )
            return True
        except InvalidSignature:
            logger.warning("ECDSA signature verification FAILED")
            return False
        except Exception as exc:
            logger.error(f"ECDSA verification error: {exc}")
            return False
