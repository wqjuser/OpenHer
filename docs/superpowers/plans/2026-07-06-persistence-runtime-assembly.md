# Persistence Runtime Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move runtime data directory, local stores, local memory, and EverMemOS service construction out of `server/bootstrap.py` into a focused persistence runtime module.

**Architecture:** Add `server/persistence_runtime.py` with path-resolution helpers, `PersistenceRuntimeServices`, and `build_persistence_runtime_services()`. Bootstrap will call the async builder, assign returned services to `AppContext`, print returned messages, and continue owning session, WebSocket, cron, and proactive orchestration.

**Tech Stack:** Python 3.11+, dataclasses, pathlib, pytest, pyright, existing FastAPI runtime and Makefile gates.

---

### Task 1: Add Persistence Runtime Boundary Tests

**Files:**
- Create: `tests/test_persistence_runtime.py`
- Modify: `tests/test_server_bootstrap.py`

- [x] **Step 1: Add path resolution tests**

Create `tests/test_persistence_runtime.py` with:

```python
"""Persistence runtime assembly boundary tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any


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
```

- [x] **Step 2: Add runtime path remapping tests**

Append:

```python
def test_runtime_path_remapping_preserves_existing_semantics(tmp_path):
    from server.persistence_runtime import resolve_runtime_path

    data_dir = tmp_path / "runtime"
    assert resolve_runtime_path(tmp_path, data_dir, ".data/memory.db") == data_dir / "memory.db"

    absolute = tmp_path / "external" / "memory.db"
    assert resolve_runtime_path(tmp_path, data_dir, str(absolute)) == absolute

    assert resolve_runtime_path(tmp_path, data_dir, "var/memory.db") == tmp_path / "var/memory.db"
```

- [x] **Step 3: Add local store assembly test**

Append:

```python
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
    assert runtime.state_store.path == str(data_dir / "openher.db")
    assert runtime.chat_log_store.path == str(data_dir / "chat.db")
    assert runtime.memory_store.path == str(data_dir / "memory.db")
    assert runtime.evermemos is None
    assert runtime.messages == ("ℹ EverMemOS: 未配置或已禁用，使用本地 MemoryStore",)
```

- [x] **Step 4: Add EverMemOS verification assembly test**

Append:

```python
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
    assert runtime.memory_store.path == str(tmp_path / "var/soulmem.db")
    assert runtime.messages == ()
```

- [x] **Step 5: Update bootstrap source boundary test**

In `tests/test_server_bootstrap.py`, import-path tests should target `server.persistence_runtime`:

```python
def test_runtime_data_dir_defaults_to_repo_data_dir(monkeypatch, tmp_path):
    from server.persistence_runtime import resolve_runtime_data_dir

    monkeypatch.delenv("OPENHER_DATA_DIR", raising=False)

    assert resolve_runtime_data_dir(tmp_path) == tmp_path / ".data"
```

Apply the same module swap to the two other `test_runtime_data_dir_*` tests and three `test_runtime_path_*` tests.

Update `test_bootstrap_degrades_when_llm_provider_is_unavailable()` with these persistence boundary assertions:

```python
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
```

- [x] **Step 6: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_persistence_runtime.py tests/test_server_bootstrap.py -v
```

Expected: FAIL because `server.persistence_runtime` does not exist and bootstrap still constructs persistence services inline.

### Task 2: Implement Persistence Runtime Module

**Files:**
- Create: `server/persistence_runtime.py`
- Modify: `server/bootstrap.py`

- [x] **Step 1: Add persistence runtime module**

Create `server/persistence_runtime.py`:

```python
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
    state_store: Any
    chat_log_store: Any
    memory_store: Any
    evermemos: Any | None
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
```

- [x] **Step 2: Refactor bootstrap imports**

In `server/bootstrap.py`, remove:

```python
import os
from engine.chat_log_store import ChatLogStore
from engine.state_store import StateStore
from memory.memory_store import MemoryStore
from providers.api_config import get_memory_config
from providers.memory.evermemos.evermemos_client import EverMemOSClient
```

Add:

```python
from server.persistence_runtime import build_persistence_runtime_services
```

Delete `_runtime_data_dir()` and `_runtime_path()` from bootstrap.

- [x] **Step 3: Refactor startup persistence assembly**

Replace the inline persistence block with:

```python
    persistence_runtime = await build_persistence_runtime_services(base_dir)
    context.genome_data_dir = str(persistence_runtime.genome_data_dir)
    context.state_store = persistence_runtime.state_store
    context.chat_log_store = persistence_runtime.chat_log_store
    context.memory_store = persistence_runtime.memory_store
    context.evermemos = persistence_runtime.evermemos
    for message in persistence_runtime.messages:
        print(message)
```

- [x] **Step 4: Run persistence runtime tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_persistence_runtime.py tests/test_server_bootstrap.py -v
```

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-persistence-runtime-assembly.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so every executed step is checked.

- [x] **Step 2: Run focused server persistence tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_persistence_runtime.py tests/test_server_bootstrap.py tests/test_server_routes.py tests/test_doctor.py tests/test_data_lifecycle.py -v
```

Expected: all focused persistence, bootstrap, status, doctor, and data lifecycle tests pass.

- [x] **Step 3: Run repository checks**

Run:

```bash
make check
```

Expected: pyright reports 0 errors and the full pytest suite passes.

- [x] **Step 4: Run runtime/smoke/build gates**

Run:

```bash
make doctor backend-acceptance-smoke backend-runtime-smoke backend-chat-smoke desktop-acceptance-smoke desktop-build
```

Expected: each command exits 0. `make doctor` may report optional warnings for unconfigured optional providers or missing local backups.

- [x] **Step 5: Commit and push**

Run:

```bash
git add docs/superpowers/specs/2026-07-06-persistence-runtime-assembly-design.md docs/superpowers/plans/2026-07-06-persistence-runtime-assembly.md server/persistence_runtime.py server/bootstrap.py tests/test_persistence_runtime.py tests/test_server_bootstrap.py
git commit -m "refactor: extract persistence runtime assembly"
git push origin main
```
