# Bootstrap Context Typing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move OpenHer service startup/shutdown wiring out of `main.py` and make `AppContext` expose typed service attributes.

**Architecture:** Add `server/bootstrap.py` as the runtime service assembler used by FastAPI lifespan. Keep `main.py` as a thin application entry point and compatibility wrapper while route handlers continue to use `request.app.state.openher`. Tighten `AppContext` with concrete optional service types so routes and startup wiring are easier to reason about.

**Tech Stack:** FastAPI lifespan, dataclasses, pytest, pyright, existing OpenHer server services.

---

### Task 1: Bootstrap Module Boundary

**Files:**
- Create: `server/bootstrap.py`
- Modify: `main.py`
- Test: `tests/test_server_bootstrap.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_bootstrap_module_exports_runtime_hooks():
    import server.bootstrap as bootstrap

    assert hasattr(bootstrap, "startup")
    assert hasattr(bootstrap, "shutdown")
    assert hasattr(bootstrap, "sync_legacy_globals")


def test_main_delegates_lifespan_to_bootstrap_module():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "from server import bootstrap" in source
    assert "await bootstrap.startup(openher_context)" in source
    assert "await bootstrap.shutdown(openher_context)" in source
    assert "def startup(" not in source
    assert "def shutdown(" not in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_server_bootstrap.py -q`

Expected: FAIL because `server.bootstrap` does not exist and `main.py` still owns startup/shutdown.

- [ ] **Step 3: Move startup/shutdown implementation**

Create `server/bootstrap.py` with:
- `async def startup(context: AppContext) -> None`
- `async def shutdown(context: AppContext) -> None`
- `def sync_legacy_globals(context: AppContext, module_globals: dict[str, object]) -> None`

Move the service creation and shutdown logic from `main.py` into those functions. Keep compatibility globals in `main.py`, and call `bootstrap.sync_legacy_globals(openher_context, globals())` after startup.

- [ ] **Step 4: Run bootstrap and server tests**

Run: `.venv/bin/python -m pytest tests/test_server_bootstrap.py tests/test_server_context.py tests/test_server_routes.py -q`

Expected: PASS.

### Task 2: Typed AppContext

**Files:**
- Modify: `server/context.py`
- Modify: `server/bootstrap.py`
- Test: `tests/test_server_context.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_app_context_annotations_are_not_any_for_core_services():
    from typing import Any, get_type_hints
    from server.context import AppContext

    hints = get_type_hints(AppContext)
    for field_name in ("session_manager", "chat_log_store", "memory_store", "proactive_service"):
        assert hints[field_name] is not Any
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_server_context.py::test_app_context_annotations_are_not_any_for_core_services -q`

Expected: FAIL because core fields are currently annotated as `Any`.

- [ ] **Step 3: Type the context fields**

Use optional concrete types for runtime services:

```python
persona_loader: PersonaLoader | None = None
llm_client: LLMClient | None = None
tts_engine: TTSEngine | None = None
session_manager: SessionManager | None = None
proactive_service: ProactiveService | None = None
```

For services that are difficult to import without cycles, use `TYPE_CHECKING` imports and string annotations.

- [ ] **Step 4: Run context and route tests**

Run: `.venv/bin/python -m pytest tests/test_server_context.py tests/test_server_routes.py -q`

Expected: PASS.

### Task 3: Verification

**Files:**
- Modify: no production files unless verification reveals a regression.

- [ ] **Step 1: Run full verification**

Run:

```bash
.venv/bin/python -m pytest tests/ -v
.venv/bin/pyright
.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py
git diff --check
```

Expected: pytest passes with one skipped external-server WebSocket test, pyright reports 0 errors, compileall exits 0, and diff check is clean.

- [ ] **Step 2: Run server smoke**

Run `PORT=8000 ./run.sh`, call `/api/status`, connect to `/ws/chat`, send `demo_presets`, then stop the server.

Expected: HTTP status returns running metadata, WebSocket returns `demo_presets`, and port 8000 is released after shutdown.
