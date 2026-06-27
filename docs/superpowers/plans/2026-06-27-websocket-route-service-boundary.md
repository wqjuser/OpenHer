# WebSocket Route Service Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move WebSocket connection-loop orchestration out of `server/routes/websocket.py` into a focused service boundary.

**Architecture:** Add `server/websocket_route_service.py` with `WebSocketRouteService`, responsible for JSON parsing, client registration, debounce buffering, command dispatch, and connection cleanup after the FastAPI route accepts the socket. The route will keep only token validation, accept/close, fallback service construction, and delegation. Existing downstream services (`WebSocketChatTurnService`, `WebSocketTTSService`, `WebSocketPersonaSwitchService`, `WebSocketDemoCommandService`) remain unchanged and are injected into the new route service.

**Tech Stack:** Python 3.11+, FastAPI/Starlette WebSocket, pytest, existing WebSocket service classes and registry.

---

### Task 1: Lock WebSocket Route Service Behavior With Failing Tests

**Files:**
- Create: `tests/test_websocket_route_service.py`
- Verify: `server/routes/websocket.py`
- Verify: `server/context.py`
- Verify: `server/bootstrap.py`

- [x] **Step 1: Write status and invalid JSON behavior test**

Create a fake WebSocket whose `receive_text()` yields:

```python
[
    "not-json",
    '{"type":"status","client_id":"client-1"}',
]
```

and then raises `WebSocketDisconnect`.

Create a fake agent with `get_status()` returning `{"temperature": 0.2}` and pass it as `initial_agent` to `service.handle_connection(...)`.

Assert:
- invalid JSON sends `{"type": "error", "content": "Invalid JSON"}`;
- status sends `{"type": "status", "temperature": 0.2}`;
- the registry records `client-1`;
- cleanup unregisters the websocket.

- [x] **Step 2: Write command dispatch behavior test**

Create fake TTS, persona switch, and demo command services.

Send:

```python
{"type":"tts_request","content":"hello"}
{"type":"switch_persona","persona_id":"iris","client_id":"client-1"}
{"type":"demo_presets"}
```

Assert:
- TTS receives the current agent and content;
- persona switch receives the current session id and returns a new session/agent;
- demo command receives the updated session/agent and can update them again.

- [x] **Step 3: Write chat debounce behavior test**

Use `debounce_fallback_sec=0` and injected sleep that records delay without actually waiting.

Send two chat messages followed by a typing inactive message:

```python
{"type":"chat","content":"第一句","persona_id":"luna"}
{"type":"chat","content":"第二句","persona_id":"luna"}
{"type":"typing","active":false}
```

Assert fake chat turn service receives both messages as one buffered batch, and `session_id`/`agent` update from its return result.

- [x] **Step 4: Write route/context/bootstrap structural tests**

Assert:
- `server/routes/websocket.py` imports `WebSocketRouteService`;
- route calls `service.handle_connection(ws)`;
- route no longer directly uses `json.loads`, `asyncio.create_task`, `ctx.ws_chat_turn_service.handle_messages`, `ctx.ws_tts_service.handle_request`, `ctx.persona_switch_service.switch`, or `ctx.ws_demo_command_service.handle`;
- `server/context.py` has a typed `ws_route_service` field;
- `server/bootstrap.py` constructs `WebSocketRouteService`.

- [x] **Step 5: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_websocket_route_service.py -q`

Expected: FAIL because `server.websocket_route_service` does not exist and WebSocket routes still own connection orchestration.

### Task 2: Add WebSocketRouteService

**Files:**
- Create: `server/websocket_route_service.py`
- Test: `tests/test_websocket_route_service.py`

- [x] **Step 1: Implement constructor**

Create `WebSocketRouteService` with injected dependencies:

```python
class WebSocketRouteService:
    def __init__(
        self,
        *,
        registry: Any,
        session_manager: Any = None,
        chat_turn_service: Any = None,
        tts_service: Any = None,
        persona_switch_service: Any = None,
        demo_command_service: Any = None,
        debounce_grace_sec: float = 2.0,
        debounce_fallback_sec: float = 3.0,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        create_task: Callable[[Awaitable[Any]], asyncio.Task[Any]] = asyncio.create_task,
    ) -> None:
        ...
```

- [x] **Step 2: Implement handle_connection**

`handle_connection(websocket, initial_session_id=None, initial_agent=None)` should:
- loop over `receive_text()`;
- send invalid JSON errors;
- register `client_id` with the registry;
- buffer chat messages;
- schedule flush after fallback delay on chat messages;
- schedule flush after grace delay when typing becomes inactive;
- dispatch `tts_request`, `status`, `switch_persona`, and `demo_*` commands to injected services;
- catch `WebSocketDisconnect`;
- catch unexpected exceptions, log them, and attempt to send a `{"type":"error"}` message;
- always cancel pending debounce tasks, clear buffered messages, unregister websocket, remove the session from `session_manager`, and print the closed session.

- [x] **Step 3: Run service tests**

Run: `.venv/bin/python -m pytest tests/test_websocket_route_service.py -q`

Expected: service behavior tests pass; route/context/bootstrap structural tests may still fail until Task 3.

### Task 3: Delegate FastAPI WebSocket Route

**Files:**
- Modify: `server/routes/websocket.py`
- Modify: `server/context.py`
- Modify: `server/bootstrap.py`
- Test: `tests/test_websocket_route_service.py`
- Test: `tests/test_server_context.py`
- Test: `tests/test_server_routes.py`
- Test: `tests/test_websocket_chat_service.py`
- Test: `tests/test_websocket_demo_commands.py`

- [x] **Step 1: Add service to app context**

Import `WebSocketRouteService` in `server/context.py` and add:

```python
ws_route_service: WebSocketRouteService | None = None
```

- [x] **Step 2: Build service during startup**

Import `WebSocketRouteService` in `server/bootstrap.py` and after WebSocket dependent services are created, set:

```python
context.ws_route_service = WebSocketRouteService(
    registry=context.ws_registry,
    session_manager=context.session_manager,
    chat_turn_service=context.ws_chat_turn_service,
    tts_service=context.ws_tts_service,
    persona_switch_service=context.persona_switch_service,
    demo_command_service=context.ws_demo_command_service,
)
```

Also expose it through `sync_legacy_globals()`.

- [x] **Step 3: Thin `server/routes/websocket.py`**

Keep:
- token validation;
- `await ws.close(code=1008)`;
- `await ws.accept()`;
- fallback service construction;
- `await service.handle_connection(ws)`.

Delete route-local JSON parsing, debounce helpers, command dispatch, and cleanup.

- [x] **Step 4: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_websocket_route_service.py tests/test_server_context.py tests/test_server_routes.py tests/test_websocket_chat_service.py tests/test_websocket_demo_commands.py tests/test_security_regressions.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification And Release

**Files:**
- Verify: `server/websocket_route_service.py`
- Verify: `server/routes/websocket.py`
- Verify: `server/context.py`
- Verify: `server/bootstrap.py`
- Verify: `tests/test_websocket_route_service.py`

- [x] **Step 1: Run static and compile checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

Run: `.venv/bin/python -m py_compile server/websocket_route_service.py server/routes/websocket.py server/context.py server/bootstrap.py tests/test_websocket_route_service.py`

Expected: exit code 0.

- [x] **Step 2: Run full tests**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: full suite passes with the known skipped WebSocket integration test unchanged when no server is already running.

- [x] **Step 3: Run repository hygiene checks**

Run: `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0.

- [x] **Step 4: Run service smoke**

Start: `PORT=8783 ./run.sh`

Check:
- `GET /api/status`;
- WebSocket `demo_presets`;
- WebSocket `status` after a chat turn;
- `POST /api/chat`.

Expected: backend starts and existing WebSocket and REST chat paths still run normally.

- [x] **Step 5: Commit, merge, and push**

Run:

```bash
git add server/websocket_route_service.py server/routes/websocket.py server/context.py server/bootstrap.py tests/test_websocket_route_service.py docs/superpowers/plans/2026-06-27-websocket-route-service-boundary.md
git commit -m "refactor: extract websocket route service boundary"
git switch main
git pull --ff-only
git merge --no-ff codex/websocket-route-service-boundary -m "merge: websocket route service boundary"
git push origin main
```

### Self-Review

- Spec coverage: The plan moves route-level WebSocket orchestration into a service without changing downstream chat, TTS, persona switch, or demo services.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `WebSocketRouteService`, `handle_connection`, and `ws_route_service` names are consistent across service, route, context, bootstrap, and tests.
