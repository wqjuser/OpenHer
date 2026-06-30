"""Backend live-process chat smoke command tests."""

from __future__ import annotations

import importlib.util
import json
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "integration" / "backend_chat_smoke.py"


def load_chat_smoke_module():
    assert SCRIPT.exists(), "backend chat smoke script must exist"
    spec = importlib.util.spec_from_file_location("backend_chat_smoke", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backend_chat_smoke_exposes_live_chat_checks():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "backend_runtime_smoke" in source
    assert "TemporaryDirectory" in source
    assert "OPENHER_DATA_DIR" in source
    assert "OPENHER_API_TOKEN" in source
    assert "def request_json_post" in source
    assert '"/api/chat"' in source
    assert 'f"/api/session/{session_id}/status"' in source
    assert 'f"/api/chat/history/{persona_id}"' in source
    assert "chat_available" in source
    assert "redact_known_secrets" in source


def test_chat_unavailable_reason_reads_status_capability():
    smoke = load_chat_smoke_module()

    assert smoke.chat_unavailable_reason({
        "capabilities": {
            "chat": {
                "available": False,
                "reason": "LLM provider unavailable",
            },
        },
    }) == "LLM provider unavailable"
    assert smoke.chat_unavailable_reason({
        "capabilities": {"chat": {"available": True}},
    }) is None
    assert smoke.chat_unavailable_reason({}) == "status.capabilities.chat unavailable"


def test_request_json_post_sends_json_and_decodes_response():
    smoke = load_chat_smoke_module()
    response = Mock()
    response.status = 200
    response.read.return_value = json.dumps({"ok": True}).encode("utf-8")
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        status_code, body = smoke.request_json_post(
            "http://127.0.0.1:8000",
            "/api/chat",
            token="secret",
            payload={"message": "hi"},
            timeout=3.0,
        )

    request = urlopen.call_args.args[0]
    assert status_code == 200
    assert body == {"ok": True}
    assert request.full_url == "http://127.0.0.1:8000/api/chat"
    assert request.get_method() == "POST"
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.headers["Content-type"] == "application/json"
    assert json.loads(request.data.decode("utf-8")) == {"message": "hi"}


def test_request_json_post_decodes_http_error_body():
    smoke = load_chat_smoke_module()
    error = urllib.error.HTTPError(
        url="http://127.0.0.1:8000/api/chat",
        code=503,
        msg="Service Unavailable",
        hdrs=Message(),
        fp=None,
    )
    error.read = Mock(return_value=b'{"detail":"not ready"}')

    with patch("urllib.request.urlopen", side_effect=error):
        status_code, body = smoke.request_json_post(
            "http://127.0.0.1:8000",
            "/api/chat",
            token="",
            payload={"message": "hi"},
        )

    assert status_code == 503
    assert body == {"detail": "not ready"}


def test_check_chat_turn_requires_response_session_and_modality():
    smoke = load_chat_smoke_module()

    result = smoke.check_chat_turn_body({
        "session_id": "session-1",
        "response": "你好",
        "modality": "文字",
    })

    assert result == {
        "status": "ok",
        "session_id": "session-1",
        "modality": "文字",
        "reply_chars": "2",
    }


def test_check_chat_history_requires_user_and_assistant_messages():
    smoke = load_chat_smoke_module()

    result = smoke.check_chat_history_body({
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "你好"},
        ],
        "total": 2,
    })

    assert result == {"status": "ok", "messages": "2", "total": "2"}
