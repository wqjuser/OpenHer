"""Live-process backend smoke for one real REST chat turn."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.integration import backend_runtime_smoke


SMOKE_CLIENT_ID = "__openher_chat_smoke__"
SMOKE_USER_NAME = "OpenHerSmoke"
SMOKE_MESSAGE = "用一句中文回复：测试通过。"


def request_json_post(
    base_url: str,
    path: str,
    *,
    token: str,
    payload: dict[str, Any],
    timeout: float = 60.0,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    headers = backend_runtime_smoke._auth_headers(token)
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return int(response.status), backend_runtime_smoke._decode_json(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return int(exc.code), backend_runtime_smoke._decode_json(raw)


def chat_unavailable_reason(status_body: dict[str, Any]) -> str | None:
    capabilities = status_body.get("capabilities")
    if not isinstance(capabilities, dict):
        return "status.capabilities.chat unavailable"
    chat = capabilities.get("chat")
    if not isinstance(chat, dict):
        return "status.capabilities.chat unavailable"
    if bool(chat.get("available", False)):
        return None
    reason = chat.get("reason")
    if isinstance(reason, str) and reason:
        return reason
    return "chat capability unavailable"


def check_chat_turn_body(body: dict[str, Any]) -> dict[str, str]:
    session_id = body.get("session_id")
    response = body.get("response")
    modality = body.get("modality")
    if not isinstance(session_id, str) or not session_id:
        raise AssertionError(f"chat_turn: missing session_id in {_safe_value(body)}")
    if not isinstance(response, str) or not response.strip():
        raise AssertionError(f"chat_turn: missing response in {_safe_value(body)}")
    if not isinstance(modality, str) or not modality:
        raise AssertionError(f"chat_turn: missing modality in {_safe_value(body)}")
    return {
        "status": "ok",
        "session_id": session_id,
        "modality": modality,
        "reply_chars": str(len(response.strip())),
    }


def check_session_status_body(body: dict[str, Any]) -> dict[str, str]:
    if not body:
        raise AssertionError("session_status: expected non-empty status object")
    return {"status": "ok", "keys": str(len(body))}


def check_chat_history_body(body: dict[str, Any]) -> dict[str, str]:
    messages = body.get("messages")
    total = body.get("total")
    if not isinstance(messages, list):
        raise AssertionError(f"history: expected messages list, got {_safe_value(messages)}")
    if not isinstance(total, int):
        raise AssertionError(f"history: expected integer total, got {_safe_value(total)}")
    roles = [message.get("role") for message in messages if isinstance(message, dict)]
    if "user" not in roles or "assistant" not in roles:
        raise AssertionError(f"history: expected user and assistant messages, got {_safe_value(messages)}")
    if total < 2:
        raise AssertionError(f"history: expected total >= 2, got {total}")
    return {"status": "ok", "messages": str(len(messages)), "total": str(total)}


def check_live_chat_turn(
    *,
    base_url: str,
    token: str,
    persona_id: str,
    chat_timeout: float,
) -> tuple[str, dict[str, str]]:
    status_code, body = request_json_post(
        base_url,
        "/api/chat",
        token=token,
        payload={
            "message": SMOKE_MESSAGE,
            "persona_id": persona_id,
            "user_name": SMOKE_USER_NAME,
            "client_id": SMOKE_CLIENT_ID,
        },
        timeout=chat_timeout,
    )
    backend_runtime_smoke._require_status(status_code, 200, "chat_turn")
    return "chat_turn", check_chat_turn_body(body)


def check_live_session_status(base_url: str, token: str, session_id: str) -> tuple[str, dict[str, str]]:
    status_code, body = backend_runtime_smoke.request_json(
        base_url,
        f"/api/session/{session_id}/status",
        token=token,
    )
    backend_runtime_smoke._require_status(status_code, 200, "session_status")
    return "session_status", check_session_status_body(body)


def check_live_chat_history(base_url: str, token: str, persona_id: str) -> tuple[str, dict[str, str]]:
    status_code, body = backend_runtime_smoke.request_json(
        base_url,
        f"/api/chat/history/{persona_id}",
        token=token,
        params={"client_id": SMOKE_CLIENT_ID, "limit": "10"},
    )
    backend_runtime_smoke._require_status(status_code, 200, "history")
    return "chat_history", check_chat_history_body(body)


def run_smoke(timeout: float, chat_timeout: float) -> list[tuple[str, dict[str, str]]]:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("OPENHER_API_TOKEN", "").strip()
    port = backend_runtime_smoke.find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="openher-chat-smoke-") as data_dir:
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
            status = backend_runtime_smoke.check_live_status(status_body)
            persona_id, personas = backend_runtime_smoke.check_live_personas(base_url, token)
            unavailable_reason = chat_unavailable_reason(status_body)
            runtime_result = ("chat_runtime", {"port": str(port), **status})
            if unavailable_reason:
                return [
                    runtime_result,
                    ("chat_personas", personas),
                    ("chat_turn", {
                        "status": "skipped",
                        "chat_available": "false",
                        "reason": unavailable_reason,
                    }),
                ]

            chat_name, chat_result = check_live_chat_turn(
                base_url=base_url,
                token=token,
                persona_id=persona_id,
                chat_timeout=chat_timeout,
            )
            session_name, session_result = check_live_session_status(
                base_url,
                token,
                chat_result["session_id"],
            )
            history_name, history_result = check_live_chat_history(base_url, token, persona_id)
            return [
                runtime_result,
                ("chat_personas", personas),
                (chat_name, chat_result),
                (session_name, session_result),
                (history_name, history_result),
            ]
        finally:
            backend_runtime_smoke.stop_server(process)
            log_file.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live OpenHer backend REST chat smoke.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Startup timeout in seconds.")
    parser.add_argument("--chat-timeout", type=float, default=90.0, help="Chat request timeout in seconds.")
    args = parser.parse_args()

    try:
        results = run_smoke(timeout=args.timeout, chat_timeout=args.chat_timeout)
    except Exception as exc:
        from server.errors import redact_known_secrets

        message = redact_known_secrets(str(exc))
        print(f"backend chat smoke failed: {type(exc).__name__}: {message}", file=sys.stderr)
        return 1

    for name, result in results:
        print(_format_result(name, result))
    return 0


def _format_result(name: str, result: dict[str, str]) -> str:
    fields = " ".join(f"{key}={value}" for key, value in sorted(result.items()))
    return f"{name}: {fields}"


def _safe_value(value: Any) -> str:
    return str(value).replace("\n", " ")[:500]


if __name__ == "__main__":
    raise SystemExit(main())
