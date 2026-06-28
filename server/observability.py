"""HTTP observability helpers for the FastAPI server."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
import re
import time
import uuid

from fastapi import Request
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-ID"
PROCESS_TIME_HEADER = "X-Process-Time-ms"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_LOGGER = logging.getLogger("openher.http")


def sanitize_request_id(value: str | None) -> str:
    """Return a safe request id, preserving valid caller-supplied ids."""
    candidate = (value or "").strip()
    if candidate and _SAFE_REQUEST_ID.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


async def add_request_observability(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach request correlation and latency metadata to HTTP responses."""
    start = time.perf_counter()
    request_id = sanitize_request_id(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = request_id

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _LOGGER.exception(
            "http_request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "elapsed_ms": round(elapsed_ms, 3),
            },
        )
        raise

    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers[REQUEST_ID_HEADER] = request_id
    response.headers[PROCESS_TIME_HEADER] = f"{elapsed_ms:.3f}"
    _LOGGER.info(
        "http_request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "elapsed_ms": round(elapsed_ms, 3),
        },
    )
    return response
