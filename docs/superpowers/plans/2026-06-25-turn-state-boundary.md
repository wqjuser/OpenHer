# Agent Turn State Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move per-turn counter, fallback reset, active timestamp, and interaction cadence updates out of `ChatAgent` into a focused turn-state mixin.

**Architecture:** Add `agent/turn_state.py` with `AgentTurnStateMixin._begin_turn()`. Both `chat()` and `chat_stream()` paths will continue to receive a `now` value, but they will delegate all turn-state bookkeeping to the mixin. This preserves current cadence math and keeps `ChatAgent` centered on lifecycle orchestration.

**Tech Stack:** Python 3.11+, pytest, pyright, existing ChatAgent mixin pattern.

---

### Task 1: Lock Turn State Behavior With Failing Tests

**Files:**
- Create: `tests/test_turn_state.py`
- Verify: `agent/chat_agent.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path
import importlib
import importlib.util


ROOT = Path(__file__).resolve().parents[1]


def make_agent(last_active=100.0, cadence=0.0, turn_count=2):
    spec = importlib.util.find_spec("agent.turn_state")
    assert spec is not None
    module = importlib.import_module("agent.turn_state")

    class DummyAgent(module.AgentTurnStateMixin):
        def __init__(self):
            self._turn_count = turn_count
            self._turn_used_fallback = True
            self._last_active = last_active
            self._interaction_cadence = cadence

    return DummyAgent()


def test_turn_state_mixin_starts_turn_and_initializes_cadence():
    agent = make_agent(last_active=100.0, cadence=0.0, turn_count=2)

    now = agent._begin_turn(now=112.0)

    assert now == 112.0
    assert agent._turn_count == 3
    assert agent._turn_used_fallback is False
    assert agent._interaction_cadence == 12.0
    assert agent._last_active == 112.0


def test_turn_state_mixin_smooths_existing_cadence():
    agent = make_agent(last_active=100.0, cadence=10.0, turn_count=4)

    now = agent._begin_turn(now=130.0)

    assert now == 130.0
    assert agent._turn_count == 5
    assert agent._interaction_cadence == 16.0
    assert agent._last_active == 130.0


def test_turn_state_mixin_handles_missing_last_active_without_touching_cadence():
    agent = make_agent(last_active=0.0, cadence=9.0, turn_count=0)

    now = agent._begin_turn(now=50.0)

    assert now == 50.0
    assert agent._turn_count == 1
    assert agent._turn_used_fallback is False
    assert agent._interaction_cadence == 9.0
    assert agent._last_active == 50.0


def test_chat_agent_delegates_turn_state_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.turn_state import AgentTurnStateMixin" in source
    assert "AgentTurnStateMixin" in source
    assert "self._turn_count += 1" not in source
    assert "self._interaction_cadence = 0.3" not in source
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_turn_state.py -q`

Expected: FAIL because `agent.turn_state` does not exist and `ChatAgent` still owns turn bookkeeping.

### Task 2: Add AgentTurnStateMixin

**Files:**
- Create: `agent/turn_state.py`
- Test: `tests/test_turn_state.py`

- [x] **Step 1: Implement `agent/turn_state.py`**

Move the duplicated turn-start logic into `_begin_turn(now: float | None = None) -> float`. When `now` is omitted, call `time.time()`. Preserve the existing cadence formula: first interval becomes `delta`, later intervals become `0.3 * delta + 0.7 * previous_cadence`.

- [x] **Step 2: Run turn-state tests**

Run: `.venv/bin/python -m pytest tests/test_turn_state.py -q`

Expected: behavior tests pass; the ChatAgent delegation test still fails until Task 3.

### Task 3: Delegate ChatAgent Turn State Behavior

**Files:**
- Modify: `agent/chat_agent.py`
- Test: `tests/test_turn_state.py`
- Test: `tests/test_websocket_chat_service.py`

- [x] **Step 1: Import and inherit the mixin**

Add `from agent.turn_state import AgentTurnStateMixin` to `agent/chat_agent.py`.

Add `AgentTurnStateMixin` to the `ChatAgent` base class list near the other lifecycle mixins.

- [x] **Step 2: Replace duplicated turn-start blocks**

Replace both duplicated blocks in `_chat_inner()` and `chat_stream()` with:

```python
now = self._begin_turn()
```

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_turn_state.py tests/test_websocket_chat_service.py tests/test_agent_status.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/turn_state.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_turn_state.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/turn_state.py agent/chat_agent.py`

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

- Spec coverage: The plan preserves current turn-count, fallback reset, active timestamp, and cadence behavior while moving it out of `ChatAgent`.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `AgentTurnStateMixin` and `_begin_turn()` are named consistently across tests, implementation, and `ChatAgent`.
