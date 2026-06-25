"""Server application context tests."""

from __future__ import annotations

from typing import Any, get_type_hints


def test_create_app_attaches_app_context():
    import main

    app = main.create_app()

    assert hasattr(app.state, "openher")
    assert app.state.openher.ws_registry is not None
    assert app.state.openher.demo_inject_service is not None


def test_module_app_uses_app_context():
    import main

    assert hasattr(main.app.state, "openher")
    assert main.app.state.openher.ws_registry is main.ws_registry


def test_app_context_annotations_are_not_any_for_core_services():
    from server.context import AppContext

    hints = get_type_hints(AppContext)

    for field_name in (
        "session_manager",
        "chat_log_store",
        "memory_store",
        "proactive_service",
        "ws_chat_turn_service",
        "persona_switch_service",
        "ws_tts_service",
    ):
        assert hints[field_name] is not Any
