# Modality Execution Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move duplicated modality-skill execution logic out of `ChatAgent` into a focused mixin shared by normal and streamed chat turns.

**Architecture:** Add `agent/modality_execution.py` with a `ModalityExecutionMixin` that extracts the raw expression-mode text, builds a structured JSON skill context, runs the modality skill engine, updates `_skill_outputs`, and performs existing retry fallback when all selected skills fail. `ChatAgent.chat()` and `ChatAgent.chat_stream()` will delegate to the mixin and preserve their external result contracts.

**Tech Stack:** Python 3.11+, pytest, pyright, existing async skill-engine interfaces.

---

### Task 1: Lock the New Modality Boundary With Failing Tests

**Files:**
- Create: `tests/test_modality_execution.py`

- [x] **Step 1: Write the failing tests**

```python
import asyncio
import json
from types import SimpleNamespace

from agent.modality_execution import ModalityExecutionMixin


class SkillResult:
    def __init__(self, success, output=None):
        self.success = success
        self.output = output or {}


class CapturingEngine:
    def __init__(self, results):
        self.results = results
        self.calls = []

    async def plan_and_execute(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


class DummyAgent(ModalityExecutionMixin):
    def __init__(self, engine):
        self.modality_skill_engine = engine
        self.persona = SimpleNamespace(persona_id="luna")
        self.llm = object()
        self.history = []
        self._skill_outputs = {"stale": "value"}
        self._pending_retry = {"old": True}
        self._fallback_history_added = False

    async def _modality_failure_with_retry(self, failed_modality, original_reply, express_content):
        self.retry_args = (failed_modality, original_reply, express_content)
        return "fallback reply"


def test_modality_execution_uses_structured_skill_context():
    engine = CapturingEngine([SkillResult(True, {"_modality": "照片", "image_path": "/tmp/a.png"})])
    agent = DummyAgent(engine)
    raw_text = "【内心独白】想拍照\n【最终回复】看这里\n【表达方式】照片，参考头像"

    result = asyncio.run(agent._execute_modality_skills(raw_text, "看这里", "文字"))

    assert result.reply == "看这里"
    assert result.modality == "照片"
    assert result.outputs == {"_modality": "照片", "image_path": "/tmp/a.png"}
    assert agent._pending_retry is None
    call = engine.calls[0]
    assert call["raw_modality"] == "照片，参考头像"
    assert json.loads(call["raw_output"]) == {"reply": "看这里", "modality": "文字"}


def test_modality_execution_falls_back_to_text_when_all_skills_fail():
    engine = CapturingEngine([SkillResult(False), SkillResult(False)])
    agent = DummyAgent(engine)
    raw_text = "【内心独白】想说话\n【最终回复】听我说\n【表达方式】语音"

    result = asyncio.run(agent._execute_modality_skills(raw_text, "听我说", "语音"))

    assert result.reply == "fallback reply"
    assert result.modality == "文字"
    assert agent._fallback_history_added is True
    assert agent.retry_args == ("语音", "听我说", raw_text)
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_modality_execution.py -q`

Expected: FAIL because `agent.modality_execution` does not exist yet.

### Task 2: Add the Modality Execution Mixin

**Files:**
- Create: `agent/modality_execution.py`
- Test: `tests/test_modality_execution.py`

- [x] **Step 1: Implement the mixin**

Create `agent/modality_execution.py` with:

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agent.parser import _SECTION_RE


@dataclass
class ModalityExecutionResult:
    reply: str
    modality: str
    outputs: dict[str, Any] = field(default_factory=dict)


class ModalityExecutionMixin:
    async def _execute_modality_skills(
        self,
        raw_text: str,
        reply: str,
        modality: str,
    ) -> ModalityExecutionResult:
        self._skill_outputs = {}
        self._pending_retry = None

        raw_modality = ""
        matches = list(_SECTION_RE.finditer(raw_text))
        if matches:
            raw_modality = raw_text[matches[-1].end():].strip()
            print(f"  [express] raw_modality='{raw_modality[:80]}'")

        if self.modality_skill_engine and raw_modality:
            structured_context = json.dumps(
                {"reply": reply, "modality": modality},
                ensure_ascii=False,
            )
            print(f"  [skill-context] 📦 {structured_context[:200]}")
            skill_results = await self.modality_skill_engine.plan_and_execute(
                raw_modality=raw_modality,
                raw_output=structured_context,
                persona=self.persona,
                llm=self.llm,
                chat_history=self.history,
            )
            for skill_result in skill_results:
                if skill_result.success:
                    self._skill_outputs.update(skill_result.output)

            if self._skill_outputs.get("_modality"):
                modality = self._skill_outputs["_modality"]

            if skill_results and all(not result.success for result in skill_results):
                print("  [skill] ⚠ All skills failed, triggering LLM fallback")
                fallback_reply = await self._modality_failure_with_retry(
                    modality,
                    reply,
                    raw_text,
                )
                if fallback_reply:
                    reply = fallback_reply
                modality = "文字"
                self._fallback_history_added = True

        return ModalityExecutionResult(
            reply=reply,
            modality=modality,
            outputs=dict(self._skill_outputs),
        )
```

- [x] **Step 2: Run the new tests**

Run: `.venv/bin/python -m pytest tests/test_modality_execution.py -q`

Expected: PASS.

### Task 3: Delegate ChatAgent Modality Execution

**Files:**
- Modify: `agent/chat_agent.py`
- Test: `tests/test_modality_execution.py`
- Test: `tests/test_bilingual_parser.py`

- [x] **Step 1: Import and inherit the mixin**

Add:

```python
from agent.modality_execution import ModalityExecutionMixin
```

Change the class bases to include `ModalityExecutionMixin`.

- [x] **Step 2: Replace duplicated modality blocks**

In `_chat_inner`, replace the direct `_SECTION_RE` extraction and `plan_and_execute` block with:

```python
modality_result = await self._execute_modality_skills(
    single_response.content,
    reply,
    modality,
)
reply = modality_result.reply
modality = modality_result.modality
```

In `chat_stream`, replace the matching direct block with:

```python
modality_result = await self._execute_modality_skills(raw_text, reply, modality)
reply = modality_result.reply
modality = modality_result.modality
```

When building the non-stream `result` dict, forward `image_path`, `audio_path`, `segments`, and `delays_ms` from `modality_result.outputs`.

- [x] **Step 3: Add a structural regression test**

Append to `tests/test_modality_execution.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chat_agent_delegates_modality_execution_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.modality_execution import ModalityExecutionMixin" in source
    assert "ModalityExecutionMixin" in source
    assert source.count("_execute_modality_skills(") == 2
    assert "plan_and_execute(" not in source
```

- [x] **Step 4: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_modality_execution.py tests/test_bilingual_parser.py tests/test_skill_engine.py::TestModalitySkillEngine -q`

Expected: all targeted tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/modality_execution.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_modality_execution.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/modality_execution.py agent/chat_agent.py`

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

- Spec coverage: The plan covers the duplicated modality-skill execution path in normal and streamed chat, plus result forwarding and fallback behavior.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `ModalityExecutionResult`, `outputs`, and `_execute_modality_skills` are named consistently across tests and implementation.
