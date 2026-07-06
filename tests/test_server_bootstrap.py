"""Server bootstrap module boundary tests."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_module_exports_runtime_hooks():
    import server.bootstrap as bootstrap

    assert hasattr(bootstrap, "startup")
    assert hasattr(bootstrap, "shutdown")
    assert hasattr(bootstrap, "sync_legacy_globals")


def test_runtime_data_dir_defaults_to_repo_data_dir(monkeypatch, tmp_path):
    from server.persistence_runtime import resolve_runtime_data_dir

    monkeypatch.delenv("OPENHER_DATA_DIR", raising=False)

    assert resolve_runtime_data_dir(tmp_path) == tmp_path / ".data"


def test_runtime_data_dir_accepts_absolute_override(monkeypatch, tmp_path):
    from server.persistence_runtime import resolve_runtime_data_dir

    data_dir = tmp_path / "isolated"
    monkeypatch.setenv("OPENHER_DATA_DIR", str(data_dir))

    assert resolve_runtime_data_dir(tmp_path) == data_dir


def test_runtime_data_dir_resolves_relative_override_against_repo(monkeypatch, tmp_path):
    from server.persistence_runtime import resolve_runtime_data_dir

    monkeypatch.setenv("OPENHER_DATA_DIR", ".runtime-smoke")

    assert resolve_runtime_data_dir(tmp_path) == tmp_path / ".runtime-smoke"


def test_runtime_path_remaps_default_data_paths_to_runtime_dir(tmp_path):
    from server.persistence_runtime import resolve_runtime_path

    assert (
        resolve_runtime_path(tmp_path, tmp_path / "runtime", ".data/memory.db")
        == tmp_path / "runtime" / "memory.db"
    )


def test_runtime_path_preserves_absolute_paths(tmp_path):
    from server.persistence_runtime import resolve_runtime_path

    absolute_path = tmp_path / "external" / "memory.db"

    assert resolve_runtime_path(tmp_path, tmp_path / "runtime", str(absolute_path)) == absolute_path


def test_runtime_path_resolves_custom_relative_paths_against_repo(tmp_path):
    from server.persistence_runtime import resolve_runtime_path

    assert (
        resolve_runtime_path(tmp_path, tmp_path / "runtime", "var/memory.db")
        == tmp_path / "var" / "memory.db"
    )


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

    assert "from server.provider_runtime import build_provider_runtime_services" in bootstrap_source
    assert "provider_runtime = build_provider_runtime_services(base_dir)" in bootstrap_source
    assert "context.llm_client = provider_runtime.llm_client" in bootstrap_source
    assert "context.tts_engine = provider_runtime.tts_engine" in bootstrap_source
    assert "context.ws_tts_service = provider_runtime.ws_tts_service" in bootstrap_source
    assert "context.media_api_service = provider_runtime.media_api_service" in bootstrap_source
    assert "if provider_runtime.tts_available:" in bootstrap_source
    assert "get_llm_config" not in bootstrap_source
    assert "get_tts_config" not in bootstrap_source
    assert "get_image_config" not in bootstrap_source
    assert "LLMClient(" not in bootstrap_source
    assert "TTSEngine(" not in bootstrap_source
    assert "from server.persistence_runtime import build_persistence_runtime_services" in bootstrap_source
    assert "persistence_runtime = await build_persistence_runtime_services(base_dir)" in bootstrap_source
    assert "context.genome_data_dir = str(persistence_runtime.genome_data_dir)" in bootstrap_source
    assert "context.state_store = persistence_runtime.state_store" in bootstrap_source
    assert "context.chat_log_store = persistence_runtime.chat_log_store" in bootstrap_source
    assert "context.memory_store = persistence_runtime.memory_store" in bootstrap_source
    assert "context.evermemos = persistence_runtime.evermemos" in bootstrap_source
    assert "StateStore(" not in bootstrap_source
    assert "ChatLogStore(" not in bootstrap_source
    assert "MemoryStore(" not in bootstrap_source
    assert "EverMemOSClient(" not in bootstrap_source
    assert "get_memory_provider_config" not in bootstrap_source
    assert "ChatApiService(" in bootstrap_source
    assert "session_manager=None" in bootstrap_source
    assert "context.session_agent_factory = None" in bootstrap_source
    assert "context.session_manager = None" in bootstrap_source
    assert "if context.llm_client and context.session_manager:" in bootstrap_source
    assert "context.proactive_service = None" in bootstrap_source
    assert "context.proactive_task = None" in bootstrap_source
