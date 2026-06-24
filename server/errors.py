"""Client-facing error helpers for external provider failures."""

from __future__ import annotations

import os


def redact_known_secrets(text: str) -> str:
    """Redact configured secrets before returning provider errors to clients."""
    redacted = text
    for key, value in os.environ.items():
        if not value or len(value) < 8:
            continue
        if any(marker in key.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            redacted = redacted.replace(value, "[redacted]")
    return redacted


def external_error_detail(action: str, exc: Exception) -> str:
    """Build a bounded client-facing error for external provider failures."""
    raw = redact_known_secrets(str(exc))
    return f"{action}: {type(exc).__name__}: {raw[:240]}"

