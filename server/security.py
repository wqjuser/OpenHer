"""HTTP/WebSocket security and CORS configuration helpers."""

from __future__ import annotations

import os
import secrets
from typing import Optional


DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,"
    "http://127.0.0.1:3000,"
    "http://localhost:8000,"
    "http://127.0.0.1:8000,"
    "http://localhost:8800,"
    "http://127.0.0.1:8800"
)


def cors_origins_from_env() -> list[str]:
    """Load explicit CORS origins; wildcard is ignored with credentials."""
    raw = os.getenv("OPENHER_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip() and origin.strip() != "*"]


def api_token_from_env() -> str:
    """Return optional API token used to protect HTTP and WebSocket entrypoints."""
    return os.getenv("OPENHER_API_TOKEN", "").strip()


def request_has_api_token(authorization: Optional[str], token_param: Optional[str] = None) -> bool:
    """Validate a bearer token or query token when OPENHER_API_TOKEN is configured."""
    required_token = api_token_from_env()
    if not required_token:
        return True

    candidates: list[str] = []
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            candidates.append(value.strip())
    if token_param:
        candidates.append(token_param.strip())

    return any(secrets.compare_digest(candidate, required_token) for candidate in candidates)

