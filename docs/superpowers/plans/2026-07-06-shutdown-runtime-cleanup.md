# Shutdown Runtime Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move shutdown cleanup out of `server/bootstrap.py` into a focused runtime module.

**Architecture:** Add `server/shutdown_runtime.py` with helpers for task cancellation and EverMemOS session closing plus a `shutdown_runtime_services()` coordinator. Bootstrap will call the coordinator and print returned messages.

**Tech Stack:** Python 3.11+, asyncio, pytest, pyright, existing FastAPI lifespan and `AppContext` services.

---

### Task 1: Add Shutdown Runtime Boundary Tests

**Files:**
- Create: `tests/test_shutdown_runtime.py`
- Modify: `tests/test_server_bootstrap.py`

- [x] **Step 1: Add full cleanup-order test**

Create `tests/test_shutdown_runtime.py` with fakes for a running proactive task, cron scheduler, session manager, state store, memory store, chat log store, and EverMemOS client.

Assert that `shutdown_runtime_services(context)`:

```python
assert context.proactive_task is None
assert events == [
    "task.cancel",
    "task.await",
    "cron.stop",
    "session.persist_all",
    "state.close",
    "memory.close",
    "chat.close",
    "evermemos.close:uid-1:iris:group-1",
    "evermemos.close:uid-2:nova:group-2",
]
assert messages == ("✓ 状态已保存，服务关闭",)
```

- [x] **Step 2: Add optional dependency test**

Append a test that passes a context with all shutdown dependencies set to `None`, except a completed proactive task. Assert no exception is raised, the completed task is not cancelled, and the existing message is returned.

- [x] **Step 3: Update bootstrap boundary test**

Update `tests/test_server_bootstrap.py::test_bootstrap_degrades_when_llm_provider_is_unavailable()` to assert:

```python
assert "from server.shutdown_runtime import shutdown_runtime_services" in bootstrap_source
assert "messages = await shutdown_runtime_services(context)" in bootstrap_source
assert "for message in messages:" in bootstrap_source
assert "context.proactive_task.cancel()" not in bootstrap_source
assert "context.cron_scheduler.stop()" not in bootstrap_source
assert "context.session_manager.persist_all()" not in bootstrap_source
assert "context.state_store.close()" not in bootstrap_source
assert "context.memory_store.close()" not in bootstrap_source
assert "context.chat_log_store.close()" not in bootstrap_source
assert "context.evermemos.close_session(" not in bootstrap_source
```

- [x] **Step 4: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_shutdown_runtime.py tests/test_server_bootstrap.py::test_bootstrap_degrades_when_llm_provider_is_unavailable -v
```

Expected: FAIL because `server.shutdown_runtime` does not exist and bootstrap still owns shutdown cleanup.

### Task 2: Implement Shutdown Runtime Module

**Files:**
- Create: `server/shutdown_runtime.py`
- Modify: `server/bootstrap.py`

- [x] **Step 1: Add shutdown runtime module**

Create `server/shutdown_runtime.py` with:

```python
"""Shutdown cleanup runtime for OpenHer lifespan."""

from __future__ import annotations

import asyncio
from typing import Any

from server.context import AppContext, SessionManagerService


async def cancel_proactive_task(context: AppContext) -> None:
    ...


async def close_evermemos_sessions(evermemos: Any | None, session_manager: SessionManagerService | None) -> None:
    ...


async def shutdown_runtime_services(context: AppContext) -> tuple[str, ...]:
    ...
```

- [x] **Step 2: Refactor bootstrap shutdown**

In `server/bootstrap.py`, remove direct `asyncio` usage and the inline cleanup body. Add:

```python
from server.shutdown_runtime import shutdown_runtime_services
```

Change `shutdown()` to:

```python
async def shutdown(context: AppContext) -> None:
    """Persist runtime state and close resources on server shutdown."""
    messages = await shutdown_runtime_services(context)
    for message in messages:
        print(message)
```

- [x] **Step 3: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_shutdown_runtime.py tests/test_server_bootstrap.py -v
```

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-shutdown-runtime-cleanup.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so every executed step is checked.

- [x] **Step 2: Run repository checks**

Run:

```bash
make check
```

Expected: pyright reports 0 errors and the full pytest suite passes.

- [x] **Step 3: Run runtime/smoke/build gates**

Run:

```bash
make doctor backend-acceptance-smoke backend-runtime-smoke backend-chat-smoke desktop-acceptance-smoke desktop-build
```

Expected: each command exits 0. `make doctor` may report optional warnings for unconfigured optional providers or missing local backups.

- [x] **Step 4: Commit and push**

Run:

```bash
git add docs/superpowers/specs/2026-07-06-shutdown-runtime-cleanup-design.md docs/superpowers/plans/2026-07-06-shutdown-runtime-cleanup.md server/shutdown_runtime.py server/bootstrap.py tests/test_shutdown_runtime.py tests/test_server_bootstrap.py
git commit -m "refactor: extract shutdown runtime cleanup"
git push origin main
```
