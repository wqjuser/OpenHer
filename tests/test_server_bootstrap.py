"""Server bootstrap module boundary tests."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_module_exports_runtime_hooks():
    import server.bootstrap as bootstrap

    assert hasattr(bootstrap, "startup")
    assert hasattr(bootstrap, "shutdown")
    assert hasattr(bootstrap, "sync_legacy_globals")


def test_main_delegates_lifespan_to_bootstrap_module():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "from server import bootstrap" in main_source
    assert "context: AppContext = _app.state.openher" in main_source
    assert "await bootstrap.startup(context)" in main_source
    assert "await bootstrap.shutdown(context)" in main_source
    assert "async def startup(" not in main_source
    assert "async def shutdown(" not in main_source


def test_bootstrap_degrades_when_llm_provider_is_unavailable():
    bootstrap_source = (ROOT / "server" / "bootstrap.py").read_text(encoding="utf-8")

    assert 'llm_available = bool(llm_cfg.get("available", True))' in bootstrap_source
    assert "context.llm_client = None" in bootstrap_source
    assert "LLM provider" in bootstrap_source
    assert "ChatApiService(" in bootstrap_source
    assert "session_manager=None" in bootstrap_source
    assert "context.session_agent_factory = None" in bootstrap_source
    assert "context.session_manager = None" in bootstrap_source
    assert "if context.llm_client and context.session_manager:" in bootstrap_source
    assert "context.proactive_service = None" in bootstrap_source
    assert "context.proactive_task = None" in bootstrap_source
