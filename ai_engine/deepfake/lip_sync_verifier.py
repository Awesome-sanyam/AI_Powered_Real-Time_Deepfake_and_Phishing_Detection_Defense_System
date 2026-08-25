"""
Lip Sync Verifier (standalone wrapper)
=======================================
Thin wrapper so other modules can import LipSyncVerifier without
pulling the full CrossModalVerificationEngine.
"""
from __future__ import annotations

from ai_engine.deepfake.cross_modal_engine import LipSyncVerifier

__all__ = ["LipSyncVerifier"]
