# Background Runtime Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move cron scheduler and proactive heartbeat startup assembly out of `server/bootstrap.py`.

**Architecture:** Add `server/background_runtime.py` with focused helpers and a `build_background_runtime_services()` builder. Bootstrap will call the builder, assign returned services to `AppContext`, print startup messages, and keep shutdown cleanup centralized.

**Tech Stack:** Python 3.11+, dataclasses, pytest, pyright, existing cron/proactive server services and Makefile gates.

---

### Task 1: Add Background Runtime Boundary Tests

**Files:**
- Create: `tests/test_background_runtime.py`
- Modify: `tests/test_server_bootstrap.py`

- [x] **Step 1: Add available-path assembly test**

Create `tests/test_background_runtime.py` with a test that imports `build_background_runtime_services`, injects fake scheduler/proactive/task factories, and asserts:

```python
runtime = build_background_runtime_services(...)

assert runtime.cron_scheduler is scheduler
assert scheduler.generator is not None
assert scheduler.callback is not None
assert scheduler.registered == [(cron_skills, ["iris", "nova"])]
assert scheduler.started is True
assert runtime.proactive_service is proactive_service
assert runtime.proactive_task == "task-handle"
assert proactive_kwargs["state_store"] is state_store
assert proactive_kwargs["session_manager"] is session_manager
assert proactive_kwargs["evermemos"] is evermemos
assert proactive_kwargs["ws_connections"] is ws_connections
assert proactive_kwargs["instance_id"] == "instance-1"
assert proactive_kwargs["config"] == {"cooldown_hours": 2, "max_pending": 7, "lock_ttl": 30}
assert proactive_kwargs["interval_seconds"] == 99
proactive_kwargs["persist_agent"]("agent-1")
assert session_manager.persisted == ["agent-1"]
assert runtime.messages == ("✓ 主动消息心跳已启动 (cooldown=2h, ttl=30s)",)
```

- [x] **Step 2: Add unavailable-path degradation test**

Append a test that passes `llm_client=None`, a non-empty `cron_skills` list, and factories that raise if called. Assert:

```python
assert runtime.cron_scheduler is None
assert runtime.proactive_service is None
assert runtime.proactive_task is None
assert runtime.messages == ("⚠ LLM 未配置，已跳过定时任务调度",)
```

- [x] **Step 3: Add helper behavior tests**

Append tests for:

```python
assert load_proactive_config(tmp_path) == {"cooldown_hours": 4, "max_pending": 3, "lock_ttl": 600}
```

Create `providers/memory/evermemos/memory_config.yaml` under `tmp_path` and assert overrides map to the returned keys.

Use fake persona loader and fake LLM to assert `generate_cron_message(...)` returns the LLM content and sends a system message containing the persona name and skill prompt.

Use a fake memory store to assert `deliver_cron_message(...)` writes:

```python
{
    "user_id": "__broadcast__",
    "persona_id": "iris",
    "content": "[weather] bring umbrella",
    "category": "event",
    "importance": 0.6,
}
```

- [x] **Step 4: Update bootstrap boundary test**

Update `tests/test_server_bootstrap.py::test_bootstrap_degrades_when_llm_provider_is_unavailable()` to assert:

```python
assert "from server.background_runtime import build_background_runtime_services" in bootstrap_source
assert "background_runtime = build_background_runtime_services(" in bootstrap_source
assert "context.cron_scheduler = background_runtime.cron_scheduler" in bootstrap_source
assert "context.proactive_service = background_runtime.proactive_service" in bootstrap_source
assert "context.proactive_task = background_runtime.proactive_task" in bootstrap_source
assert "for message in background_runtime.messages:" in bootstrap_source
assert "CronScheduler(" not in bootstrap_source
assert "ProactiveService(" not in bootstrap_source
assert "_cron_generate_message" not in bootstrap_source
assert "_cron_deliver_message" not in bootstrap_source
assert "_load_proactive_config" not in bootstrap_source
```

- [x] **Step 5: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_background_runtime.py tests/test_server_bootstrap.py::test_bootstrap_degrades_when_llm_provider_is_unavailable -v
```

Expected: FAIL because `server.background_runtime` does not exist and bootstrap still constructs background services inline.

### Task 2: Implement Background Runtime Module

**Files:**
- Create: `server/background_runtime.py`
- Modify: `server/bootstrap.py`

- [x] **Step 1: Add background runtime module**

Create `server/background_runtime.py` with:

```python
"""Background runtime service assembly for OpenHer startup."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

from agent.cron_scheduler import CronScheduler
from server.proactive_service import ProactiveService


ProactiveConfig = dict[str, Any]
CronSchedulerFactory = Callable[[], Any]
ProactiveServiceFactory = Callable[..., Any]
TaskCreator = Callable[[Awaitable[None]], Any]


@dataclass(frozen=True)
class BackgroundRuntimeServices:
    cron_scheduler: CronScheduler | None
    proactive_service: ProactiveService | None
    proactive_task: Any | None
    messages: tuple[str, ...]
```

Then implement `load_proactive_config`, `generate_cron_message`, `deliver_cron_message`, and `build_background_runtime_services`.

- [x] **Step 2: Refactor bootstrap imports and helpers**

In `server/bootstrap.py`, remove `CronScheduler`, `ProactiveService`, `_cron_generate_message`, `_cron_deliver_message`, and `_load_proactive_config`.

Add:

```python
from server.background_runtime import build_background_runtime_services
```

- [x] **Step 3: Refactor startup background assembly**

Replace the inline cron/proactive `if context.llm_client and session_manager:` block with:

```python
    background_runtime = build_background_runtime_services(
        base_dir=base_dir,
        llm_client=context.llm_client,
        persona_loader=context.persona_loader,
        memory_store=memory_store,
        session_manager=session_manager,
        cron_skills=cron_skills,
        persona_ids=list(personas.keys()),
        state_store=state_store,
        evermemos=evermemos,
        ws_connections=context.ws_registry.session_connections,
        instance_id=INSTANCE_ID,
        proactive_interval_seconds=PROACTIVE_INTERVAL_SECONDS,
    )
    context.cron_scheduler = background_runtime.cron_scheduler
    context.proactive_service = background_runtime.proactive_service
    context.proactive_task = background_runtime.proactive_task
    for message in background_runtime.messages:
        print(message)
```

- [x] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_background_runtime.py tests/test_server_bootstrap.py tests/test_proactive_delivery.py tests/test_proactive_ws_push.py tests/test_security_regressions.py::WebSocketDemoProactiveServiceRegressionTests::test_forced_proactive_is_reprocessed_and_delivered_as_segments -v
```

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-background-runtime-assembly.md`

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
git add docs/superpowers/specs/2026-07-06-background-runtime-assembly-design.md docs/superpowers/plans/2026-07-06-background-runtime-assembly.md server/background_runtime.py server/bootstrap.py tests/test_background_runtime.py tests/test_server_bootstrap.py
git commit -m "refactor: extract background runtime assembly"
git push origin main
```
