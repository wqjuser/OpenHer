"""Provider diagnostics transformation tests."""

from __future__ import annotations


def test_provider_capability_status_redacts_secret_values():
    from providers.diagnostics import provider_capability_status

    status = provider_capability_status({
        "provider": "deepseek",
        "available": False,
        "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        "api_key": "secret-llm-key",
    })

    assert status == {
        "provider": "deepseek",
        "available": False,
        "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        "setup_hint": "Set DEEPSEEK_API_KEY or LLM_API_KEY in .env, then restart the backend.",
    }
    assert "secret" not in repr(status)


def test_provider_capability_status_has_empty_hint_when_available():
    from providers.diagnostics import provider_capability_status

    status = provider_capability_status({
        "provider": "gemini",
        "available": True,
        "missing_key_env": "",
        "active_api_key": "secret-image-key",
    })

    assert status == {
        "provider": "gemini",
        "available": True,
        "missing_key_env": "",
        "setup_hint": "",
    }
    assert "secret" not in repr(status)


def test_memory_runtime_status_uses_config_and_runtime_availability_without_leaking_values():
    from providers.diagnostics import memory_runtime_status

    status = memory_runtime_status(
        {
            "enabled": True,
            "base_url": "https://memory.example.test/api/v1",
            "api_key": "secret-memory-key",
        },
        runtime_available=False,
    )

    assert status == {
        "provider": "evermemos",
        "enabled": True,
        "configured": True,
        "available": False,
        "setup_hint": "Check EverMemOS credentials or network connectivity, then restart the backend.",
    }
    assert "secret" not in repr(status)
    assert "memory.example.test" not in repr(status)


def test_capabilities_status_matches_backend_status_contract():
    from providers.diagnostics import capabilities_status

    providers = {
        "llm": {
            "provider": "deepseek",
            "available": False,
            "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
            "setup_hint": "Set DEEPSEEK_API_KEY or LLM_API_KEY in .env, then restart the backend.",
        },
        "tts": {
            "provider": "dashscope",
            "available": False,
            "missing_key_env": "DASHSCOPE_API_KEY or TTS_API_KEY",
            "setup_hint": "Set DASHSCOPE_API_KEY or TTS_API_KEY in .env, then restart the backend.",
        },
        "image": {
            "provider": "gemini",
            "available": True,
            "missing_key_env": "",
            "setup_hint": "",
        },
        "memory": {
            "provider": "evermemos",
            "enabled": True,
            "configured": True,
            "available": False,
            "setup_hint": "Check EverMemOS credentials or network connectivity, then restart the backend.",
        },
    }

    assert capabilities_status(providers) == {
        "chat": {
            "available": False,
            "reason": "LLM provider is not configured (missing DEEPSEEK_API_KEY or LLM_API_KEY)",
            "requires": ["llm"],
            "setup_hint": "Set DEEPSEEK_API_KEY or LLM_API_KEY in .env, then restart the backend.",
        },
        "voice": {
            "available": False,
            "reason": "TTS provider is not configured (missing DASHSCOPE_API_KEY or TTS_API_KEY)",
            "requires": ["tts"],
            "setup_hint": "Set DASHSCOPE_API_KEY or TTS_API_KEY in .env, then restart the backend.",
        },
        "image": {
            "available": True,
            "reason": "",
            "requires": ["image"],
            "setup_hint": "",
        },
        "memory": {
            "available": False,
            "reason": "EverMemOS is not available",
            "requires": ["memory"],
            "setup_hint": "Check EverMemOS credentials or network connectivity, then restart the backend.",
        },
    }


def test_provider_secret_configured_reads_generic_and_active_secret_fields():
    from providers.diagnostics import provider_secret_configured

    assert provider_secret_configured({"api_key": "secret"}) is True
    assert provider_secret_configured({"api_key": ""}) is False
    assert provider_secret_configured({"active_api_key": "secret"}, active=True) is True
    assert provider_secret_configured({"active_api_key": ""}, active=True) is False
