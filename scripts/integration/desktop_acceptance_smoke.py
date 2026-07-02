"""Live desktop acceptance smoke for the OpenHer backend contract.

This script emulates the macOS client's startup sequence without launching the
GUI: status diagnostics, persona discovery, history load, WebSocket handshake,
typing events, and one chat attempt.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import websockets


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.integration import backend_runtime_smoke


SMOKE_CLIENT_ID = "__openher_desktop_acceptance_smoke__"
SMOKE_USER_NAME = "OpenHerDesktopSmoke"
SMOKE_MESSAGE = "用一句中文回复：桌面端验收通过。"


def websocket_url(base_url: str, token: str) -> str:
    """Map the REST base URL to the same /ws/chat URL used by Swift."""
    parsed = urllib.parse.urlsplit(base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    path = f"{parsed.path.rstrip('/')}/ws/chat"
    query = urllib.parse.urlencode({"token": token}) if token else ""
    return urllib.parse.urlunsplit((scheme, parsed.netloc, path, query, ""))


def check_desktop_status_body(body: dict[str, Any]) -> dict[str, str]:
    """Validate the status payload consumed by AppState and SettingsView."""
    if body.get("status") != "running":
        raise AssertionError(f"status: expected running, got {body.get('status')!r}")

    providers = _require_dict(body.get("providers"), "status.providers")
    capabilities = _require_dict(body.get("capabilities"), "status.capabilities")

    for key in ("llm", "tts", "image", "memory"):
        if key not in providers:
            raise AssertionError(f"status.providers: missing {key}")
        provider = _require_dict(providers.get(key), f"status.providers.{key}")
        if not isinstance(provider.get("setup_hint"), str):
            raise AssertionError(f"status.providers.{key}.setup_hint must be a string")
    for key in ("chat", "voice", "image", "memory"):
        if key not in capabilities:
            raise AssertionError(f"status.capabilities: missing {key}")
        capability = _require_dict(capabilities.get(key), f"status.capabilities.{key}")
        if not isinstance(capability.get("setup_hint"), str):
            raise AssertionError(f"status.capabilities.{key}.setup_hint must be a string")

    for key in ("chat", "voice", "image", "memory"):
        capability = _require_dict(capabilities.get(key), f"status.capabilities.{key}")
        if not isinstance(capability.get("available"), bool):
            raise AssertionError(f"status.capabilities.{key}.available must be a boolean")
        if "reason" not in capability:
            raise AssertionError(f"status.capabilities.{key}.reason is required")

    memory_provider = _require_dict(providers.get("memory"), "status.providers.memory")
    for key in ("enabled", "configured", "available"):
        if not isinstance(memory_provider.get(key), bool):
            raise AssertionError(f"status.providers.memory.{key} must be a boolean")

    return {
        "status": "ok",
        "chat_available": _bool_text(capabilities["chat"]["available"]),
        "voice_available": _bool_text(capabilities["voice"]["available"]),
        "image_available": _bool_text(capabilities["image"]["available"]),
        "memory_available": _bool_text(capabilities["memory"]["available"]),
    }


def check_desktop_personas_body(body: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Validate the persona list consumed by DiscoveryView."""
    personas = body.get("personas")
    if not isinstance(personas, list) or not personas:
        raise AssertionError("personas: expected a non-empty personas list")

    first = _require_dict(personas[0], "personas[0]")
    persona_id = first.get("persona_id")
    name = first.get("name")
    if not isinstance(persona_id, str) or not persona_id:
        raise AssertionError("personas[0].persona_id must be a non-empty string")
    if not isinstance(name, str) or not name:
        raise AssertionError("personas[0].name must be a non-empty string")

    return persona_id, {
        "status": "ok",
        "count": str(len(personas)),
        "first": persona_id,
    }


def check_desktop_history_body(body: dict[str, Any]) -> dict[str, str]:
    """Validate the chat history shape loaded before a restored conversation."""
    messages = body.get("messages")
    total = body.get("total")
    if not isinstance(messages, list):
        raise AssertionError(f"history: expected messages list, got {_safe_value(messages)}")
    if not isinstance(total, int):
        raise AssertionError(f"history: expected integer total, got {_safe_value(total)}")
    return {
        "status": "ok",
        "messages": str(len(messages)),
        "total": str(total),
    }


async def check_desktop_websocket_chat(
    *,
    uri: str,
    persona_id: str,
    chat_available: bool,
    timeout: float,
) -> tuple[str, dict[str, str]]:
    """Exercise the WebSocket events the macOS client sends and receives."""
    async with websockets.connect(uri, open_timeout=8, ping_interval=None) as websocket:
        await websocket.send(json.dumps({
            "type": "handshake",
            "client_id": SMOKE_CLIENT_ID,
        }))
        await websocket.send(json.dumps({
            "type": "typing",
            "active": True,
        }))
        await websocket.send(json.dumps({
            "type": "chat",
            "content": SMOKE_MESSAGE,
            "persona_id": persona_id,
            "client_id": SMOKE_CLIENT_ID,
            "user_name": SMOKE_USER_NAME,
            "session_id": None,
        }))
        await websocket.send(json.dumps({
            "type": "typing",
            "active": False,
        }))

        if not chat_available:
            event = await _recv_event(websocket, timeout=min(timeout, 10.0))
            if event.get("type") != "error" or event.get("code") != "service_unavailable":
                raise AssertionError(f"desktop_ws_unavailable: unexpected event {_safe_value(event)}")
            return "desktop_ws_chat", {
                "status": "ok",
                "chat_available": "false",
                "event": "service_unavailable",
            }

        saw_start = False
        saw_end = False
        session_id = ""
        reply_chars = 0
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            event = await _recv_event(
                websocket,
                timeout=max(0.5, deadline - asyncio.get_running_loop().time()),
            )
            event_type = event.get("type")
            if event_type == "error":
                raise AssertionError(f"desktop_ws_chat: unexpected error {_safe_value(event)}")
            if event_type == "chat_start":
                saw_start = True
                raw_session_id = event.get("session_id")
                if isinstance(raw_session_id, str):
                    session_id = raw_session_id
            elif event_type == "chat_end":
                saw_end = True
                reply = event.get("reply")
                if isinstance(reply, str):
                    reply_chars = len(reply.strip())
                break

        if not saw_start:
            raise AssertionError("desktop_ws_chat: did not receive chat_start")
        if not saw_end:
            raise AssertionError("desktop_ws_chat: did not receive chat_end")
        if not session_id:
            raise AssertionError("desktop_ws_chat: chat_start missing session_id")
        if reply_chars <= 0:
            raise AssertionError("desktop_ws_chat: chat_end missing non-empty reply")

        return "desktop_ws_chat", {
            "status": "ok",
            "chat_available": "true",
            "session_id": session_id,
            "reply_chars": str(reply_chars),
        }


def run_smoke(timeout: float, chat_timeout: float) -> list[tuple[str, dict[str, str]]]:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("OPENHER_API_TOKEN", "").strip()
    port = backend_runtime_smoke.find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="openher-desktop-acceptance-") as data_dir:
        process, log_file = backend_runtime_smoke.start_server(
            port,
            env_overrides={"OPENHER_DATA_DIR": data_dir},
        )
        try:
            status_body = backend_runtime_smoke.wait_for_status(
                base_url=base_url,
                process=process,
                log_file=log_file,
                token=token,
                timeout=timeout,
            )
            status = check_desktop_status_body(status_body)
            status_code, personas_body = backend_runtime_smoke.request_json(
                base_url,
                "/api/personas",
                token=token,
            )
            backend_runtime_smoke._require_status(status_code, 200, "personas")
            persona_id, personas = check_desktop_personas_body(personas_body)

            status_code, history_body = backend_runtime_smoke.request_json(
                base_url,
                f"/api/chat/history/{persona_id}",
                token=token,
                params={"client_id": SMOKE_CLIENT_ID, "limit": "10"},
            )
            backend_runtime_smoke._require_status(status_code, 200, "history")
            history = check_desktop_history_body(history_body)

            ws_name, ws_result = asyncio.run(check_desktop_websocket_chat(
                uri=websocket_url(base_url, token),
                persona_id=persona_id,
                chat_available=status["chat_available"] == "true",
                timeout=chat_timeout,
            ))
            return [
                ("desktop_status", {"port": str(port), **status}),
                ("desktop_personas", personas),
                ("desktop_history", history),
                (ws_name, ws_result),
            ]
        finally:
            backend_runtime_smoke.stop_server(process)
            log_file.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live OpenHer desktop acceptance smoke.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Startup timeout in seconds.")
    parser.add_argument("--chat-timeout", type=float, default=90.0, help="WebSocket chat timeout in seconds.")
    args = parser.parse_args()

    try:
        results = run_smoke(timeout=args.timeout, chat_timeout=args.chat_timeout)
    except Exception as exc:
        from server.errors import redact_known_secrets

        message = redact_known_secrets(str(exc))
        print(f"desktop acceptance smoke failed: {type(exc).__name__}: {message}", file=sys.stderr)
        return 1

    for name, result in results:
        print(_format_result(name, result))
    return 0


async def _recv_event(websocket: Any, *, timeout: float) -> dict[str, Any]:
    raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise AssertionError(f"expected WebSocket JSON object, got {_safe_value(value)}")
    return value


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError(f"{label}: expected object, got {_safe_value(value)}")
    return value


def _bool_text(value: Any) -> str:
    if not isinstance(value, bool):
        raise AssertionError(f"expected boolean, got {_safe_value(value)}")
    return str(value).lower()


def _format_result(name: str, result: dict[str, str]) -> str:
    fields = " ".join(f"{key}={value}" for key, value in sorted(result.items()))
    return f"{name}: {fields}"


def _safe_value(value: Any) -> str:
    return str(value).replace("\n", " ")[:500]


if __name__ == "__main__":
    raise SystemExit(main())
