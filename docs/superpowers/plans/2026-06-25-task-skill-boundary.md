# Agent Task Skill Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move task-skill pre-processing and task execution logging out of `ChatAgent` into a focused mixin while preserving `_run_task_skills()` and `_log_task()` call sites.

**Architecture:** Add `agent/task_skills.py` with `AgentTaskSkillMixin`. The mixin will read the existing `task_skill_engine`, `llm`, `task_log_store`, and `persona` fields from `ChatAgent`. `ChatAgent` will inherit it, keeping the main chat lifecycle focused on persona engine orchestration.

**Tech Stack:** Python 3.11+, pytest, pyright, existing ChatAgent mixin pattern.

---

### Task 1: Lock Task Skill Behavior With Failing Tests

**Files:**
- Create: `tests/test_task_skills.py`
- Verify: `agent/chat_agent.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path
from types import SimpleNamespace
import importlib
import importlib.util


ROOT = Path(__file__).resolve().parents[1]


class FakeTaskSkillEngine:
    def __init__(self, observations=None, error=None):
        self.observations = observations
        self.error = error
        self.calls = []

    async def react_loop(self, user_message, llm):
        self.calls.append((user_message, llm))
        if self.error:
            raise self.error
        return self.observations


class FakeTaskLogStore:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def log_execution(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error


def make_agent(task_skill_engine=None, task_log_store=None):
    spec = importlib.util.find_spec("agent.task_skills")
    assert spec is not None
    module = importlib.import_module("agent.task_skills")

    class DummyAgent(module.AgentTaskSkillMixin):
        def __init__(self):
            self.task_skill_engine = task_skill_engine
            self.llm = object()
            self.task_log_store = task_log_store
            self.persona = SimpleNamespace(persona_id="luna")

    return DummyAgent()


async def test_task_skill_mixin_injects_observations_into_user_message():
    engine = FakeTaskSkillEngine(observations="weather=21C")
    agent = make_agent(task_skill_engine=engine)

    result = await agent._run_task_skills("天气如何")

    assert "天气如何" in result
    assert "以下是真实查询数据" in result
    assert "weather=21C" in result
    assert engine.calls == [("天气如何", agent.llm)]


async def test_task_skill_mixin_preserves_message_without_engine_or_on_error():
    assert await make_agent()._run_task_skills("hello") == "hello"

    engine = FakeTaskSkillEngine(error=RuntimeError("boom"))
    agent = make_agent(task_skill_engine=engine)

    assert await agent._run_task_skills("hello") == "hello"
    assert engine.calls == [("hello", agent.llm)]


def test_task_skill_mixin_logs_execution_and_swallows_store_errors():
    store = FakeTaskLogStore()
    agent = make_agent(task_log_store=store)

    agent._log_task(
        "weather",
        "天气",
        {"command": "curl", "stdout": "sunny", "stderr": "", "success": True},
        "晴天",
    )

    assert store.calls == [
        {
            "persona_id": "luna",
            "skill_id": "weather",
            "user_input": "天气",
            "command": "curl",
            "stdout": "sunny",
            "stderr": "",
            "success": True,
            "reply": "晴天",
        }
    ]

    failing = make_agent(task_log_store=FakeTaskLogStore(error=RuntimeError("db")))
    failing._log_task("weather", "天气", {}, "fallback")


def test_chat_agent_delegates_task_skill_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.task_skills import AgentTaskSkillMixin" in source
    assert "AgentTaskSkillMixin" in source
    assert "def _run_task_skills(" not in source
    assert "def _log_task(" not in source
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_task_skills.py -q`

Expected: FAIL because `agent.task_skills` does not exist and `ChatAgent` still owns the methods.

### Task 2: Add AgentTaskSkillMixin

**Files:**
- Create: `agent/task_skills.py`
- Test: `tests/test_task_skills.py`

- [x] **Step 1: Implement `agent/task_skills.py`**

Move `_run_task_skills()` and `_log_task()` from `ChatAgent` into `AgentTaskSkillMixin`. Keep the injected observation text and logging payload unchanged.

- [x] **Step 2: Run task skill tests**

Run: `.venv/bin/python -m pytest tests/test_task_skills.py -q`

Expected: behavior tests pass; the ChatAgent delegation test still fails until Task 3.

### Task 3: Delegate ChatAgent Task Skill Behavior

**Files:**
- Modify: `agent/chat_agent.py`
- Test: `tests/test_task_skills.py`
- Test: `tests/test_skill_engine.py`

- [x] **Step 1: Import and inherit the mixin**

Add `from agent.task_skills import AgentTaskSkillMixin` to `agent/chat_agent.py`.

Add `AgentTaskSkillMixin` to the `ChatAgent` base class list after `PromptBuilderMixin`.

- [x] **Step 2: Remove inline task skill methods**

Delete `_run_task_skills()` and `_log_task()` from `agent/chat_agent.py`.

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_task_skills.py tests/test_skill_engine.py tests/test_agent_status.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/task_skills.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_task_skills.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/task_skills.py agent/chat_agent.py`

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

- Spec coverage: The plan preserves task skill preprocessing and task log payloads while moving them out of `ChatAgent`.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `AgentTaskSkillMixin`, `_run_task_skills()`, and `_log_task()` are named consistently across tests and implementation.
