# Agent Critic Context Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Critic perception setup and relationship-context merge out of `ChatAgent` into a focused mixin.

**Architecture:** Add `agent/critic_context.py` with `AgentCriticContextMixin`. The mixin will build the rounded drive-frustration input, build the persona-aware Critic hint, call `critic_sense()`, apply relationship EMA, merge the 12D context, store `_last_critic`, and return the data needed by the rest of the turn. `ChatAgent` will call one helper from both normal and streaming paths.

**Tech Stack:** Python 3.11+, pytest, pyright, existing ChatAgent mixin pattern.

---

### Task 1: Lock Critic Context Behavior With Failing Tests

**Files:**
- Create: `tests/test_critic_context.py`
- Verify: `agent/chat_agent.py`

- [x] **Step 1: Write the failing tests**

Create tests that assert:
- `_sense_critic_context()` rounds drive frustration, builds the persona hint from name, MBTI, and the first three tags, calls `critic_sense()` with user profile and episode summary, applies relationship EMA using conversation depth, merges the relationship context, stores `_last_critic`, and returns context, frustration delta, and drive satisfaction.
- `_sense_critic_context()` falls back to `未知` MBTI and omits the tag suffix when no tags exist.
- `ChatAgent` imports and inherits `AgentCriticContextMixin`, no longer imports `critic_sense` directly, and no longer contains the inline `_persona_hint` Critic setup.

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_critic_context.py -q`

Expected: FAIL because `agent.critic_context` does not exist and `ChatAgent` still owns the duplicated Critic setup.

### Task 2: Add AgentCriticContextMixin

**Files:**
- Create: `agent/critic_context.py`
- Test: `tests/test_critic_context.py`

- [x] **Step 1: Implement `agent/critic_context.py`**

Add `AgentCriticContextMixin` with:

```python
async def _sense_critic_context(
    self,
    user_message: str,
    relationship_prior: dict[str, float],
) -> tuple[dict[str, Any], dict[str, float], dict[str, float]]:
    ...
```

The helper preserves existing behavior:
- Build `frust_dict` from `DRIVES` and `host.metabolism.frustration`, rounded to two decimals.
- Build persona hint as `"{name} ({mbti}) — {tag1、tag2、tag3}"` when tags exist.
- Build persona hint as `"{name} ({mbti})"` when tags are empty.
- Use `未知` when MBTI is missing.
- Pass `user_profile`, `episode_summary`, and `persona_hint` to `critic_sense()`.
- Apply `_apply_relationship_ema(relationship_prior, rel_delta, context.get("conversation_depth", 0.0))`.
- Merge returned relationship values into context.
- Store the merged context on `_last_critic`.
- Return `(context, frustration_delta, drive_satisfaction)`.

- [x] **Step 2: Run critic context tests**

Run: `.venv/bin/python -m pytest tests/test_critic_context.py -q`

Expected: behavior tests pass; the ChatAgent delegation test still fails until Task 3.

### Task 3: Delegate ChatAgent Critic Context

**Files:**
- Modify: `agent/chat_agent.py`
- Test: `tests/test_critic_context.py`
- Test: `tests/test_relationship.py`
- Test: `tests/test_websocket_chat_service.py`

- [x] **Step 1: Import and inherit the mixin**

Add `from agent.critic_context import AgentCriticContextMixin` to `agent/chat_agent.py`.

Add `AgentCriticContextMixin` to the `ChatAgent` base class list near the other lifecycle mixins.

- [x] **Step 2: Replace inline Critic blocks**

Replace both inline Critic setup blocks with:

```python
context, frustration_delta, drive_satisfaction = await self._sense_critic_context(
    user_message,
    relationship_prior,
)
```

Remove the now-unused direct `critic_sense` and top-level `DRIVES` imports from `agent/chat_agent.py`.

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_critic_context.py tests/test_relationship.py tests/test_websocket_chat_service.py tests/test_agent_status.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/critic_context.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_critic_context.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/critic_context.py agent/chat_agent.py`

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

- Spec coverage: The plan preserves Critic sensing and relationship merge behavior while moving it out of `ChatAgent`.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `AgentCriticContextMixin` and `_sense_critic_context()` are named consistently across tests and implementation.
