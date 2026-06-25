# Agent Drive Lifecycle Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move drive baseline evolution and crystallization gate execution out of `ChatAgent` into a focused genome lifecycle mixin.

**Architecture:** Add `agent/drive_lifecycle.py` with `AgentDriveLifecycleMixin`. The mixin will expose `_evolve_drive_baseline()` and `_crystallize_last_action_if_needed()`, preserving current math, clamping, style-memory clock updates, and crystallization payload. `ChatAgent` will call these helpers from both normal and streaming paths.

**Tech Stack:** Python 3.11+, pytest, pyright, existing ChatAgent mixin pattern.

---

### Task 1: Lock Drive Lifecycle Behavior With Failing Tests

**Files:**
- Create: `tests/test_drive_lifecycle.py`
- Verify: `agent/chat_agent.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path
import importlib
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
DRIVES = ["connection", "novelty", "expression", "safety", "play"]


class FakeGenomeAgent:
    def __init__(self):
        self.drive_baseline = {
            "connection": 0.5,
            "novelty": 0.94,
            "expression": 0.12,
            "safety": 0.5,
            "play": 0.5,
        }


class FakeStyleMemory:
    def __init__(self):
        self.clock = None
        self.crystallized = []

    def set_clock(self, now):
        self.clock = now

    def crystallize(self, context, monologue, reply, user_input):
        self.crystallized.append((context, monologue, reply, user_input))


def make_agent():
    spec = importlib.util.find_spec("agent.drive_lifecycle")
    assert spec is not None
    module = importlib.import_module("agent.drive_lifecycle")

    class DummyAgent(module.AgentDriveLifecycleMixin):
        def __init__(self):
            self.agent = FakeGenomeAgent()
            self._initial_baseline = {
                "connection": 0.4,
                "novelty": 0.5,
                "expression": 0.5,
                "safety": 0.5,
                "play": 0.5,
            }
            self.baseline_lr = 0.1
            self.elasticity = 0.2
            self.style_memory = FakeStyleMemory()
            self._last_action = None
            self.should_crystallize = False

        def _should_crystallize(self, reward, context):
            return self.should_crystallize

    return DummyAgent()


def test_drive_lifecycle_mixin_evolves_and_clamps_baseline():
    agent = make_agent()

    agent._evolve_drive_baseline(
        {
            "connection": 0.3,
            "novelty": 1.0,
            "expression": -1.0,
        }
    )

    assert agent.agent.drive_baseline == {
        "connection": 0.51,
        "novelty": 0.95,
        "expression": 0.1,
        "safety": 0.5,
        "play": 0.5,
    }


def test_drive_lifecycle_mixin_crystallizes_last_action_when_gate_allows():
    agent = make_agent()
    context = {"novelty_level": 0.9}
    agent._last_action = {
        "context": {"old": 1},
        "monologue": "thinking",
        "reply": "hello",
        "user_input": "hi",
    }
    agent.should_crystallize = True

    did_crystallize = agent._crystallize_last_action_if_needed(
        reward=0.9,
        context=context,
        now=123.0,
    )

    assert did_crystallize is True
    assert agent.style_memory.clock == 123.0
    assert agent.style_memory.crystallized == [
        ({"old": 1}, "thinking", "hello", "hi")
    ]


def test_drive_lifecycle_mixin_skips_crystallization_without_last_action_or_gate():
    agent = make_agent()

    assert agent._crystallize_last_action_if_needed(0.9, {}, 1.0) is False
    assert agent.style_memory.crystallized == []

    agent._last_action = {
        "context": {},
        "monologue": "thinking",
        "reply": "hello",
        "user_input": "hi",
    }
    agent.should_crystallize = False

    assert agent._crystallize_last_action_if_needed(0.9, {}, 2.0) is False
    assert agent.style_memory.crystallized == []


def test_chat_agent_delegates_drive_lifecycle_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.drive_lifecycle import AgentDriveLifecycleMixin" in source
    assert "AgentDriveLifecycleMixin" in source
    assert "shift = frustration_delta.get" not in source
    assert "self.style_memory.crystallize(" not in source
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_drive_lifecycle.py -q`

Expected: FAIL because `agent.drive_lifecycle` does not exist and `ChatAgent` still owns the duplicated drive lifecycle blocks.

### Task 2: Add AgentDriveLifecycleMixin

**Files:**
- Create: `agent/drive_lifecycle.py`
- Test: `tests/test_drive_lifecycle.py`

- [x] **Step 1: Implement `agent/drive_lifecycle.py`**

Move the baseline evolution loop into `_evolve_drive_baseline(frustration_delta: dict[str, float]) -> None`. Move crystallization execution into `_crystallize_last_action_if_needed(reward: float, context: dict, now: float) -> bool`.

- [x] **Step 2: Run drive lifecycle tests**

Run: `.venv/bin/python -m pytest tests/test_drive_lifecycle.py -q`

Expected: behavior tests pass; the ChatAgent delegation test still fails until Task 3.

### Task 3: Delegate ChatAgent Drive Lifecycle Behavior

**Files:**
- Modify: `agent/chat_agent.py`
- Test: `tests/test_drive_lifecycle.py`
- Test: `tests/test_websocket_chat_service.py`

- [x] **Step 1: Import and inherit the mixin**

Add `from agent.drive_lifecycle import AgentDriveLifecycleMixin` to `agent/chat_agent.py`.

Add `AgentDriveLifecycleMixin` to the `ChatAgent` base class list near other lifecycle mixins.

- [x] **Step 2: Replace duplicated blocks**

Replace both baseline-evolution loops with:

```python
self._evolve_drive_baseline(frustration_delta)
```

Replace both crystallization blocks with:

```python
self._crystallize_last_action_if_needed(reward, context, now)
```

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_drive_lifecycle.py tests/test_websocket_chat_service.py tests/test_agent_status.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/drive_lifecycle.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_drive_lifecycle.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/drive_lifecycle.py agent/chat_agent.py`

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

- Spec coverage: The plan preserves current drive baseline evolution and crystallization payloads while moving them out of `ChatAgent`.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `AgentDriveLifecycleMixin`, `_evolve_drive_baseline()`, and `_crystallize_last_action_if_needed()` are named consistently across tests and implementation.
