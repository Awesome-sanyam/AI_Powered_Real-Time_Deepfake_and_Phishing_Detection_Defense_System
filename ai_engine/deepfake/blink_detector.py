"""
Blink Rate Detector (standalone wrapper)
=========================================
Thin wrapper so other modules can import BlinkRateDetector without
pulling the full CrossModalVerificationEngine.
"""
from __future__ import annotations

from ai_engine.deepfake.cross_modal_engine import BlinkRateDetector

__all__ = ["BlinkRateDetector"]
