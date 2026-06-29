"""Live-process backend smoke for OpenHer startup and core HTTP routes."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, TextIO

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SMOKE_CLIENT_ID = "__openher_runtime_smoke__"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_server(port: int) -> tuple[subprocess.Popen[str], TextIO]:
    log_file = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return process, log_file


def stop_server(process: subprocess.Popen[str], timeout: float = 8.0) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def wait_for_status(
    *,
    base_url: str,
    process: subprocess.Popen[str],
    log_file: TextIO,
    token: str,
    timeout: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error = "server did not respond yet"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "backend exited before /api/status became ready\n"
                f"{_log_tail(log_file)}"
            )
        try:
            status_code, body = request_json(base_url, "/api/status", token=token, timeout=2.0)
            if status_code == 200 and body.get("status") == "running":
                return body
            last_error = f"HTTP {status_code}: {_safe_value(body)}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.25)

    raise TimeoutError(
        f"backend did not become ready within {timeout:.1f}s; last_error={last_error}\n"
        f"{_log_tail(log_file)}"
    )


def request_json(
    base_url: str,
    path: str,
    *,
    token: str,
    timeout: float = 5.0,
    params: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    request = urllib.request.Request(
        f"{base_url}{path}{query}",
        headers=_auth_headers(token),
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return int(response.status), _decode_json(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return int(exc.code), _decode_json(raw)


def check_live_status(body: dict[str, Any]) -> dict[str, str]:
    providers = _require_dict(body.get("providers"), "status.providers")
    capabilities = _require_dict(body.get("capabilities"), "status.capabilities")
    chat = _require_dict(capabilities.get("chat"), "status.capabilities.chat")
    memory = _require_dict(capabilities.get("memory"), "status.capabilities.memory")

    for key in ("llm", "tts", "image", "memory"):
        if key not in providers:
            raise AssertionError(f"status.providers: missing {key}")
    for key in ("chat", "voice", "image", "memory"):
        if key not in capabilities:
            raise AssertionError(f"status.capabilities: missing {key}")
    if not isinstance(chat.get("available"), bool):
        raise AssertionError("status.capabilities.chat.available must be a boolean")
    if not isinstance(memory.get("available"), bool):
        raise AssertionError("status.capabilities.memory.available must be a boolean")

    return {
        "status": "ok",
        "chat_available": str(chat["available"]).lower(),
        "memory_available": str(memory["available"]).lower(),
    }


def check_live_personas(base_url: str, token: str) -> tuple[str, dict[str, str]]:
    status_code, body = request_json(base_url, "/api/personas", token=token)
    _require_status(status_code, 200, "personas")
    personas = body.get("personas")
    if not isinstance(personas, list) or not personas:
        raise AssertionError("personas: expected a non-empty personas list")

    first = _require_dict(personas[0], "personas[0]")
    persona_id = first.get("persona_id")
    if not isinstance(persona_id, str) or not persona_id:
        raise AssertionError("personas[0].persona_id must be a non-empty string")
    if not isinstance(first.get("name"), str) or not first.get("name"):
        raise AssertionError("personas[0].name must be a non-empty string")

    return persona_id, {
        "status": "ok",
        "count": str(len(personas)),
        "first": persona_id,
    }


def check_live_history(base_url: str, token: str, persona_id: str) -> dict[str, str]:
    status_code, body = request_json(
        base_url,
        f"/api/chat/history/{persona_id}",
        token=token,
        params={"client_id": f"{SMOKE_CLIENT_ID}_{os.getpid()}", "limit": "5"},
    )
    _require_status(status_code, 200, "history")
    if body.get("messages") != []:
        raise AssertionError(f"history: expected empty messages, got {_safe_value(body.get('messages'))}")
    if body.get("total") != 0:
        raise AssertionError(f"history: expected total 0, got {body.get('total')!r}")
    return {"status": "ok", "messages": "0", "total": "0"}


def run_smoke(timeout: float) -> list[tuple[str, dict[str, str]]]:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("OPENHER_API_TOKEN", "").strip()
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    process, log_file = start_server(port)
    try:
        status_body = wait_for_status(
            base_url=base_url,
            process=process,
            log_file=log_file,
            token=token,
            timeout=timeout,
        )
        status = check_live_status(status_body)
        persona_id, personas = check_live_personas(base_url, token)
        history = check_live_history(base_url, token, persona_id)
        return [
            ("runtime_status", {"port": str(port), **status}),
            ("runtime_personas", personas),
            ("runtime_history", history),
        ]
    finally:
        stop_server(process)
        log_file.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live OpenHer backend runtime smoke.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Startup timeout in seconds.")
    args = parser.parse_args()

    try:
        results = run_smoke(timeout=args.timeout)
    except Exception as exc:
        from server.errors import redact_known_secrets

        message = redact_known_secrets(str(exc))
        print(f"backend runtime smoke failed: {type(exc).__name__}: {message}", file=sys.stderr)
        return 1

    for name, result in results:
        print(_format_result(name, result))
    return 0


def _auth_headers(token: str) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _decode_json(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object, got {_safe_value(value)}")
    return value


def _require_status(status_code: int, expected: int, label: str) -> None:
    if status_code != expected:
        raise AssertionError(f"{label}: expected HTTP {expected}, got {status_code}")


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError(f"{label}: expected object, got {_safe_value(value)}")
    return value


def _format_result(name: str, result: dict[str, str]) -> str:
    fields = " ".join(f"{key}={value}" for key, value in sorted(result.items()))
    return f"{name}: {fields}"


def _safe_value(value: Any) -> str:
    return str(value).replace("\n", " ")[:500]


def _log_tail(log_file: TextIO, limit: int = 4000) -> str:
    log_file.flush()
    log_file.seek(0)
    text = log_file.read()
    if not text:
        return "<no backend output>"
    return text[-limit:]


if __name__ == "__main__":
    raise SystemExit(main())
