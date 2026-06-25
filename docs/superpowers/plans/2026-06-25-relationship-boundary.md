# Agent Relationship Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move relationship EMA state evolution out of `EverMemosMixin` into a focused relationship mixin while preserving the existing `_apply_relationship_ema()` API.

**Architecture:** Add `agent/relationship.py` with `AgentRelationshipMixin`. `EverMemosMixin` will only handle EverMemOS session context, background store/search, and search collection. `ChatAgent` will inherit both mixins so chat and streaming paths keep calling `_apply_relationship_ema()` unchanged.

**Tech Stack:** Python 3.11+, pytest, pyright, existing ChatAgent mixin pattern.

---

### Task 1: Lock Relationship Boundary With Failing Tests

**Files:**
- Create: `tests/test_relationship.py`
- Verify: `agent/evermemos_mixin.py`
- Verify: `agent/chat_agent.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path
import importlib
import importlib.util


ROOT = Path(__file__).resolve().parents[1]


def make_agent():
    spec = importlib.util.find_spec("agent.relationship")
    assert spec is not None
    module = importlib.import_module("agent.relationship")

    class DummyAgent(module.AgentRelationshipMixin):
        def __init__(self):
            self._relationship_ema = {}

    return DummyAgent()


def test_relationship_mixin_initializes_prior_and_applies_depth_weighted_delta():
    agent = make_agent()

    status = agent._apply_relationship_ema(
        {
            "relationship_depth": 0.2,
            "emotional_valence": 0.1,
            "trust_level": 0.3,
            "pending_foresight": 0.6,
        },
        {
            "relationship_delta": 0.4,
            "emotional_valence": -0.3,
            "trust_delta": 0.2,
        },
        conversation_depth=0.4,
    )

    assert status == {
        "relationship_depth": 0.34,
        "emotional_valence": -0.005,
        "trust_level": 0.37,
        "pending_foresight": 0.6,
    }
    assert agent._relationship_ema == status


def test_relationship_mixin_clips_and_smooths_existing_state():
    agent = make_agent()
    agent._relationship_ema = {
        "relationship_depth": 0.8,
        "emotional_valence": -0.8,
        "trust_level": 0.1,
        "pending_foresight": 0.2,
    }

    status = agent._apply_relationship_ema(
        {
            "relationship_depth": 0.9,
            "emotional_valence": -0.9,
            "trust_level": 0.9,
            "pending_foresight": 1.0,
        },
        {
            "relationship_delta": 0.5,
            "emotional_valence": -0.5,
            "trust_delta": 0.5,
        },
        conversation_depth=2.0,
    )

    assert status == {
        "relationship_depth": 0.93,
        "emotional_valence": -0.93,
        "trust_level": 0.685,
        "pending_foresight": 0.72,
    }


def test_chat_agent_delegates_relationship_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")
    evermemos_source = (ROOT / "agent/evermemos_mixin.py").read_text(encoding="utf-8")

    assert "from agent.relationship import AgentRelationshipMixin" in source
    assert "AgentRelationshipMixin" in source
    assert "def _apply_relationship_ema(" not in evermemos_source
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_relationship.py -q`

Expected: FAIL because `agent.relationship` does not exist and `EverMemosMixin` still owns `_apply_relationship_ema()`.

### Task 2: Add AgentRelationshipMixin

**Files:**
- Create: `agent/relationship.py`
- Test: `tests/test_relationship.py`

- [x] **Step 1: Implement `agent/relationship.py`**

Move the existing `_apply_relationship_ema()` method body from `EverMemosMixin` into `AgentRelationshipMixin`. Keep the method name, signature, rounding, clipping, and observability log unchanged.

- [x] **Step 2: Run relationship tests**

Run: `.venv/bin/python -m pytest tests/test_relationship.py -q`

Expected: behavior tests pass; the ChatAgent delegation test still fails until Task 3.

### Task 3: Delegate ChatAgent Relationship Behavior

**Files:**
- Modify: `agent/chat_agent.py`
- Modify: `agent/evermemos_mixin.py`
- Test: `tests/test_relationship.py`
- Test: `tests/test_security_regressions.py::EverMemOSLoggingRegressionTests`

- [x] **Step 1: Import and inherit the mixin**

Add `from agent.relationship import AgentRelationshipMixin` to `agent/chat_agent.py`.

Add `AgentRelationshipMixin` to the `ChatAgent` base class list after `EverMemosMixin`.

- [x] **Step 2: Remove relationship method from EverMemosMixin**

Delete `_apply_relationship_ema()` from `agent/evermemos_mixin.py`. Update the module docstring so it no longer claims to handle relationship EMA computation.

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_relationship.py tests/test_security_regressions.py::EverMemOSLoggingRegressionTests -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/relationship.py`
- Verify: `agent/evermemos_mixin.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_relationship.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/relationship.py agent/evermemos_mixin.py agent/chat_agent.py`

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

- Spec coverage: The plan preserves `_apply_relationship_ema()` behavior while moving it out of the EverMemOS memory boundary.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `AgentRelationshipMixin` and `_apply_relationship_ema()` are named consistently across tests, implementation, and `ChatAgent`.
