"""Media filename/signature helpers used by HTTP routes."""

from __future__ import annotations

import mimetypes
import os
from typing import Optional


def audio_format_for_path(audio_path: Optional[str]) -> str:
    """Infer a client-facing audio format from a generated file path."""
    if not audio_path:
        return "mp3"
    return os.path.splitext(audio_path)[1].lstrip(".").lower() or "mp3"


def selfie_url_for_path(image_path: Optional[str]) -> Optional[str]:
    """Map a generated selfie file path to the served `/api/selfie/...` URL."""
    if not image_path:
        return None
    parts = image_path.replace("\\", "/").split("/")
    selfie_idx = parts.index("selfie") if "selfie" in parts else -1
    if selfie_idx >= 0:
        return "/api/selfie/" + "/".join(parts[selfie_idx + 1:])
    return f"/api/selfie/{os.path.basename(image_path)}"


def media_type_for_file(file_path) -> str:
    """Infer media type from file signature first, then filename."""
    path = os.fspath(file_path)
    try:
        with open(path, "rb") as f:
            header = f.read(16)
    except OSError:
        header = b""

    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "video/mp4"

    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"
