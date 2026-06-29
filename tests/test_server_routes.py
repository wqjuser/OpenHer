"""Server route module boundary tests."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def test_route_modules_exist_and_export_routers():
    for module_name in (
        "server.routes.health",
        "server.routes.persona",
        "server.routes.chat",
        "server.routes.media",
        "server.routes.demo",
        "server.routes.websocket",
    ):
        module = importlib.import_module(module_name)
        assert hasattr(module, "router"), module_name


def test_create_app_registers_core_routes():
    import main

    app = main.create_app()
    expected_routes = {
        "api_status": "/api/status",
        "proactive_metrics": "/api/proactive/metrics",
        "list_personas": "/api/personas",
        "chat_api": "/api/chat",
        "demo_inject": "/api/demo/inject",
        "websocket_chat": "/ws/chat",
    }

    for route_name, path in expected_routes.items():
        assert str(app.url_path_for(route_name)) == path


def test_main_delegates_core_route_registration_to_modules():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "register_routes(server_app)" in main_source
    assert "@app.get(\"/api/status\")" not in main_source
    assert "@app.post(\"/api/chat\")" not in main_source
    assert "@app.websocket(\"/ws/chat\")" not in main_source


def test_api_status_reports_provider_readiness_without_secrets():
    from fastapi.testclient import TestClient
    import main
    from server.context import AppContext

    app = main.create_app(AppContext())

    with patch("server.routes.health.get_llm_config", return_value={
        "provider": "deepseek",
        "available": False,
        "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        "api_key": "secret-llm-key",
    }):
        with patch("server.routes.health.get_tts_config", return_value={
            "provider": "dashscope",
            "available": False,
            "missing_key_env": "DASHSCOPE_API_KEY or TTS_API_KEY",
            "active_api_key": "secret-tts-key",
        }):
            with patch("server.routes.health.get_image_config", return_value={
                "provider": "gemini",
                "available": True,
                "missing_key_env": "",
                "active_api_key": "secret-image-key",
            }):
                with patch("server.routes.health.get_memory_config", return_value={
                    "enabled": True,
                    "base_url": "https://memory.example.test/api/v1",
                    "api_key": "secret-memory-key",
                }):
                    response = TestClient(app, raise_server_exceptions=False).get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["providers"] == {
        "llm": {
            "provider": "deepseek",
            "available": False,
            "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        },
        "tts": {
            "provider": "dashscope",
            "available": False,
            "missing_key_env": "DASHSCOPE_API_KEY or TTS_API_KEY",
        },
        "image": {
            "provider": "gemini",
            "available": True,
            "missing_key_env": "",
        },
        "memory": {
            "provider": "evermemos",
            "enabled": True,
            "configured": True,
            "available": False,
        },
    }
    assert body["capabilities"] == {
        "chat": {
            "available": False,
            "reason": "LLM provider is not configured (missing DEEPSEEK_API_KEY or LLM_API_KEY)",
            "requires": ["llm"],
        },
        "voice": {
            "available": False,
            "reason": "TTS provider is not configured (missing DASHSCOPE_API_KEY or TTS_API_KEY)",
            "requires": ["tts"],
        },
        "image": {
            "available": True,
            "reason": "",
            "requires": ["image"],
        },
        "memory": {
            "available": False,
            "reason": "EverMemOS is not available",
            "requires": ["memory"],
        },
    }
    assert "secret" not in response.text
    assert "memory.example.test" not in response.text
