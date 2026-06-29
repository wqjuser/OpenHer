"""Live WebSocket smoke for OpenHer backend error-event contracts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import websockets


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.integration import backend_runtime_smoke


SMOKE_CLIENT_ID = "__openher_websocket_smoke__"


def websocket_url(base_url: str, token: str) -> str:
    parsed = urllib.parse.urlsplit(base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    path = f"{parsed.path.rstrip('/')}/ws/chat"
    query = urllib.parse.urlencode({"token": token}) if token else ""
    return urllib.parse.urlunsplit((scheme, parsed.netloc, path, query, ""))


async def check_websocket_errors(uri: str) -> list[tuple[str, dict[str, str]]]:
    async with websockets.connect(uri, open_timeout=8, ping_interval=None) as websocket:
        await websocket.send("{not-json")
        invalid = _decode_event(await asyncio.wait_for(websocket.recv(), timeout=5))
        if invalid.get("type") != "error" or invalid.get("content") != "Invalid JSON":
            raise AssertionError(f"invalid_json: unexpected event {_safe_value(invalid)}")

        await websocket.send(json.dumps({
            "type": "status",
            "client_id": SMOKE_CLIENT_ID,
        }))
        unavailable = _decode_event(await asyncio.wait_for(websocket.recv(), timeout=5))
        if unavailable.get("type") != "error":
            raise AssertionError(f"service_unavailable: expected error event, got {_safe_value(unavailable)}")
        if unavailable.get("code") != "service_unavailable":
            raise AssertionError(
                "service_unavailable: expected code=service_unavailable, "
                f"got {_safe_value(unavailable)}"
            )

    return [
        ("websocket_invalid_json", {"status": "ok", "type": "error"}),
        ("websocket_service_unavailable", {"status": "ok", "code": "service_unavailable"}),
    ]


async def run_smoke(timeout: float) -> list[tuple[str, dict[str, str]]]:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("OPENHER_API_TOKEN", "").strip()
    port = backend_runtime_smoke.find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    process, log_file = backend_runtime_smoke.start_server(port)
    try:
        status_body = backend_runtime_smoke.wait_for_status(
            base_url=base_url,
            process=process,
            log_file=log_file,
            token=token,
            timeout=timeout,
        )
        status = backend_runtime_smoke.check_live_status(status_body)
        events = await check_websocket_errors(websocket_url(base_url, token))
        return [
            ("websocket_runtime", {"status": "ok", "port": str(port), **status}),
            *events,
        ]
    finally:
        backend_runtime_smoke.stop_server(process)
        log_file.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live OpenHer backend WebSocket smoke.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Startup timeout in seconds.")
    args = parser.parse_args()

    try:
        results = asyncio.run(run_smoke(timeout=args.timeout))
    except Exception as exc:
        from server.errors import redact_known_secrets

        message = redact_known_secrets(str(exc))
        print(f"backend websocket smoke failed: {type(exc).__name__}: {message}", file=sys.stderr)
        return 1

    for name, result in results:
        print(_format_result(name, result))
    return 0


def _decode_event(raw: str | bytes) -> dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise AssertionError(f"expected WebSocket JSON object, got {_safe_value(value)}")
    return value


def _format_result(name: str, result: dict[str, str]) -> str:
    fields = " ".join(f"{key}={value}" for key, value in sorted(result.items()))
    return f"{name}: {fields}"


def _safe_value(value: Any) -> str:
    return str(value).replace("\n", " ")[:500]


if __name__ == "__main__":
    raise SystemExit(main())
