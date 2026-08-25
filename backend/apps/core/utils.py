"""Core utility helpers shared across apps."""
from __future__ import annotations

import hashlib
import uuid


def generate_session_id() -> str:
    """Generate a URL-safe UUID4 session identifier."""
    return str(uuid.uuid4())


def sha256_hex(data: str) -> str:
    """Return the SHA-256 hex digest of a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
