"""Path helpers for serving files from bounded directories."""

from __future__ import annotations

from pathlib import Path


def safe_child_path(base_dir: str | Path, child_path: str) -> Path:
    """Resolve a child path and reject attempts to escape ``base_dir``."""
    base = Path(base_dir).resolve()
    candidate = (base / child_path).resolve()
    if candidate == base or base not in candidate.parents:
        raise ValueError("path escapes base directory")
    return candidate
