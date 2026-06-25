# Agent Turn Finalization Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move completed-turn state updates out of `ChatAgent` into a focused finalization mixin.

**Architecture:** Add `agent/turn_finalization.py` with `AgentTurnFinalizationMixin`. The mixin will update chat history, fallback flags, `_last_action`, `_last_modality`, keyword memory, turn logs, and EverMemOS background hooks after a reply is produced. `ChatAgent` will call the helper from both normal and streaming paths.

**Tech Stack:** Python 3.11+, pytest, pyright, existing ChatAgent mixin pattern.

---

### Task 1: Lock Turn Finalization Behavior With Failing Tests

**Files:**
- Create: `tests/test_turn_finalization.py`
- Verify: `agent/chat_agent.py`

- [x] **Step 1: Write the failing tests**

Create tests that assert:
- `_finalize_turn_response()` appends user and assistant messages, truncates to `max_history`, updates `_last_action`, writes keyword memory, and triggers EverMemOS background hooks.
- `_finalize_turn_response()` respects `_fallback_history_added` and avoids duplicate assistant history entries.
- `_finalize_turn_response()` skips user memory and EverMemOS for proactive turns while preserving the assistant reply in local history.
- `ChatAgent` imports and inherits `AgentTurnFinalizationMixin`, and no longer performs direct completed-turn history, memory, or EverMemOS finalization inline.

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_turn_finalization.py -q`

Expected: FAIL because `agent.turn_finalization` does not exist and `ChatAgent` still owns completed-turn finalization blocks.

### Task 2: Add AgentTurnFinalizationMixin

**Files:**
- Create: `agent/turn_finalization.py`
- Test: `tests/test_turn_finalization.py`

- [x] **Step 1: Implement `agent/turn_finalization.py`**

Add `_finalize_turn_response(...) -> None` with this signature:

```python
def _finalize_turn_response(
    self,
    user_message: str,
    reply: str,
    monologue: str,
    modality: str,
    context: dict[str, Any],
    drive_satisfaction: dict[str, float],
    reward: float,
    *,
    is_proactive: bool = False,
) -> None:
    ...
```

The helper preserves existing behavior:
- Append user history only when `is_proactive` is false.
- Append assistant history unless `_fallback_history_added` is true.
- Reset `_fallback_history_added` to false.
- Truncate history to `max_history`.
- Set `_last_action` and `_last_modality`.
- Store keyword memory only when `memory_store` exists and `is_proactive` is false.
- Print the same genome, feel, and drive satisfaction logs.
- Trigger `_evermemos_store_bg()` and `_evermemos_search_bg()` only when `is_proactive` is false.

- [x] **Step 2: Run turn finalization tests**

Run: `.venv/bin/python -m pytest tests/test_turn_finalization.py -q`

Expected: behavior tests pass; the ChatAgent delegation test still fails until Task 3.

### Task 3: Delegate ChatAgent Turn Finalization

**Files:**
- Modify: `agent/chat_agent.py`
- Test: `tests/test_turn_finalization.py`
- Test: `tests/test_websocket_chat_service.py`

- [x] **Step 1: Import and inherit the mixin**

Add `from agent.turn_finalization import AgentTurnFinalizationMixin` to `agent/chat_agent.py`.

Add `AgentTurnFinalizationMixin` to the `ChatAgent` base class list near the other lifecycle mixins.

- [x] **Step 2: Replace inline completed-turn blocks**

Replace the normal chat history/action/memory/log/EverMemOS block with:

```python
self._finalize_turn_response(
    user_message,
    reply,
    monologue,
    modality,
    context,
    drive_satisfaction,
    reward,
    is_proactive=is_proactive,
)
```

Replace the stream path history/action/log/EverMemOS block with:

```python
self._finalize_turn_response(
    user_message,
    reply,
    monologue,
    modality,
    context,
    drive_satisfaction,
    reward,
)
```

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_turn_finalization.py tests/test_websocket_chat_service.py tests/test_agent_status.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/turn_finalization.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_turn_finalization.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/turn_finalization.py agent/chat_agent.py`

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

- Spec coverage: The plan preserves completed-turn state updates while moving them out of `ChatAgent`.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `AgentTurnFinalizationMixin` and `_finalize_turn_response()` are named consistently across tests and implementation.
