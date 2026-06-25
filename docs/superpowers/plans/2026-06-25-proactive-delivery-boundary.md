# Proactive Delivery Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move proactive outbox reprocessing, WebSocket push, EverMemOS storage, and outbox state transitions out of `ProactiveService` into a focused delivery service.

**Architecture:** Add `server/proactive_delivery.py` with `ProactiveOutboxDeliveryService` and `ProactiveDeliveryResult`. `ProactiveService` will keep heartbeat/sweep orchestration, outbox enqueue decisions, persistence, and metric aggregation while delegating one-row delivery to the new service.

**Tech Stack:** Python 3.11+, pytest, existing FastAPI/Starlette WebSocket messaging conventions.

---

### Task 1: Lock Proactive Outbox Delivery With Failing Tests

**Files:**
- Create: `tests/test_proactive_delivery.py`
- Verify: `server/proactive_service.py`

- [x] **Step 1: Write segment delivery success test**

Create fake state store, fake EverMemOS, fake websocket, and fake agent. The fake agent returns:

```python
{
    "reply": "aggregate reply",
    "modality": "文字",
    "segments": ["第一句", "第二句"],
    "delays_ms": [0, 1],
}
```

Call:

```python
result = await service.deliver(agent, "session-1", row)
```

Assert:
- `outbox_try_send()` is called;
- the agent is called with `is_proactive=True` and a stimulus containing the raw outbox reply;
- websocket receives segment messages with `proactive=True`, `drive`, and `persona`;
- sleeps for `0.3`;
- EverMemOS stores the proactive turn;
- state store marks delivered;
- result reports `delivered=True`, `ws_push_ok=True`, and `ws_push_failed=False`.

- [x] **Step 2: Write failed websocket delivery test**

Use one websocket that raises from `send_json()`. Assert:
- websocket is removed from the session connection set;
- state store marks failed;
- state store does not mark delivered;
- result reports `delivered=False`, `ws_push_ok=False`, and `ws_push_failed=True`.

- [x] **Step 3: Write ProactiveService delegation structural test**

Assert `server/proactive_service.py` imports `ProactiveOutboxDeliveryService`, accepts or constructs `delivery_service`, calls `self.delivery_service.deliver()`, and no longer contains direct `send_json()`, `store_proactive_turn()`, `outbox_try_send()`, `outbox_mark_failed()`, or `outbox_mark_delivered()` calls.

- [x] **Step 4: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_proactive_delivery.py -q`

Expected: FAIL because `server.proactive_delivery` does not exist and `ProactiveService` still owns outbox delivery.

### Task 2: Add ProactiveOutboxDeliveryService

**Files:**
- Create: `server/proactive_delivery.py`
- Test: `tests/test_proactive_delivery.py`

- [x] **Step 1: Implement result dataclass**

Create:

```python
@dataclass(frozen=True)
class ProactiveDeliveryResult:
    attempted: bool
    delivered: bool
    ws_push_ok: bool
    ws_push_failed: bool
    reply: str = ""
    sent_count: int = 0
```

- [x] **Step 2: Implement constructor**

The service constructor accepts:
- `state_store: Any`
- `evermemos: Any`
- `ws_connections: dict[str, set[Any]]`
- `sleep: SleepFunc = asyncio.sleep`

- [x] **Step 3: Implement `deliver()`**

Move existing behavior from `ProactiveService.deliver_message()`:
- try-send the outbox row;
- reprocess through `agent.chat(stimulus, is_proactive=True)`;
- fall back to raw reply on engine failure;
- send single or segmented WebSocket messages;
- discard failed websocket peers;
- mark failed when no connected websocket accepts the message;
- store proactive turn in EverMemOS when available;
- mark delivered on success;
- return a `ProactiveDeliveryResult` that lets `ProactiveService` update metrics.

- [x] **Step 4: Run proactive delivery tests**

Run: `.venv/bin/python -m pytest tests/test_proactive_delivery.py -q`

Expected: behavior tests pass; structural delegation may still fail until Task 3.

### Task 3: Delegate ProactiveService Delivery

**Files:**
- Modify: `server/proactive_service.py`
- Test: `tests/test_proactive_delivery.py`
- Test: `tests/test_security_regressions.py::ProactiveDeliveryContractTests`

- [x] **Step 1: Import and construct delivery service**

Add:

```python
from server.proactive_delivery import ProactiveDeliveryResult, ProactiveOutboxDeliveryService
```

Constructor should accept:

```python
delivery_service: Optional[ProactiveOutboxDeliveryService] = None
```

Store:

```python
self.delivery_service = delivery_service or ProactiveOutboxDeliveryService(
    state_store=state_store,
    evermemos=evermemos,
    ws_connections=ws_connections,
)
```

- [x] **Step 2: Replace `deliver_message()` body**

Use:

```python
result = await self.delivery_service.deliver(agent, session_id, row)
self._apply_delivery_result(result)
```

- [x] **Step 3: Add metric aggregator helper**

Add `_apply_delivery_result()`:
- increments `ws_push_fail` when `result.ws_push_failed`;
- increments `ws_push_ok` when `result.ws_push_ok`;
- increments `outbox_delivered` when `result.delivered`.

- [x] **Step 4: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_proactive_delivery.py tests/test_security_regressions.py::ProactiveDeliveryContractTests tests/test_websocket_demo_commands.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `server/proactive_delivery.py`
- Verify: `server/proactive_service.py`
- Verify: `tests/test_proactive_delivery.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile server/proactive_delivery.py server/proactive_service.py tests/test_proactive_delivery.py`

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

- Spec coverage: The plan extracts only proactive outbox delivery behavior while preserving sweep and enqueue responsibilities in `ProactiveService`.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `ProactiveOutboxDeliveryService`, `ProactiveDeliveryResult`, and `deliver()` are named consistently across tests and implementation.
