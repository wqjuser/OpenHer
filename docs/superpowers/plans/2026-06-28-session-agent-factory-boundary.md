# Session Agent Factory Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split ChatAgent construction and state hydration out of `SessionManager` so session lifecycle and agent creation are independently testable.

**Architecture:** `SessionAgentFactory` will own persona lookup, `ChatAgent` construction, persisted state hydration, proactive metadata restore, and first-run pre-warm. `SessionManager` will retain session id reuse, client/persona reuse, TTL cleanup, persistence, and removal. `server.bootstrap` wires both services into `AppContext`.

**Tech Stack:** Python 3.11+, FastAPI runtime services, pytest, pyright.

---

### Task 1: Red Tests For Factory Boundary

**Files:**
- Create: `tests/test_session_agent_factory.py`
- Test: `tests/test_session_agent_factory.py`

- [x] **Step 1: Write failing tests**

Add tests that import `SessionAgentFactory`, inject a fake ChatAgent constructor, verify new-agent creation, verify persisted state hydration, verify missing persona errors, and inspect source boundaries so `SessionManager` no longer owns `ChatAgent(` construction or `state_store.load_session(...)`.

- [x] **Step 2: Run tests and verify expected failure**

Run: `.venv/bin/python -m pytest tests/test_session_agent_factory.py -q`

Expected: FAIL because `server.session_agent_factory` does not exist yet.

### Task 2: Extract Agent Creation Service

**Files:**
- Create: `server/session_agent_factory.py`
- Modify: `server/session_manager.py`
- Test: `tests/test_session_agent_factory.py`

- [x] **Step 1: Implement `SessionAgentFactory`**

Create a focused service with constructor dependencies for persona loader, LLM client, skill engines, memory store, state store, EverMemOS, genome data dir, and injectable `agent_factory`.

- [x] **Step 2: Move hydration behavior**

Move the existing persona lookup, stable user id selection, genome seed calculation, `ChatAgent` construction, `_client_id` assignment, `state_store.load_session`, proactive metadata restore, and `pre_warm()` branch from `SessionManager.get_or_create()` into `SessionAgentFactory.create(...)`.

- [x] **Step 3: Slim `SessionManager`**

Change `SessionManager.__init__` to accept `agent_factory`, `state_store`, `evermemos`, and `ttl_seconds`. Keep `sessions`, `active_count`, `get_entry`, `persist_agent`, `persist_all`, `cleanup_expired_sessions`, `get_or_create`, and `remove` as lifecycle operations.

- [x] **Step 4: Run targeted factory tests**

Run: `.venv/bin/python -m pytest tests/test_session_agent_factory.py -q`

Expected: PASS.

### Task 3: Wire Bootstrap And Context

**Files:**
- Modify: `server/bootstrap.py`
- Modify: `server/context.py`
- Modify: `main.py`
- Test: `tests/test_session_agent_factory.py`
- Test: `tests/test_server_bootstrap.py`

- [x] **Step 1: Add context field**

Add `session_agent_factory: SessionAgentFactory | None = None` to `AppContext`.

- [x] **Step 2: Assemble factory before manager**

Construct `SessionAgentFactory(...)` in `startup()`, store it on context, and pass it into `SessionManager(agent_factory=...)`.

- [x] **Step 3: Expose legacy global**

Add `"session_agent_factory": context.session_agent_factory` to `sync_legacy_globals(...)` so legacy module globals stay aligned with context.

- [x] **Step 4: Run bootstrap/context tests**

Run: `.venv/bin/python -m pytest tests/test_server_context.py tests/test_server_bootstrap.py -q`

Expected: PASS.

### Task 4: Regression And Runtime Verification

**Files:**
- Modify: `tests/test_security_regressions.py`
- Test: full suite

- [x] **Step 1: Update reuse regression**

Update the existing session reuse regression to inject `SessionAgentFactory(..., agent_factory=FakeAgent)` instead of patching `server.session_manager.ChatAgent`.

- [x] **Step 2: Run focused impacted tests**

Run: `.venv/bin/python -m pytest tests/test_session_agent_factory.py tests/test_security_regressions.py tests/test_chat_api_service.py tests/test_websocket_chat_service.py tests/test_websocket_route_service.py tests/test_server_context.py tests/test_server_bootstrap.py -q`

Expected: PASS.

- [x] **Step 3: Run full verification**

Run:
- `.venv/bin/pyright`
- `.venv/bin/python -m py_compile server/session_agent_factory.py server/session_manager.py server/context.py server/bootstrap.py tests/test_session_agent_factory.py`
- `.venv/bin/python -m pytest tests/ -q`
- `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`
- `git diff --check`

Expected: all commands exit 0.

- [x] **Step 4: Run server smoke**

Run the backend on an unused local port and verify `/api/status`, `/api/chat`, and `/api/session/{session_id}/status` still work with the configured provider.

### Task 5: Commit, Merge, Push

**Files:**
- Stage all files touched by this plan.

- [x] **Step 1: Commit branch**

Run:
```bash
git add main.py server/session_agent_factory.py server/session_manager.py server/context.py server/bootstrap.py tests/test_session_agent_factory.py tests/test_security_regressions.py docs/superpowers/plans/2026-06-28-session-agent-factory-boundary.md
git commit -m "refactor: extract session agent factory"
```

- [ ] **Step 2: Merge to main and push**

Run:
```bash
git switch main
git pull --ff-only
git merge --no-ff codex/session-agent-factory-boundary -m "merge: session agent factory boundary"
git push origin main
```

Expected: `main` contains the merge commit and is pushed to `origin/main`.
