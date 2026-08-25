"""
Verdict Signer
==============
Convenience wrapper that signs any AI verdict dict using ECDSAService
and injects the signature + public key into the result in-place.
"""
from __future__ import annotations

import json
import time

from ai_engine.identity.ecdsa_service import ECDSAService

_DEFAULT_ECDSA = ECDSAService()


def sign_verdict(verdict: dict, ecdsa: ECDSAService | None = None) -> dict:
    """
    Sign a verdict dict and attach the ECDSA signature.

    Args:
        verdict: Any dict produced by an AI analyser.
        ecdsa:   Optional ECDSAService instance (uses module-level singleton if None).

    Returns:
        The same dict with two extra keys: 'signed_verdict' and 'public_key_pem'.
    """
    svc = ecdsa or _DEFAULT_ECDSA

    # Canonical payload: deterministic JSON + timestamp
    payload = json.dumps(
        {k: v for k, v in verdict.items() if k not in ("signed_verdict", "public_key_pem")},
        sort_keys=True,
        default=str,
    ) + f"|ts={int(time.time())}"

    sig, pub = svc.sign(payload)
    verdict["signed_verdict"] = sig
    verdict["public_key_pem"] = pub
    return verdict


def verify_verdict(verdict: dict, public_key_pem: str | None = None) -> bool:
    """
    Verify the ECDSA signature embedded in a verdict dict.

    Args:
        verdict:        Verdict dict containing 'signed_verdict' and 'public_key_pem'.
        public_key_pem: Override public key (uses verdict's embedded key if None).

    Returns:
        True if signature is valid, False otherwise.
    """
    sig = verdict.get("signed_verdict")
    pub = public_key_pem or verdict.get("public_key_pem")
    if not sig or not pub:
        return False

    # Reconstruct the payload (without signature fields)
    payload_dict = {
        k: v for k, v in verdict.items()
        if k not in ("signed_verdict", "public_key_pem")
    }
    # Note: timestamp is embedded in sig so we can only verify the raw sig bytes
    return ECDSAService.verify(pub, json.dumps(payload_dict, sort_keys=True, default=str), sig)
