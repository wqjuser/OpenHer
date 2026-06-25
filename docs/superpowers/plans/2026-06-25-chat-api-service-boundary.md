# Chat API Service Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `/api/chat` turn processing out of the FastAPI route into a focused, testable REST chat service.

**Architecture:** Add `server/chat_api_service.py` with `ChatApiService`, a response dataclass, and small domain exceptions. `server/routes/chat.py` will keep HTTP request handling and status-code mapping while delegating session creation, `agent.chat()`, agent persistence, chat-log writes, and response assembly to the service. `AppContext` and bootstrap will expose a configured service while tests can still fall back to constructing the service from context dependencies.

**Tech Stack:** Python 3.11+, FastAPI, pytest, existing `ChatRequest` schema and `SessionManagerService` protocol.

---

### Task 1: Lock REST Chat Service Behavior With Failing Tests

**Files:**
- Create: `tests/test_chat_api_service.py`
- Verify: `server/routes/chat.py`
- Verify: `server/context.py`
- Verify: `server/bootstrap.py`

- [x] **Step 1: Write successful chat service behavior test**

Create fake session manager, agent, and chat log store. The fake agent returns:

```python
{
    "reply": "你好",
    "modality": "文字",
    "image_path": "/tmp/selfie/luna.png",
}
```

The fake status is:

```python
{"temperature": 0.42, "mood": "curious"}
```

Call:

```python
result = await service.chat(ChatRequest(
    message="hi",
    persona_id="luna",
    session_id=None,
    user_name="Codex",
    client_id="client-1",
))
```

Assert:
- session manager receives `get_or_create(None, "luna", "Codex", "client-1")`;
- agent receives `chat("hi")`;
- session manager persists the agent;
- chat log store saves one turn with `client_id`, `persona_id`, user message, agent reply, and modality;
- `result.to_response()` returns `session_id`, `response`, `modality`, basename-based `image_url`, and status fields.

- [x] **Step 2: Write provider failure behavior test**

Use an agent whose `chat()` raises `RuntimeError("provider unavailable")`. Assert `ChatApiProviderError` is raised and `persist_agent()` is not called.

- [x] **Step 3: Write route and bootstrap structural tests**

Assert `server/routes/chat.py` imports `ChatApiService` domain exceptions, and the `chat_api()` function body no longer contains direct calls to:
- `get_or_create(`
- `agent.chat(`
- `persist_agent(`
- `save_turn(`
- `os.path.basename`

Assert `server/context.py` exposes a typed `chat_api_service` field and `server/bootstrap.py` constructs `ChatApiService`.

- [x] **Step 4: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_chat_api_service.py -q`

Expected: FAIL because `server.chat_api_service` does not exist and the route still owns chat turn behavior.

### Task 2: Add ChatApiService

**Files:**
- Create: `server/chat_api_service.py`
- Test: `tests/test_chat_api_service.py`

- [x] **Step 1: Implement response dataclass**

Create:

```python
@dataclass(frozen=True)
class ChatApiResult:
    session_id: str
    response: str
    modality: str
    image_url: Optional[str]
    status: dict[str, Any]

    def to_response(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "response": self.response,
            "modality": self.modality,
            "image_url": self.image_url,
            **self.status,
        }
```

- [x] **Step 2: Implement domain exceptions**

Create:

```python
class ChatApiServiceUnavailable(RuntimeError): ...
class ChatApiPersonaNotFound(ValueError): ...
class ChatApiProviderError(RuntimeError):
    def __init__(self, original: Exception) -> None:
        super().__init__(str(original))
        self.original = original
```

- [x] **Step 3: Implement `ChatApiService.chat()`**

The constructor accepts:

```python
session_manager: Any
chat_log_store: Any = None
```

The `chat()` method should:
- raise `ChatApiServiceUnavailable` when `session_manager` is missing;
- call `session_manager.get_or_create(req.session_id, req.persona_id, req.user_name, req.client_id)`;
- convert `ValueError` into `ChatApiPersonaNotFound`;
- call `await agent.chat(req.message)`;
- convert provider exceptions into `ChatApiProviderError`;
- call `agent.get_status()`;
- call `session_manager.persist_agent(agent)`;
- save the display chat turn when `chat_log_store` and `req.client_id` exist;
- continue when chat-log saving fails, preserving existing non-fatal behavior;
- return `ChatApiResult`.

- [x] **Step 4: Run service tests**

Run: `.venv/bin/python -m pytest tests/test_chat_api_service.py -q`

Expected: service behavior tests pass; structural tests may still fail until Task 3.

### Task 3: Delegate `/api/chat` Route And Bootstrap Service

**Files:**
- Modify: `server/routes/chat.py`
- Modify: `server/context.py`
- Modify: `server/bootstrap.py`
- Test: `tests/test_chat_api_service.py`
- Test: `tests/test_server_routes.py`
- Test: `tests/test_server_context.py`
- Test: `tests/test_security_regressions.py::ExternalEndpointErrorTests`

- [x] **Step 1: Add service to app context**

Import `ChatApiService` in `server/context.py` and add:

```python
chat_api_service: ChatApiService | None = None
```

- [x] **Step 2: Build service during startup**

Import `ChatApiService` in `server/bootstrap.py` and after `context.session_manager` and `context.chat_log_store` are initialized, set:

```python
context.chat_api_service = ChatApiService(
    session_manager=context.session_manager,
    chat_log_store=context.chat_log_store,
)
```

- [x] **Step 3: Thin the route**

In `server/routes/chat.py`, import the service exceptions and use:

```python
service = ctx.chat_api_service or ChatApiService(
    session_manager=ctx.session_manager,
    chat_log_store=ctx.chat_log_store,
)
```

Map:
- `ChatApiServiceUnavailable` to HTTP 503;
- `ChatApiPersonaNotFound` to HTTP 404;
- `ChatApiProviderError` to HTTP 502 using `external_error_detail("Chat provider failed", e.original)`.

Return:

```python
return result.to_response()
```

- [x] **Step 4: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_chat_api_service.py tests/test_server_routes.py tests/test_server_context.py tests/test_security_regressions.py::ExternalEndpointErrorTests -q`

Expected: all selected tests pass.

### Task 4: Full Verification And Release

**Files:**
- Verify: `server/chat_api_service.py`
- Verify: `server/routes/chat.py`
- Verify: `server/context.py`
- Verify: `server/bootstrap.py`
- Verify: `tests/test_chat_api_service.py`

- [x] **Step 1: Run static and compile checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

Run: `.venv/bin/python -m py_compile server/chat_api_service.py server/routes/chat.py server/context.py server/bootstrap.py tests/test_chat_api_service.py`

Expected: exit code 0.

- [x] **Step 2: Run full tests**

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: full suite passes with the known skipped WebSocket integration test unchanged.

- [x] **Step 3: Run repository hygiene checks**

Run: `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0.

- [x] **Step 4: Run service smoke**

Start: `PORT=8781 ./run.sh`

Check:
- `GET /api/status`
- `POST /api/chat`
- WebSocket `demo_presets`

Expected: backend starts and the REST chat path still returns a normal response through the configured provider.

- [x] **Step 5: Commit, merge, and push**

Run:

```bash
git add server/chat_api_service.py server/routes/chat.py server/context.py server/bootstrap.py tests/test_chat_api_service.py docs/superpowers/plans/2026-06-25-chat-api-service-boundary.md
git commit -m "refactor: extract chat api service boundary"
git switch main
git pull --ff-only
git merge --no-ff codex/chat-api-service-boundary -m "merge: chat api service boundary"
git push origin main
```

### Self-Review

- Spec coverage: The plan extracts only `/api/chat` POST turn behavior and leaves status/history read routes unchanged.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `ChatApiService`, `ChatApiResult`, and service exception names are consistent across tests, route, context, and bootstrap.
