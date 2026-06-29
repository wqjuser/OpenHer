"""Backend live WebSocket smoke command tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "integration" / "backend_websocket_smoke.py"


def load_websocket_smoke_module():
    assert SCRIPT.exists(), "backend websocket smoke script must exist"
    spec = importlib.util.spec_from_file_location("backend_websocket_smoke", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backend_websocket_smoke_exposes_live_ws_checks():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "websockets.connect" in source
    assert "backend_runtime_smoke" in source
    assert "async def check_websocket_errors" in source
    assert "def websocket_url" in source
    assert "Invalid JSON" in source
    assert "service_unavailable" in source
    assert "OPENHER_API_TOKEN" in source
    assert "redact_known_secrets" in source


def test_websocket_url_converts_http_base_and_encodes_token():
    smoke = load_websocket_smoke_module()

    assert smoke.websocket_url("http://127.0.0.1:8123", "") == "ws://127.0.0.1:8123/ws/chat"
    assert (
        smoke.websocket_url("https://openher.example.test/base/", "a b+c")
        == "wss://openher.example.test/base/ws/chat?token=a+b%2Bc"
    )
