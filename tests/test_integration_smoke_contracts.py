"""Shared integration smoke contract tests."""

from __future__ import annotations

import json


def valid_status_body() -> dict:
    return {
        "status": "running",
        "providers": {
            "llm": {"provider": "deepseek", "available": True, "missing_key_env": "", "setup_hint": ""},
            "tts": {
                "provider": "dashscope",
                "available": False,
                "missing_key_env": "TTS_API_KEY",
                "setup_hint": "set tts",
            },
            "image": {"provider": "gemini", "available": True, "missing_key_env": "", "setup_hint": ""},
            "memory": {
                "provider": "evermemos",
                "enabled": True,
                "configured": True,
                "available": False,
                "setup_hint": "set memory",
            },
        },
        "capabilities": {
            "chat": {"available": True, "reason": "", "requires": ["llm"], "setup_hint": ""},
            "voice": {
                "available": False,
                "reason": "TTS missing",
                "requires": ["tts"],
                "setup_hint": "set tts",
            },
            "image": {"available": True, "reason": "", "requires": ["image"], "setup_hint": ""},
            "memory": {
                "available": False,
                "reason": "EverMemOS unavailable",
                "requires": ["memory"],
                "setup_hint": "set memory",
            },
        },
    }


def test_smoke_contracts_format_and_safe_value_helpers():
    from scripts.integration.smoke_contracts import format_result, safe_value

    assert format_result("status", {"z": "last", "a": "first"}) == "status: a=first z=last"
    assert safe_value("a\nb") == "a b"
    assert len(safe_value("x" * 600)) == 500


def test_smoke_contracts_decodes_json_objects_only():
    from scripts.integration.smoke_contracts import decode_json

    assert decode_json(json.dumps({"ok": True})) == {"ok": True}
    assert decode_json("") == {}
    try:
        decode_json(json.dumps(["not", "object"]))
    except AssertionError as exc:
        assert "expected JSON object" in str(exc)
    else:
        raise AssertionError("list JSON should fail")


def test_smoke_contracts_validates_status_diagnostics():
    from scripts.integration.smoke_contracts import bool_text, validate_status_diagnostics

    diagnostics = validate_status_diagnostics(valid_status_body(), require_setup_hints=True)

    assert diagnostics.chat["available"] is True
    assert diagnostics.voice["available"] is False
    assert diagnostics.memory_provider["configured"] is True
    assert bool_text(diagnostics.memory["available"], "memory available") == "false"


def test_smoke_contracts_rejects_missing_capability():
    from scripts.integration.smoke_contracts import validate_status_diagnostics

    body = valid_status_body()
    body["capabilities"].pop("memory")

    try:
        validate_status_diagnostics(body)
    except AssertionError as exc:
        assert "status.capabilities: missing memory" in str(exc)
    else:
        raise AssertionError("missing memory capability should fail")
