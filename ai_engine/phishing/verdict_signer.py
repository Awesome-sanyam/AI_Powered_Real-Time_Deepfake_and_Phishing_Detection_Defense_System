"""
Verdict Signer
==============
Convenience wrapper that signs any AI verdict dict using ECDSAService
and injects the signature + public key into the result in-place.

Design: The timestamp is stored as a separate key ('verdict_ts') so that
verify_verdict can reconstruct the exact signed payload for verification.
"""
from __future__ import annotations

import json
import time

from ai_engine.identity.ecdsa_service import ECDSAService

_DEFAULT_ECDSA = ECDSAService()


def sign_verdict(verdict: dict, ecdsa: ECDSAService | None = None) -> dict:
    """
    Sign a verdict dict and attach the ECDSA signature.

    The canonical signed payload is:
        json.dumps(<verdict_fields>, sort_keys=True) + "|ts=<unix_ts>"

    The timestamp is stored in 'verdict_ts' so that verify_verdict can
    reconstruct the exact payload string without timestamp drift.

    Args:
        verdict: Any dict produced by an AI analyser.
        ecdsa:   Optional ECDSAService instance (uses module-level singleton if None).

    Returns:
        The same dict with three extra keys:
          'verdict_ts'    — unix timestamp (int) used in payload
          'signed_verdict' — hex-encoded DER ECDSA signature
          'public_key_pem' — PEM public key for verification
    """
    svc = ecdsa or _DEFAULT_ECDSA
    ts  = int(time.time())

    # Canonical payload: deterministic JSON of verdict fields + timestamp suffix
    core_fields = {
        k: v for k, v in verdict.items()
        if k not in ("signed_verdict", "public_key_pem", "verdict_ts")
    }
    payload = json.dumps(core_fields, sort_keys=True, default=str) + f"|ts={ts}"

    sig, pub = svc.sign(payload)

    verdict["verdict_ts"]     = ts
    verdict["signed_verdict"] = sig
    verdict["public_key_pem"] = pub
    return verdict


def verify_verdict(verdict: dict, public_key_pem: str | None = None) -> bool:
    """
    Verify the ECDSA signature embedded in a verdict dict.

    Reconstructs the exact canonical payload that was signed:
        json.dumps(<core_fields>, sort_keys=True) + "|ts=<verdict_ts>"

    Args:
        verdict:        Verdict dict containing 'signed_verdict', 'public_key_pem',
                        and 'verdict_ts' (as set by sign_verdict).
        public_key_pem: Override public key (uses verdict's embedded key if None).

    Returns:
        True if signature is valid, False otherwise.
    """
    sig = verdict.get("signed_verdict")
    pub = public_key_pem or verdict.get("public_key_pem")
    ts  = verdict.get("verdict_ts")

    if not sig or not pub or ts is None:
        return False

    # Reconstruct exact signed payload (mirror of sign_verdict)
    core_fields = {
        k: v for k, v in verdict.items()
        if k not in ("signed_verdict", "public_key_pem", "verdict_ts")
    }
    payload = json.dumps(core_fields, sort_keys=True, default=str) + f"|ts={ts}"

    return ECDSAService.verify(pub, payload, sig)
