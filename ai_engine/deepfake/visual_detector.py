"""
Visual Artifact Detector (standalone wrapper)
=============================================
Thin wrapper around the MobileNetV2 classifier defined in cross_modal_engine.
Exposed here so other modules can import it without pulling the full engine.
"""
from __future__ import annotations

from ai_engine.deepfake.cross_modal_engine import VisualArtifactDetector

__all__ = ["VisualArtifactDetector"]
