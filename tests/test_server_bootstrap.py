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
