"""Desktop acceptance smoke command tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "integration" / "desktop_acceptance_smoke.py"


def load_desktop_smoke_module():
    assert SCRIPT.exists(), "desktop acceptance smoke script must exist"
    spec = importlib.util.spec_from_file_location("desktop_acceptance_smoke", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_desktop_acceptance_smoke_exposes_startup_and_chat_flow_checks():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "backend_runtime_smoke" in source
    assert "websockets.connect" in source
    assert "TemporaryDirectory" in source
    assert "OPENHER_DATA_DIR" in source
    assert "OPENHER_API_TOKEN" in source
    assert "smoke_contracts" in source
    assert "validate_status_diagnostics" in source
    assert "def check_desktop_status_body" in source
    assert "require_setup_hints=True" in source
    assert "def check_desktop_personas_body" in source
    assert "def check_desktop_history_body" in source
    assert "async def check_desktop_websocket_chat" in source
    assert '"type": "handshake"' in source
    assert '"type": "typing"' in source
    assert '"type": "chat"' in source
    assert '"chat_start"' in source
    assert '"chat_end"' in source
    assert "chat_available" in source
    assert "redact_known_secrets" in source
    assert "def _require_dict" not in source
    assert "def _format_result" not in source
    assert "def _safe_value" not in source
    assert "def _bool_text" not in source


def test_desktop_websocket_url_matches_swift_connection_mapping():
    smoke = load_desktop_smoke_module()

    assert smoke.websocket_url("http://127.0.0.1:8123", "") == "ws://127.0.0.1:8123/ws/chat"
    assert (
        smoke.websocket_url("https://openher.example.test/base/", "a b+c")
        == "wss://openher.example.test/base/ws/chat?token=a+b%2Bc"
    )


def test_desktop_status_body_requires_settings_diagnostic_contract():
    smoke = load_desktop_smoke_module()

    result = smoke.check_desktop_status_body({
        "status": "running",
        "providers": {
            "llm": {"provider": "deepseek", "available": True, "missing_key_env": "", "setup_hint": ""},
            "tts": {
                "provider": "dashscope",
                "available": False,
                "missing_key_env": "DASHSCOPE_API_KEY",
                "setup_hint": "Set DASHSCOPE_API_KEY in .env, then restart the backend.",
            },
            "image": {"provider": "gemini", "available": True, "missing_key_env": "", "setup_hint": ""},
            "memory": {
                "provider": "evermemos",
                "enabled": True,
                "configured": True,
                "available": False,
                "setup_hint": "Check EverMemOS credentials or network connectivity, then restart the backend.",
            },
        },
        "capabilities": {
            "chat": {"available": True, "reason": "", "requires": ["llm"], "setup_hint": ""},
            "voice": {
                "available": False,
                "reason": "TTS missing",
                "requires": ["tts"],
                "setup_hint": "Set DASHSCOPE_API_KEY in .env, then restart the backend.",
            },
            "image": {"available": True, "reason": "", "requires": ["image"], "setup_hint": ""},
            "memory": {
                "available": False,
                "reason": "EverMemOS unavailable",
                "requires": ["memory"],
                "setup_hint": "Check EverMemOS credentials or network connectivity, then restart the backend.",
            },
        },
    })

    assert result == {
        "status": "ok",
        "chat_available": "true",
        "voice_available": "false",
        "image_available": "true",
        "memory_available": "false",
    }


def test_desktop_status_body_rejects_missing_capability():
    smoke = load_desktop_smoke_module()

    try:
        smoke.check_desktop_status_body({
            "status": "running",
            "providers": {
                "llm": {"provider": "deepseek", "available": True, "missing_key_env": "", "setup_hint": ""},
                "tts": {"provider": "dashscope", "available": True, "missing_key_env": "", "setup_hint": ""},
                "image": {"provider": "gemini", "available": True, "missing_key_env": "", "setup_hint": ""},
                "memory": {
                    "provider": "evermemos",
                    "enabled": True,
                    "configured": True,
                    "available": True,
                    "setup_hint": "",
                },
            },
            "capabilities": {
                "chat": {"available": True, "reason": "", "requires": ["llm"], "setup_hint": ""},
                "voice": {"available": True, "reason": "", "requires": ["tts"], "setup_hint": ""},
                "image": {"available": True, "reason": "", "requires": ["image"], "setup_hint": ""},
            },
        })
    except AssertionError as exc:
        assert "status.capabilities: missing memory" in str(exc)
    else:
        raise AssertionError("missing memory capability should fail")
