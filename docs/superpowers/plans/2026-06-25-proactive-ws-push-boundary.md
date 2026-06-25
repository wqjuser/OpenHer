# Proactive WebSocket Push Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract proactive WebSocket message formatting and segmented delivery into one reusable service shared by outbox delivery and demo proactive delivery.

**Architecture:** Add `server/proactive_ws_push.py` with a small immutable payload type and `ProactiveWebSocketPushService`. `server/proactive_delivery.py` keeps outbox state transitions and engine reprocessing, while `server/websocket_demo.py` keeps demo orchestration; both delegate WebSocket protocol details to the shared push service.

**Tech Stack:** Python 3.11+, pytest, existing Starlette-compatible `send_json()` WebSocket protocol.

---

### Task 1: Lock Shared Push Protocol With Failing Tests

**Files:**
- Create: `tests/test_proactive_ws_push.py`
- Verify: `server/proactive_delivery.py`
- Verify: `server/websocket_demo.py`

- [x] **Step 1: Write push service behavior tests**

Create a fake WebSocket that records `send_json()` calls and a fake sleep coroutine that records delays. The segmented test imports:

```python
from server.proactive_ws_push import ProactivePushPayload, ProactiveWebSocketPushService
```

It sends:

```python
payload = ProactivePushPayload(
    reply="aggregate reply",
    modality="文字",
    segments=["第一句", "第二句"],
    delays_ms=[0, 1],
    drive="connection",
    persona="Luna",
)
```

It asserts the messages are `chat_end`, `chat_start`, `chat_end`, with `proactive=True`, `drive`, and `persona`, and that delay `1ms` is clamped to `0.3` seconds.

The single-message test sends:

```python
payload = ProactivePushPayload(reply="hello", modality="文字")
```

It asserts the emitted message is exactly:

```python
{"type": "proactive", "content": "hello", "modality": "文字"}
```

- [x] **Step 2: Write delegation structural tests**

Assert `server/proactive_delivery.py` imports `ProactiveWebSocketPushService` and `ProactivePushPayload`, calls `self.push_service.push(...)`, and no longer defines `_send_segments()`.

Assert the `WebSocketDemoProactiveService` class imports and uses the shared push service and its class body no longer calls `send_json()` directly.

- [x] **Step 3: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_proactive_ws_push.py -q`

Expected: FAIL because `server.proactive_ws_push` does not exist and both existing services still own push formatting.

### Task 2: Add ProactiveWebSocketPushService

**Files:**
- Create: `server/proactive_ws_push.py`
- Test: `tests/test_proactive_ws_push.py`

- [x] **Step 1: Implement payload dataclass**

Create:

```python
@dataclass(frozen=True)
class ProactivePushPayload:
    reply: str
    modality: str
    segments: Any = None
    delays_ms: Any = None
    drive: Optional[str] = None
    persona: Optional[str] = None
```

- [x] **Step 2: Implement push service**

Create `ProactiveWebSocketPushService` with:

```python
async def push(
    self,
    websocket: Any,
    *,
    session_id: Optional[str],
    payload: ProactivePushPayload,
) -> None:
```

If `payload.segments` has more than one item, send the segment protocol. For segment indexes greater than zero, first send `{"type": "chat_start", "session_id": session_id}`, then sleep for `max(delay_ms, 300) / 1000.0`, then send `chat_end`. Otherwise send the single `proactive` message. Include optional `drive` and `persona` keys only when they are not `None`.

- [x] **Step 3: Run push service tests**

Run: `.venv/bin/python -m pytest tests/test_proactive_ws_push.py -q`

Expected: push service behavior tests pass; delegation tests may still fail until Task 3.

### Task 3: Delegate Existing Proactive Paths

**Files:**
- Modify: `server/proactive_delivery.py`
- Modify: `server/websocket_demo.py`
- Test: `tests/test_proactive_ws_push.py`
- Test: `tests/test_proactive_delivery.py`
- Test: `tests/test_security_regressions.py::WebSocketDemoProactiveServiceRegressionTests`
- Test: `tests/test_websocket_demo_commands.py`

- [x] **Step 1: Inject push service into outbox delivery**

Add an optional constructor dependency:

```python
push_service: Optional[ProactiveWebSocketPushService] = None
```

Store:

```python
self.push_service = push_service or ProactiveWebSocketPushService(sleep=sleep)
```

Replace direct segment/single send logic with:

```python
await self.push_service.push(
    ws,
    session_id=session_id,
    payload=ProactivePushPayload(
        reply=reply,
        modality=modality,
        segments=segments,
        delays_ms=delays_ms,
        drive=drive_id,
        persona=agent.persona.name,
    ),
)
```

- [x] **Step 2: Inject push service into demo proactive delivery**

Keep the existing `sleep` constructor argument for tests and callers, and add:

```python
push_service: Optional[ProactiveWebSocketPushService] = None
```

Store:

```python
self.push_service = push_service or ProactiveWebSocketPushService(sleep=sleep)
```

Replace direct segment/single send logic in `deliver_forced_proactive()` with `self.push_service.push(...)`.

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_proactive_ws_push.py tests/test_proactive_delivery.py tests/test_security_regressions.py::WebSocketDemoProactiveServiceRegressionTests tests/test_websocket_demo_commands.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification And Release

**Files:**
- Verify: `server/proactive_ws_push.py`
- Verify: `server/proactive_delivery.py`
- Verify: `server/websocket_demo.py`
- Verify: `tests/test_proactive_ws_push.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile checks**

Run: `.venv/bin/python -m py_compile server/proactive_ws_push.py server/proactive_delivery.py server/websocket_demo.py tests/test_proactive_ws_push.py`

Expected: exit code 0.

Run: `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`

Expected: exit code 0.

- [x] **Step 3: Run full tests**

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: full suite passes with the known skipped WebSocket integration test unchanged.

- [x] **Step 4: Run service smoke**

Start: `PORT=8780 ./run.sh`

Check:
- `GET /api/status`
- WebSocket `demo_presets`
- `POST /api/chat`

Expected: backend starts, DeepSeek/EverMemOS status is reported according to local config, and core HTTP/WebSocket paths respond.

- [x] **Step 5: Commit, merge, and push**

Run:

```bash
git add server/proactive_ws_push.py server/proactive_delivery.py server/websocket_demo.py tests/test_proactive_ws_push.py docs/superpowers/plans/2026-06-25-proactive-ws-push-boundary.md
git commit -m "refactor: extract proactive websocket push boundary"
git switch main
git pull --ff-only
git merge --no-ff codex/proactive-ws-push-boundary -m "merge: proactive websocket push boundary"
git push origin main
```

### Self-Review

- Spec coverage: The plan extracts only shared proactive WebSocket push formatting and preserves existing outbox/demo orchestration responsibilities.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `ProactivePushPayload`, `ProactiveWebSocketPushService`, and `push()` are named consistently across tests and implementation.
