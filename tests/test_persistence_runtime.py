"""Persistence runtime assembly boundary tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast


class FakeStore:
    def __init__(self, path: str) -> None:
        self.path = path


class FakeEverMemOS:
    def __init__(self, *, base_url: str | None, api_key: str | None) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.available = True
        self.verify_calls = 0

    async def verify_connection(self) -> None:
        self.verify_calls += 1


def test_runtime_data_dir_resolution_matches_bootstrap_contract(tmp_path, monkeypatch):
    from server.persistence_runtime import resolve_runtime_data_dir

    monkeypatch.delenv("OPENHER_DATA_DIR", raising=False)
    assert resolve_runtime_data_dir(tmp_path) == tmp_path / ".data"

    monkeypatch.setenv("OPENHER_DATA_DIR", ".runtime-smoke")
    assert resolve_runtime_data_dir(tmp_path) == tmp_path / ".runtime-smoke"

    absolute = tmp_path / "isolated"
    monkeypatch.setenv("OPENHER_DATA_DIR", str(absolute))
    assert resolve_runtime_data_dir(tmp_path) == absolute

    assert resolve_runtime_data_dir(tmp_path, configured="custom") == tmp_path / "custom"


def test_runtime_path_remapping_preserves_existing_semantics(tmp_path):
    from server.persistence_runtime import resolve_runtime_path

    data_dir = tmp_path / "runtime"
    assert resolve_runtime_path(tmp_path, data_dir, ".data/memory.db") == data_dir / "memory.db"

    absolute = tmp_path / "external" / "memory.db"
    assert resolve_runtime_path(tmp_path, data_dir, str(absolute)) == absolute

    assert resolve_runtime_path(tmp_path, data_dir, "var/memory.db") == tmp_path / "var/memory.db"


async def test_persistence_runtime_builds_local_stores_and_disabled_evermemos(tmp_path):
    from server.persistence_runtime import build_persistence_runtime_services

    runtime = await build_persistence_runtime_services(
        tmp_path,
        configured_data_dir="runtime-data",
        memory_config={"enabled": False, "base_url": "", "api_key": ""},
        memory_provider_config={"soulmem": {"db_path": ".data/memory.db"}},
        state_store_factory=FakeStore,
        chat_log_store_factory=FakeStore,
        memory_store_factory=FakeStore,
        evermemos_client_factory=FakeEverMemOS,
    )

    data_dir = tmp_path / "runtime-data"
    assert runtime.data_dir == data_dir
    assert runtime.genome_data_dir == data_dir / "genome"
    assert data_dir.joinpath("genome").is_dir()
    assert cast(FakeStore, runtime.state_store).path == str(data_dir / "openher.db")
    assert cast(FakeStore, runtime.chat_log_store).path == str(data_dir / "chat.db")
    assert cast(FakeStore, runtime.memory_store).path == str(data_dir / "memory.db")
    assert runtime.evermemos is None
    assert runtime.messages == ("ℹ EverMemOS: 未配置或已禁用，使用本地 MemoryStore",)


async def test_persistence_runtime_builds_and_verifies_available_evermemos(tmp_path):
    from server.persistence_runtime import build_persistence_runtime_services

    calls: list[dict[str, Any]] = []

    def evermemos_factory(**kwargs: Any) -> FakeEverMemOS:
        calls.append(kwargs)
        return FakeEverMemOS(**kwargs)

    runtime = await build_persistence_runtime_services(
        tmp_path,
        memory_config={
            "enabled": True,
            "base_url": "https://memory.example.test/api/v1",
            "api_key": "secret",
        },
        memory_provider_config={"soulmem": {"db_path": "var/soulmem.db"}},
        state_store_factory=FakeStore,
        chat_log_store_factory=FakeStore,
        memory_store_factory=FakeStore,
        evermemos_client_factory=evermemos_factory,
    )

    assert calls == [{"base_url": "https://memory.example.test/api/v1", "api_key": "secret"}]
    assert isinstance(runtime.evermemos, FakeEverMemOS)
    assert runtime.evermemos.verify_calls == 1
    assert cast(FakeStore, runtime.memory_store).path == str(tmp_path / "var/soulmem.db")
    assert runtime.messages == ()
