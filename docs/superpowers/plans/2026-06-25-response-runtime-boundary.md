# Agent Response Runtime Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the duplicated post-Actor response lifecycle out of `ChatAgent` into a focused response runtime mixin shared by normal and streaming chat.

**Architecture:** Add `agent/response_runtime.py` with `AgentResponseRuntimeMixin` and a `CompletedActorResponse` dataclass. The mixin parses Actor output, runs modality skills, applies Hebbian learning, updates drive satisfaction, finalizes turn state, and returns the reply/modality/skill outputs that entry points need.

**Tech Stack:** Python 3.11+, pytest, pyright, existing ChatAgent mixin pattern.

---

### Task 1: Lock Post-Actor Runtime With Failing Tests

**Files:**
- Create: `tests/test_response_runtime.py`
- Verify: `agent/chat_agent.py`

- [x] **Step 1: Write failing response runtime tests**

Create a dummy host that inherits `AgentResponseRuntimeMixin` and records:

```python
class FakeGenomeAgent:
    def __init__(self):
        self.step_calls = []

    def step(self, context, reward, drive_satisfaction):
        self.step_calls.append((context, reward, drive_satisfaction))
```

Add a test that calls:

```python
completed = await agent._complete_actor_response(
    user_message="hello",
    raw_text="【内心独白】thinking\n【最终回复】hi\n【表达方式】文字",
    context={"entropy": 0.8},
    drive_satisfaction={"connection": 0.6},
    reward=2.0,
)
```

Assert:
- `_execute_modality_skills()` receives the raw Actor text, parsed reply `hi`, and parsed modality `文字`.
- `agent.step()` receives clamped reward `1.0`.
- `_last_drive_satisfaction` is updated.
- `_finalize_turn_response()` receives the modality-adjusted reply and modality.
- The returned object exposes `reply`, `modality`, `monologue`, and `outputs`.

- [x] **Step 2: Write proactive preservation test**

Call `_complete_actor_response(..., is_proactive=True)` and assert `_finalize_turn_response()` receives `is_proactive=True`.

- [x] **Step 3: Write ChatAgent delegation structural test**

Assert `agent/chat_agent.py` imports `AgentResponseRuntimeMixin`, inherits it, calls `_complete_actor_response()` twice, and no longer contains inline `extract_reply()`, `_execute_modality_skills()`, `self.agent.step()`, `_last_drive_satisfaction =`, or `_finalize_turn_response()` calls.

- [x] **Step 4: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_response_runtime.py -q`

Expected: FAIL because `agent.response_runtime` does not exist and `ChatAgent` still owns the duplicated post-Actor lifecycle.

### Task 2: Add AgentResponseRuntimeMixin

**Files:**
- Create: `agent/response_runtime.py`
- Test: `tests/test_response_runtime.py`

- [x] **Step 1: Implement dataclass and host protocol**

Create:

```python
@dataclass
class CompletedActorResponse:
    reply: str
    modality: str
    monologue: str
    outputs: dict[str, Any]
```

The host protocol must provide `agent`, `_last_drive_satisfaction`, `_execute_modality_skills()`, and `_finalize_turn_response()`.

- [x] **Step 2: Implement `_complete_actor_response()`**

The helper must:
- parse `raw_text` using `extract_reply()`;
- run `_execute_modality_skills(raw_text, reply, modality)`;
- clamp reward into `[-1.0, 1.0]`;
- call `agent.step(context, reward=clamped_reward, drive_satisfaction=drive_satisfaction)`;
- assign `_last_drive_satisfaction`;
- call `_finalize_turn_response()` with `is_proactive` passed through;
- return `CompletedActorResponse` using the modality execution result.

- [x] **Step 3: Run response runtime tests**

Run: `.venv/bin/python -m pytest tests/test_response_runtime.py -q`

Expected: behavior tests pass; the ChatAgent structural test still fails until Task 3.

### Task 3: Delegate ChatAgent Post-Actor Runtime

**Files:**
- Modify: `agent/chat_agent.py`
- Test: `tests/test_response_runtime.py`
- Test: `tests/test_modality_execution.py`
- Test: `tests/test_turn_finalization.py`
- Test: `tests/test_websocket_chat_service.py`

- [x] **Step 1: Import and inherit the mixin**

Add `from agent.response_runtime import AgentResponseRuntimeMixin` to `agent/chat_agent.py`.

Add `AgentResponseRuntimeMixin` to the `ChatAgent` base class list near `ModalityExecutionMixin` and `AgentTurnFinalizationMixin`.

- [x] **Step 2: Replace normal chat post-Actor block**

In `_chat_inner()`, replace parsing, modality execution, Hebbian step, and finalization with:

```python
completed_response = await self._complete_actor_response(
    user_message,
    single_response.content,
    context,
    drive_satisfaction,
    reward,
    is_proactive=is_proactive,
)

result = {
    "reply": completed_response.reply,
    "modality": completed_response.modality,
}
for key in ("image_path", "audio_path", "segments", "delays_ms"):
    if completed_response.outputs.get(key):
        result[key] = completed_response.outputs[key]
return result
```

- [x] **Step 3: Replace stream post-Actor block**

In `chat_stream()`, after collecting `raw_text`, call:

```python
await self._complete_actor_response(
    user_message,
    raw_text,
    context,
    drive_satisfaction,
    reward,
)
```

- [x] **Step 4: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_response_runtime.py tests/test_modality_execution.py tests/test_turn_finalization.py tests/test_websocket_chat_service.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/response_runtime.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_response_runtime.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/response_runtime.py agent/chat_agent.py`

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

- Spec coverage: The plan extracts only duplicated post-Actor runtime behavior and keeps entry point behavior unchanged.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `CompletedActorResponse`, `AgentResponseRuntimeMixin`, and `_complete_actor_response()` are named consistently across tests and implementation.
