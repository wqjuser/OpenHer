# WebSocket Delivery Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move completed WebSocket turn delivery and chat-log persistence out of `WebSocketChatTurnService` into a focused delivery service.

**Architecture:** Add `server/websocket_delivery.py` with `WebSocketCompletedTurnDeliveryService`. `WebSocketChatTurnService` will continue to merge buffered messages, resolve sessions, register connections, and stream the Actor response, but will delegate completed-turn status delivery, segment delivery, audio delivery, retry cleanup, and chat-log persistence to the new service.

**Tech Stack:** Python 3.11+, pytest, existing Starlette/FastAPI WebSocket service style.

---

### Task 1: Lock Completed Turn Delivery With Failing Tests

**Files:**
- Create: `tests/test_websocket_delivery.py`
- Verify: `server/websocket_chat.py`

- [x] **Step 1: Write segment delivery and chat-log persistence test**

Create a fake websocket, fake chat log store, fake agent returning:

```python
{
    "modality": "文字",
    "segments": ["第一句", "第二句"],
    "delays_ms": [0, 1],
    "temperature": 0.2,
}
```

Call:

```python
await service.deliver_completed_turn(
    websocket=websocket,
    agent=agent,
    session_id="session-1",
    persona_id="luna",
    client_id="client-1",
    merged_text="你好",
    clean_reply_text="完整回复",
    debug_mode=True,
)
```

Assert:
- sends first `chat_end`;
- sends a second `chat_start` and second `chat_end`;
- sleeps for `0.3`;
- includes debug status;
- persists first segment via `save_turn()` and following segment via `save_message()`.

- [x] **Step 2: Write silence and audio delivery test**

Use a fake agent status with `modality="静默"` and `audio_path` pointing to a temporary file. Assert:
- sends `silence`;
- sends `tts_audio` with base64 content and resolved format;
- does not save an assistant chat message when `client_id` is missing.

- [x] **Step 3: Write WebSocketChatTurnService structural delegation test**

Assert `server/websocket_chat.py` imports `WebSocketCompletedTurnDeliveryService`, constructs or accepts a delivery service, calls `deliver_completed_turn()`, and no longer contains `_deliver_segments()`, `_deliver_audio()`, `_log_and_persist_turn()`, or `_image_url()`.

- [x] **Step 4: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_websocket_delivery.py -q`

Expected: FAIL because `server.websocket_delivery` does not exist and `WebSocketChatTurnService` still owns the delivery helpers.

### Task 2: Add WebSocketCompletedTurnDeliveryService

**Files:**
- Create: `server/websocket_delivery.py`
- Test: `tests/test_websocket_delivery.py`

- [x] **Step 1: Implement constructor and `deliver_completed_turn()`**

The service constructor accepts:
- `chat_log_store: Any = None`
- `sleep: SleepFunc = asyncio.sleep`
- `audio_format_resolver: Callable[[str], str] = audio_format_for_path`

`deliver_completed_turn()` must:
- read `agent.get_status()`;
- add `agent.get_debug_status()` when `debug_mode=True`;
- pop `image_path`, `audio_path`, `segments`, and `delays_ms`;
- deliver silence, multi-segment, or regular chat end;
- deliver audio when available;
- clear and deliver pending retry using existing behavior;
- persist the turn using existing behavior.

- [x] **Step 2: Move helper behavior**

Move helper methods from `WebSocketChatTurnService` to the new service:
- `_deliver_segments()`
- `_deliver_audio()`
- `_clear_pending_retry()`
- `_deliver_pending_retry()`
- `_log_and_persist_turn()`
- `_image_url()`

- [x] **Step 3: Run delivery tests**

Run: `.venv/bin/python -m pytest tests/test_websocket_delivery.py -q`

Expected: behavior tests pass; structural delegation may still fail until Task 3.

### Task 3: Delegate WebSocketChatTurnService Delivery

**Files:**
- Modify: `server/websocket_chat.py`
- Test: `tests/test_websocket_chat_service.py`
- Test: `tests/test_websocket_delivery.py`

- [x] **Step 1: Import and type the delivery service**

Add `from server.websocket_delivery import WebSocketCompletedTurnDeliveryService`.

Constructor should accept:

```python
delivery_service: Optional[WebSocketCompletedTurnDeliveryService] = None
```

Store:

```python
self.delivery_service = delivery_service or WebSocketCompletedTurnDeliveryService(
    chat_log_store=chat_log_store,
    sleep=sleep,
    audio_format_resolver=audio_format_resolver,
)
```

- [x] **Step 2: Replace completed-turn helper call**

Replace:

```python
await self._deliver_completed_turn(...)
```

with:

```python
await self.delivery_service.deliver_completed_turn(...)
```

- [x] **Step 3: Remove moved helper methods and unused imports**

Remove `base64`, `os`, and `audio_format_for_path` from `server/websocket_chat.py` if unused after the move.

- [x] **Step 4: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_websocket_delivery.py tests/test_websocket_chat_service.py tests/test_websocket_demo_commands.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `server/websocket_delivery.py`
- Verify: `server/websocket_chat.py`
- Verify: `tests/test_websocket_delivery.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile server/websocket_delivery.py server/websocket_chat.py tests/test_websocket_delivery.py`

Expected: exit code 0.

- [x] **Step 3: Run full tests**

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: full suite passes with the known skipped WebSocket integration test unchanged.

- [x] **Step 4: Run repository hygiene checks**

Run: `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0.

### Self-Review

- Spec coverage: The plan extracts only completed-turn delivery and persistence from the WebSocket chat turn service.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `WebSocketCompletedTurnDeliveryService` and `deliver_completed_turn()` are named consistently across tests and implementation.
