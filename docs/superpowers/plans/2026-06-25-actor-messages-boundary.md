# Agent Actor Messages Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Actor prompt preparation and ChatMessage assembly out of `ChatAgent` into a focused mixin.

**Architecture:** Add `agent/actor_messages.py` with `AgentActorMessagesMixin`. The mixin will compute genome signals, apply thermodynamic noise, update signal state, retrieve few-shot style memories, build the single-pass Actor prompt, inject EverMemOS context, and assemble the final LLM messages. `ChatAgent` will call one helper from both normal and streaming paths.

**Tech Stack:** Python 3.11+, pytest, pyright, existing ChatAgent mixin pattern.

---

### Task 1: Lock Actor Message Preparation With Failing Tests

**Files:**
- Create: `tests/test_actor_messages.py`
- Verify: `agent/chat_agent.py`

- [x] **Step 1: Write the failing tests**

Create tests that assert:
- `_prepare_actor_messages()` computes signals from the Critic context, applies thermodynamic noise, updates `_prev_signals` and `_last_signals`, sets the style-memory clock, asks style memory for three full examples in the persona language, calls `_build_single_prompt()` with the modality skill engine, injects memory context, and returns `[system prompt] + recent history + [current user message]`.
- `_prepare_actor_messages()` respects `max_history` when assembling the LLM messages.
- `ChatAgent` imports and inherits `AgentActorMessagesMixin`, and no longer contains inline few-shot prompt/message assembly.

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_actor_messages.py -q`

Expected: FAIL because `agent.actor_messages` does not exist and `ChatAgent` still owns the duplicated Actor message preparation blocks.

### Task 2: Add AgentActorMessagesMixin

**Files:**
- Create: `agent/actor_messages.py`
- Test: `tests/test_actor_messages.py`

- [x] **Step 1: Implement `agent/actor_messages.py`**

Add `AgentActorMessagesMixin` with:

```python
async def _prepare_actor_messages(
    self,
    user_message: str,
    context: dict[str, Any],
    now: float,
) -> list[ChatMessage]:
    ...
```

The helper preserves existing behavior:
- Compute base signals via `agent.compute_signals(context)`.
- Apply thermodynamic noise via `metabolism.apply_thermodynamic_noise(base_signals)`.
- Set `_prev_signals` to the previous `_last_signals`, then set `_last_signals` to the noisy signals.
- Set the style-memory clock to `now`.
- Build few-shot examples using `top_k=3`, `monologue_only=False`, and `persona.lang`.
- Build the Actor prompt via `_build_single_prompt(few_shot, noisy_signals, modality_skill_engine=modality_skill_engine)`.
- Inject memory context via `_inject_memory_context(single_prompt, context)`.
- Return the system prompt, the last `max_history` history messages, and the current user message.

- [x] **Step 2: Run actor message tests**

Run: `.venv/bin/python -m pytest tests/test_actor_messages.py -q`

Expected: behavior tests pass; the ChatAgent delegation test still fails until Task 3.

### Task 3: Delegate ChatAgent Actor Message Preparation

**Files:**
- Modify: `agent/chat_agent.py`
- Test: `tests/test_actor_messages.py`
- Test: `tests/test_memory_injection.py`
- Test: `tests/test_websocket_chat_service.py`

- [x] **Step 1: Import and inherit the mixin**

Add `from agent.actor_messages import AgentActorMessagesMixin` to `agent/chat_agent.py`.

Add `AgentActorMessagesMixin` to the `ChatAgent` base class list near the other lifecycle mixins.

- [x] **Step 2: Replace inline message-preparation blocks**

Replace both inline signal/few-shot/prompt/message assembly blocks with:

```python
single_messages = await self._prepare_actor_messages(user_message, context, now)
```

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_actor_messages.py tests/test_memory_injection.py tests/test_websocket_chat_service.py tests/test_agent_status.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/actor_messages.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_actor_messages.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/actor_messages.py agent/chat_agent.py`

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

- Spec coverage: The plan preserves Actor message preparation while moving it out of `ChatAgent`.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `AgentActorMessagesMixin` and `_prepare_actor_messages()` are named consistently across tests and implementation.
