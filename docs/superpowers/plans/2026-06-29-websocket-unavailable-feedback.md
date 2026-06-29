# WebSocket Unavailable Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make WebSocket chat routes report explicit service-unavailable events when LLM/session-backed runtime services are disabled.

**Architecture:** Keep the degraded startup wiring from `server/bootstrap.py` intact and localize behavior in `WebSocketRouteService`. When route dependencies are missing, the service sends a stable WebSocket error payload with `code="service_unavailable"` and does not buffer messages indefinitely or silently ignore requested operations.

**Tech Stack:** Python 3.11+, pytest/pytest-asyncio, existing WebSocket route service boundary tests.

---

### Task 1: Add Failing WebSocket Unavailable Tests

**Files:**
- Modify: `tests/test_websocket_route_service.py`

- [x] **Step 1: Add a chat-unavailable regression test**

Add an async test that constructs `WebSocketRouteService` without `chat_turn_service`, sends one `chat` message, flushes immediately with `debounce_fallback_sec=0`, and expects a WebSocket error payload:

```python
async def test_websocket_route_service_reports_unavailable_when_chat_service_missing():
    from server.websocket_route_service import WebSocketRouteService

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    websocket = FakeWebSocket([
        {"type": "chat", "content": "hi", "persona_id": "luna"},
    ])
    registry = FakeRegistry()
    service = WebSocketRouteService(
        registry=registry,
        chat_turn_service=None,
        debounce_fallback_sec=0,
        sleep=fake_sleep,
    )

    await service.handle_connection(websocket)

    assert websocket.sent == [{
        "type": "error",
        "code": "service_unavailable",
        "content": "聊天服务暂不可用，请先配置 LLM provider key",
    }]
    assert 0 in sleep_calls
    assert registry.unregister_websocket_calls == [websocket]
```

- [x] **Step 2: Add status/switch/demo unavailable coverage**

Add a second async test that sends `status`, `switch_persona`, and `demo_presets` with no agent and no LLM-backed services. It should receive three `service_unavailable` errors instead of silence:

```python
async def test_websocket_route_service_reports_unavailable_for_session_commands():
    from server.websocket_route_service import WebSocketRouteService

    websocket = FakeWebSocket([
        {"type": "status"},
        {"type": "switch_persona", "persona_id": "iris"},
        {"type": "demo_presets"},
    ])
    registry = FakeRegistry()
    service = WebSocketRouteService(registry=registry)

    await service.handle_connection(websocket)

    assert websocket.sent == [
        {
            "type": "error",
            "code": "service_unavailable",
            "content": "会话状态暂不可用，请先配置 LLM provider key",
        },
        {
            "type": "error",
            "code": "service_unavailable",
            "content": "角色切换暂不可用，请先配置 LLM provider key",
        },
        {
            "type": "error",
            "code": "service_unavailable",
            "content": "演示命令暂不可用，请先配置 LLM provider key",
        },
    ]
```

- [x] **Step 3: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_websocket_route_service.py::test_websocket_route_service_reports_unavailable_when_chat_service_missing tests/test_websocket_route_service.py::test_websocket_route_service_reports_unavailable_for_session_commands -q
```

Expected: fail because the route service currently sends no response for missing services.

### Task 2: Implement Explicit Unavailable Responses

**Files:**
- Modify: `server/websocket_route_service.py`

- [x] **Step 4: Add a focused unavailable helper**

Add a private helper on `WebSocketRouteService`:

```python
async def _send_unavailable(self, websocket: Any, content: str) -> None:
    await websocket.send_json({
        "type": "error",
        "code": "service_unavailable",
        "content": content,
    })
```

- [x] **Step 5: Use the helper for missing chat service**

In `flush_buffer()`, after copying and clearing `msg_buffer`, if `self.chat_turn_service` is missing, send:

```python
await self._send_unavailable(websocket, "聊天服务暂不可用，请先配置 LLM provider key")
return
```

Then keep the existing `handle_messages(...)` path unchanged when the service exists.

- [x] **Step 6: Use the helper for session commands**

For `status`, if there is no `agent`, send:

```python
await self._send_unavailable(websocket, "会话状态暂不可用，请先配置 LLM provider key")
```

For `switch_persona`, if `persona_switch_service` is missing, send:

```python
await self._send_unavailable(websocket, "角色切换暂不可用，请先配置 LLM provider key")
```

For `demo_` commands, if `demo_command_service` is missing, send:

```python
await self._send_unavailable(websocket, "演示命令暂不可用，请先配置 LLM provider key")
```

- [x] **Step 7: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_websocket_route_service.py -q
```

Expected: all WebSocket route service boundary tests pass.

### Task 3: Verify And Ship

**Files:**
- Verify: full backend checks
- Verify: live provider smoke
- Verify: macOS Swift package build

- [x] **Step 8: Run full checks**

Run:

```bash
source .venv/bin/activate && make check
```

- [x] **Step 9: Run integration smoke and desktop build**

Run:

```bash
source .venv/bin/activate && make integration-smoke
cd desktop/OpenHer && swift build
```

- [x] **Step 10: Commit, merge to main, and push**

Commit message:

```bash
git commit -m "fix: report websocket unavailable services"
```
