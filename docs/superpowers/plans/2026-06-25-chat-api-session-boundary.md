# Chat API Session Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move REST chat session status and chat history lookup rules out of FastAPI routes into `ChatApiService`.

**Architecture:** Extend the existing `server/chat_api_service.py` boundary instead of adding another chat service. The route module will keep request parsing, query validation, HTTP exception mapping, and response serialization while delegating session status lookup and display history lookup to the service. This keeps chat REST behavior in one injectable service backed by `session_manager` and `chat_log_store`.

**Tech Stack:** Python 3.11+, FastAPI, pytest, existing `ChatApiService`, `SessionManager`, and `ChatLogStore` interfaces.

---

### Task 1: Lock Remaining Chat REST Behavior With Failing Tests

**Files:**
- Modify: `tests/test_chat_api_service.py`
- Verify: `server/routes/chat.py`

- [x] **Step 1: Write session status service test**

Add a fake session manager with:

```python
def get_entry(self, session_id: str) -> tuple[Any, float] | None:
    return (agent, 123.0) if session_id == "session-1" else None
```

Assert:
- `service.session_status("session-1")` returns `agent.get_status()`;
- missing sessions raise `ChatApiSessionNotFound("Session not found")`;
- missing session manager raises `ChatApiServiceUnavailable("Session manager is not initialized")`.

- [x] **Step 2: Write chat history service test**

Add a fake chat log store with `load_messages()` and `count_messages()` call recorders.

Assert:
- `service.chat_history("luna", client_id="client-1", limit=25, before_id=42)` returns `{"messages": messages, "total": total}`;
- the fake store receives `(client_id, persona_id, limit, before_id)`;
- when no chat log store is configured, the service returns `{"messages": [], "total": 0}`.

- [x] **Step 3: Write route delegation test**

Extend `test_chat_route_delegates_post_chat_turn_to_service_boundary()` or add a sibling test that asserts:
- `session_status` route body calls `service.session_status(session_id)`;
- `get_chat_history` route body calls `service.chat_history(...)`;
- `server/routes/chat.py` no longer directly calls `ctx.session_manager.get_entry`, `agent.get_status()`, `ctx.chat_log_store.load_messages`, or `ctx.chat_log_store.count_messages`.

- [x] **Step 4: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_chat_api_service.py -q`

Expected: FAIL because `ChatApiService` does not yet expose `session_status()`, `chat_history()`, or `ChatApiSessionNotFound`, and routes still own those lookup rules.

### Task 2: Extend ChatApiService

**Files:**
- Modify: `server/chat_api_service.py`
- Test: `tests/test_chat_api_service.py`

- [x] **Step 1: Add session exception**

Create:

```python
class ChatApiSessionNotFound(ValueError):
    """Raised when a REST session lookup misses."""
```

- [x] **Step 2: Implement session_status**

Add:

```python
def session_status(self, session_id: str) -> dict[str, Any]:
    if not self.session_manager:
        raise ChatApiServiceUnavailable("Session manager is not initialized")
    entry = self.session_manager.get_entry(session_id)
    if not entry:
        raise ChatApiSessionNotFound("Session not found")
    agent, _ = entry
    return agent.get_status()
```

- [x] **Step 3: Implement chat_history**

Add:

```python
def chat_history(
    self,
    *,
    persona_id: str,
    client_id: str,
    limit: int,
    before_id: int | None,
) -> dict[str, Any]:
    if not self.chat_log_store:
        return {"messages": [], "total": 0}
    messages = self.chat_log_store.load_messages(client_id, persona_id, limit, before_id)
    total = self.chat_log_store.count_messages(client_id, persona_id)
    return {"messages": messages, "total": total}
```

- [x] **Step 4: Run service tests**

Run: `.venv/bin/python -m pytest tests/test_chat_api_service.py -q`

Expected: service behavior tests pass; route delegation tests may still fail until Task 3.

### Task 3: Thin Chat Routes

**Files:**
- Modify: `server/routes/chat.py`
- Test: `tests/test_chat_api_service.py`
- Test: `tests/test_server_routes.py`
- Test: `tests/test_security_regressions.py`

- [x] **Step 1: Add a route service helper**

Create a private helper:

```python
def _chat_service(request: Request) -> ChatApiService:
    ctx = context_from_request(request)
    return ctx.chat_api_service or ChatApiService(
        session_manager=ctx.session_manager,
        chat_log_store=ctx.chat_log_store,
    )
```

- [x] **Step 2: Use helper in chat_api**

Replace the inline `ctx = context_from_request(...)` and service construction with:

```python
service = _chat_service(request)
```

- [x] **Step 3: Delegate session_status**

Use:

```python
try:
    return service.session_status(session_id)
except ChatApiServiceUnavailable as e:
    raise HTTPException(status_code=503, detail=str(e)) from e
except ChatApiSessionNotFound as e:
    raise HTTPException(status_code=404, detail=str(e)) from e
```

- [x] **Step 4: Delegate get_chat_history**

Use:

```python
return service.chat_history(
    persona_id=persona_id,
    client_id=client_id,
    limit=limit,
    before_id=before_id,
)
```

- [x] **Step 5: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_chat_api_service.py tests/test_server_routes.py tests/test_security_regressions.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification And Release

**Files:**
- Verify: `server/chat_api_service.py`
- Verify: `server/routes/chat.py`
- Verify: `tests/test_chat_api_service.py`

- [x] **Step 1: Run static and compile checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

Run: `.venv/bin/python -m py_compile server/chat_api_service.py server/routes/chat.py tests/test_chat_api_service.py`

Expected: exit code 0.

- [x] **Step 2: Run full tests**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: full suite passes with the known skipped WebSocket integration test unchanged.

- [x] **Step 3: Run repository hygiene checks**

Run: `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0.

- [x] **Step 4: Run service smoke**

Start: `PORT=8783 ./run.sh`

Check:
- `GET /api/status`;
- `POST /api/chat`;
- `GET /api/session/{session_id}/status` using the session id from chat;
- `GET /api/chat/history/luna?client_id=<client-id>`;
- WebSocket `demo_presets`.

Expected: backend starts and existing chat REST, history, session status, and websocket paths still run normally.

- [x] **Step 5: Commit, merge, and push**

Run:

```bash
git add server/chat_api_service.py server/routes/chat.py tests/test_chat_api_service.py docs/superpowers/plans/2026-06-25-chat-api-session-boundary.md
git commit -m "refactor: move chat session lookups into service"
git switch main
git pull --ff-only
git merge --no-ff codex/chat-api-session-boundary -m "merge: chat api session boundary"
git push origin main
```

### Self-Review

- Spec coverage: The plan extends the existing chat REST service for session status and history without changing public endpoints.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `ChatApiSessionNotFound`, `session_status`, and `chat_history` names are consistent across service, routes, and tests.
