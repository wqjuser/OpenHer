# Agent Turn Pipeline Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the shared pre-Actor turn lifecycle out of `ChatAgent` into a focused pipeline mixin.

**Architecture:** Add `agent/turn_pipeline.py` with `AgentTurnPipelineMixin` and a `PreparedTurn` dataclass. The mixin will run task skills, begin the turn, gather EverMemOS relationship prior, apply time metabolism, sense Critic context, compute reward, sync metabolism to the genome agent, evolve drive lifecycle, and prepare Actor messages. `ChatAgent` will call this helper from both normal and streaming paths.

**Tech Stack:** Python 3.11+, pytest, pyright, existing ChatAgent mixin pattern.

---

### Task 1: Lock Shared Turn Preparation With Failing Tests

**Files:**
- Create: `tests/test_turn_pipeline.py`
- Verify: `agent/chat_agent.py`

- [x] **Step 1: Write the failing tests**

Create tests that assert:
- `_prepare_turn_for_actor()` calls task skills, turn start, EverMemOS gather, time metabolism, Critic context, reward calculation, genome sync, drive baseline evolution, crystallization, and Actor message preparation in the same order as the current chat lifecycle.
- `_prepare_turn_for_actor()` returns the skill-processed user message, now timestamp, merged context, frustration delta, drive satisfaction, reward, and Actor messages.
- `_prepare_turn_for_actor()` stores `_last_reward`.
- `ChatAgent` imports and inherits `AgentTurnPipelineMixin`, and no longer contains the inline shared pre-Actor lifecycle calls.

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_turn_pipeline.py -q`

Expected: FAIL because `agent.turn_pipeline` does not exist and `ChatAgent` still owns the duplicated pre-Actor lifecycle.

### Task 2: Add AgentTurnPipelineMixin

**Files:**
- Create: `agent/turn_pipeline.py`
- Test: `tests/test_turn_pipeline.py`

- [x] **Step 1: Implement `agent/turn_pipeline.py`**

Add:

```python
@dataclass
class PreparedTurn:
    user_message: str
    now: float
    context: dict[str, Any]
    frustration_delta: dict[str, float]
    drive_satisfaction: dict[str, float]
    reward: float
    actor_messages: list[ChatMessage]
```

Add:

```python
async def _prepare_turn_for_actor(self, user_message: str) -> PreparedTurn:
    ...
```

The helper preserves existing behavior:
- Run `_run_task_skills()`.
- Run `_begin_turn()`.
- Run `_evermemos_gather()`.
- Run `metabolism.time_metabolism(now)`.
- Run `_sense_critic_context(user_message, relationship_prior)`.
- Run `metabolism.apply_llm_delta(frustration_delta)`.
- Run `metabolism.sync_to_agent(agent)`.
- Store `_last_reward`.
- Run `_evolve_drive_baseline(frustration_delta)`.
- Run `_crystallize_last_action_if_needed(reward, context, now)`.
- Run `_prepare_actor_messages(user_message, context, now)`.
- Return `PreparedTurn`.

- [x] **Step 2: Run turn pipeline tests**

Run: `.venv/bin/python -m pytest tests/test_turn_pipeline.py -q`

Expected: behavior tests pass; the ChatAgent delegation test still fails until Task 3.

### Task 3: Delegate ChatAgent Shared Turn Preparation

**Files:**
- Modify: `agent/chat_agent.py`
- Test: `tests/test_turn_pipeline.py`
- Test: `tests/test_actor_messages.py`
- Test: `tests/test_critic_context.py`

- [x] **Step 1: Import and inherit the mixin**

Add `from agent.turn_pipeline import AgentTurnPipelineMixin` to `agent/chat_agent.py`.

Add `AgentTurnPipelineMixin` to the `ChatAgent` base class list near the other lifecycle mixins.

- [x] **Step 2: Replace inline shared lifecycle blocks**

Replace the duplicated pre-Actor setup in both `_chat_inner()` and `chat_stream()` with:

```python
prepared_turn = await self._prepare_turn_for_actor(user_message)
user_message = prepared_turn.user_message
context = prepared_turn.context
drive_satisfaction = prepared_turn.drive_satisfaction
reward = prepared_turn.reward
single_messages = prepared_turn.actor_messages
```

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_turn_pipeline.py tests/test_actor_messages.py tests/test_critic_context.py tests/test_websocket_chat_service.py tests/test_agent_status.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/turn_pipeline.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_turn_pipeline.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/turn_pipeline.py agent/chat_agent.py`

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

- Spec coverage: The plan preserves shared pre-Actor lifecycle behavior while moving it out of `ChatAgent`.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `AgentTurnPipelineMixin`, `PreparedTurn`, and `_prepare_turn_for_actor()` are named consistently across tests and implementation.
