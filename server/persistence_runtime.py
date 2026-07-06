"""Persistence runtime service assembly for OpenHer startup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from engine.chat_log_store import ChatLogStore
from engine.state_store import StateStore
from memory.memory_store import MemoryStore
from providers.api_config import get_memory_config, get_memory_provider_config
from providers.memory.evermemos.evermemos_client import EverMemOSClient


@dataclass(frozen=True)
class PersistenceRuntimeServices:
    data_dir: Path
    genome_data_dir: Path
    state_store: StateStore
    chat_log_store: ChatLogStore
    memory_store: MemoryStore
    evermemos: EverMemOSClient | None
    messages: tuple[str, ...]


StoreFactory = Callable[[str], Any]
EverMemOSFactory = Callable[..., Any]


def resolve_runtime_data_dir(base_dir: Path, configured: str | None = None) -> Path:
    raw_configured = os.getenv("OPENHER_DATA_DIR", "").strip() if configured is None else configured.strip()
    if not raw_configured:
        return Path(base_dir) / ".data"

    data_dir = Path(raw_configured).expanduser()
    if not data_dir.is_absolute():
        data_dir = Path(base_dir) / data_dir
    return data_dir


def resolve_runtime_path(base_dir: Path, data_dir: Path, configured_path: str) -> Path:
    path = Path(configured_path).expanduser()
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == ".data":
        return Path(data_dir).joinpath(*path.parts[1:])
    return Path(base_dir) / path


async def build_persistence_runtime_services(
    base_dir: Path,
    *,
    configured_data_dir: str | None = None,
    memory_config: Mapping[str, Any] | None = None,
    memory_provider_config: Mapping[str, Any] | None = None,
    state_store_factory: StoreFactory = StateStore,
    chat_log_store_factory: StoreFactory = ChatLogStore,
    memory_store_factory: StoreFactory = MemoryStore,
    evermemos_client_factory: EverMemOSFactory = EverMemOSClient,
) -> PersistenceRuntimeServices:
    data_dir = resolve_runtime_data_dir(Path(base_dir), configured=configured_data_dir)
    genome_data_dir = data_dir / "genome"
    genome_data_dir.mkdir(parents=True, exist_ok=True)

    state_store = state_store_factory(str(data_dir / "openher.db"))
    chat_log_store = chat_log_store_factory(str(data_dir / "chat.db"))

    mem_prov_cfg = memory_provider_config or get_memory_provider_config()
    soulmem_db = resolve_runtime_path(Path(base_dir), data_dir, str(mem_prov_cfg["soulmem"]["db_path"]))
    soulmem_db.parent.mkdir(parents=True, exist_ok=True)
    memory_store = memory_store_factory(str(soulmem_db))

    mem_cfg = memory_config or get_memory_config()
    messages: list[str] = []
    evermemos = None
    if mem_cfg["enabled"] and (mem_cfg["base_url"] or mem_cfg["api_key"]):
        evermemos = evermemos_client_factory(
            base_url=mem_cfg["base_url"] or None,
            api_key=mem_cfg["api_key"] or None,
        )
        if evermemos.available:
            await evermemos.verify_connection()
    else:
        messages.append("ℹ EverMemOS: 未配置或已禁用，使用本地 MemoryStore")

    return PersistenceRuntimeServices(
        data_dir=data_dir,
        genome_data_dir=genome_data_dir,
        state_store=state_store,
        chat_log_store=chat_log_store,
        memory_store=memory_store,
        evermemos=evermemos,
        messages=tuple(messages),
    )
