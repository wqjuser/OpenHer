"""Deterministic backend acceptance smoke for core OpenHer HTTP flows."""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path
from typing import Any

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SMOKE_CLIENT_ID = "__openher_acceptance_smoke__"


def build_client() -> TestClient:
    """Build an in-process app with persona services and no live chat session."""
    import main
    from persona.loader import PersonaLoader
    from server.context import AppContext
    from server.persona_api_service import PersonaApiService

    context = AppContext()
    personas_dir = ROOT / "persona" / "personas"
    context.persona_loader = PersonaLoader(str(personas_dir))
    context.persona_api_service = PersonaApiService(
        persona_loader=context.persona_loader,
        personas_dir=personas_dir,
    )
    return TestClient(main.create_app(context), raise_server_exceptions=False)


def check_status(client: TestClient) -> dict[str, str]:
    response = _request(client, "GET", "/api/status")
    _require_status(response, 200, "status")
    body = response.json()

    capabilities = _require_dict(body.get("capabilities"), "status.capabilities")
    providers = _require_dict(body.get("providers"), "status.providers")
    chat = _require_dict(capabilities.get("chat"), "status.capabilities.chat")

    if body.get("status") != "running":
        raise AssertionError(f"status: expected running, got {body.get('status')!r}")
    for key in ("llm", "tts", "image", "memory"):
        if key not in providers:
            raise AssertionError(f"status.providers: missing {key}")
    for key in ("chat", "voice", "image", "memory"):
        if key not in capabilities:
            raise AssertionError(f"status.capabilities: missing {key}")
    if not isinstance(chat.get("available"), bool):
        raise AssertionError("status.capabilities.chat.available must be a boolean")

    return {
        "status": "ok",
        "chat_available": str(chat["available"]).lower(),
        "personas": str(len(body.get("personas") or [])),
    }


def check_personas(client: TestClient) -> str:
    response = _request(client, "GET", "/api/personas")
    _require_status(response, 200, "personas")
    body = response.json()
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
    return persona_id


def check_chat_history_empty_state(client: TestClient, persona_id: str) -> dict[str, str]:
    response = _request(
        client,
        "GET",
        f"/api/chat/history/{persona_id}",
        params={"client_id": SMOKE_CLIENT_ID, "limit": 5},
    )
    _require_status(response, 200, "history")
    body = response.json()
    messages = body.get("messages")
    total = body.get("total")
    if messages != []:
        raise AssertionError(f"history: expected empty messages, got {_safe_value(messages)}")
    if total != 0:
        raise AssertionError(f"history: expected total 0, got {total!r}")
    return {"status": "ok", "messages": "0", "total": "0"}


def check_chat_unavailable(client: TestClient, persona_id: str) -> dict[str, str]:
    response = _request(
        client,
        "POST",
        "/api/chat",
        json={
            "message": "smoke",
            "persona_id": persona_id,
            "client_id": SMOKE_CLIENT_ID,
        },
    )
    _require_status(response, 503, "chat_unavailable")
    body = response.json()
    detail = str(body.get("detail") or "")
    if "Session manager is not initialized" not in detail:
        raise AssertionError(f"chat_unavailable: unexpected detail {_safe_value(detail)}")
    return {"status": "ok", "http_status": "503"}


def run_smoke() -> list[tuple[str, dict[str, str]]]:
    client = build_client()
    status = check_status(client)
    persona_id = check_personas(client)
    history = check_chat_history_empty_state(client, persona_id)
    chat_unavailable = check_chat_unavailable(client, persona_id)
    return [
        ("status", status),
        ("personas", {"status": "ok", "persona_id": persona_id}),
        ("history", history),
        ("chat_unavailable", chat_unavailable),
    ]


def main() -> int:
    try:
        results = run_smoke()
    except Exception as exc:
        from server.errors import redact_known_secrets

        message = redact_known_secrets(str(exc))
        print(f"backend acceptance smoke failed: {type(exc).__name__}: {message}", file=sys.stderr)
        return 1

    for name, result in results:
        print(_format_result(name, result))
    return 0


def _request(client: TestClient, method: str, path: str, **kwargs: Any):
    headers = dict(kwargs.pop("headers", {}) or {})
    token = os.getenv("OPENHER_API_TOKEN", "").strip()
    if token and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {token}"
    return client.request(method, path, headers=headers, **kwargs)


def _require_status(response: Any, expected: int, label: str) -> None:
    if response.status_code != expected:
        raise AssertionError(
            f"{label}: expected HTTP {expected}, got {response.status_code}: "
            f"{_safe_value(response.text)}"
        )


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError(f"{label}: expected object, got {_safe_value(value)}")
    return value


def _safe_value(value: Any) -> str:
    text = str(value).replace("\n", " ")
    return text[:500]


def _format_result(name: str, result: dict[str, str]) -> str:
    fields = " ".join(f"{key}={value}" for key, value in sorted(result.items()))
    return f"{name}: {fields}"


if __name__ == "__main__":
    raise SystemExit(main())
