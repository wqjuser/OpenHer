"""Server application context tests."""

from __future__ import annotations


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
