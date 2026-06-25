"""Server route module boundary tests."""

from __future__ import annotations

import importlib
from pathlib import Path


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
