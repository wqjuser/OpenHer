# Legacy Compatibility Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move legacy global alias and helper-wrapper logic out of `main.py` and `server/bootstrap.py`.

**Architecture:** Add `server/legacy_compat.py` with initial globals, runtime synchronization, and a context-bound helper adapter. `main.py` keeps legacy symbol names by binding them to the adapter, while bootstrap stops owning compatibility synchronization.

**Tech Stack:** Python 3.11+, dataclasses, pytest, pyright, FastAPI lifespan, existing `AppContext`.

## Global Constraints

- Preserve existing `main.py` legacy symbol names.
- Do not change startup, shutdown, route, session, or proactive service behavior.
- Keep tests mocked and local; no provider, memory, or network calls.

---

### Task 1: Add Legacy Compatibility Boundary Tests

**Files:**
- Create: `tests/test_legacy_compat.py`
- Modify: `tests/test_server_bootstrap.py`

**Interfaces:**
- Consumes: `AppContext` from `server.context`.
- Produces: expected `server.legacy_compat.initial_legacy_globals`, `server.legacy_compat.sync_legacy_globals`, and `server.legacy_compat.LegacyCompatibility`.

- [x] **Step 1: Write failing tests for initial and synced legacy globals**

Create `tests/test_legacy_compat.py` with assertions that `initial_legacy_globals(context)` exposes the expected startup defaults and context-bound WebSocket/demo values, and that `sync_legacy_globals(context, module_globals)` updates service aliases.

- [x] **Step 2: Write failing tests for legacy helper delegation**

Append tests that instantiate `LegacyCompatibility(context)` with fake proactive and session services and assert each helper delegates to the underlying context service.

- [x] **Step 3: Write failing tests for unavailable helper errors**

Append tests that assert `get_or_create_session(...)` raises `RuntimeError("Session manager is not initialized")` and `deliver_proactive_msg(...)` raises `RuntimeError("Proactive service is not initialized")` when those services are missing.

- [x] **Step 4: Update source boundary tests**

Update `tests/test_server_bootstrap.py` to assert `bootstrap` no longer exports `sync_legacy_globals`, `main.py` imports from `server.legacy_compat`, and lifespan calls `sync_legacy_globals(context, globals())`.

- [x] **Step 5: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_legacy_compat.py tests/test_server_bootstrap.py::test_bootstrap_module_exports_runtime_hooks tests/test_server_bootstrap.py::test_main_delegates_lifespan_to_bootstrap_module -v
```

Expected: FAIL because `server.legacy_compat` does not exist and main/bootstrap still own compatibility logic.

### Task 2: Implement Legacy Compatibility Module

**Files:**
- Create: `server/legacy_compat.py`
- Modify: `main.py`
- Modify: `server/bootstrap.py`

**Interfaces:**
- Consumes: `AppContext`.
- Produces: `initial_legacy_globals(context) -> dict[str, object]`, `sync_legacy_globals(context, module_globals) -> None`, and `LegacyCompatibility` methods bound by `main.py`.

- [x] **Step 1: Add `server/legacy_compat.py`**

Create a module with `initial_legacy_globals`, `sync_legacy_globals`, and `LegacyCompatibility`.

- [x] **Step 2: Refactor `main.py` legacy section**

Replace direct legacy global declarations and helper bodies with:

```python
from server.legacy_compat import LegacyCompatibility, initial_legacy_globals, sync_legacy_globals

globals().update(initial_legacy_globals(openher_context))
legacy_helpers = LegacyCompatibility(openher_context)
_proactive_heartbeat_loop = legacy_helpers.proactive_heartbeat_loop
_proactive_sweep = legacy_helpers.proactive_sweep
_deliver_proactive_msg = legacy_helpers.deliver_proactive_msg
_persist_agent = legacy_helpers.persist_agent
_cleanup_expired_sessions = legacy_helpers.cleanup_expired_sessions
get_or_create_session = legacy_helpers.get_or_create_session
remove_session = legacy_helpers.remove_session
```

- [x] **Step 3: Refactor bootstrap ownership**

Remove `sync_legacy_globals(...)` from `server/bootstrap.py`.

- [x] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_legacy_compat.py tests/test_server_bootstrap.py tests/test_security_regressions.py::FastAPILifespanRegressionTests::test_server_uses_lifespan_instead_of_deprecated_on_event_hooks -v
```

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-07-legacy-compat-boundary.md`

**Interfaces:**
- Consumes: completed implementation from Tasks 1 and 2.
- Produces: committed and pushed branch state on `main`.

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
git add docs/superpowers/specs/2026-07-07-legacy-compat-boundary-design.md docs/superpowers/plans/2026-07-07-legacy-compat-boundary.md server/legacy_compat.py main.py server/bootstrap.py tests/test_legacy_compat.py tests/test_server_bootstrap.py
git commit -m "refactor: extract legacy compatibility boundary"
git push origin main
```
