# Memory Injection Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move duplicated ChatAgent Step 8.5 prompt memory injection out of `chat_agent.py` into a focused mixin shared by normal and streamed chat turns.

**Architecture:** Add `agent/memory_injection.py` with `MemoryInjectionMixin._inject_memory_context()`. The method owns collecting pending EverMemOS search results, blending relevant/static memories with existing budget helpers, appending localized prompt sections, and incrementing relevant-injection metrics. `ChatAgent._chat_inner()` and `ChatAgent.chat_stream()` will delegate to the new boundary while preserving prompt content and counters.

**Tech Stack:** Python 3.11+, pytest, pyright, existing ChatAgent mixin style.

---

### Task 1: Lock Memory Injection Behavior With Failing Tests

**Files:**
- Create: `tests/test_memory_injection.py`

- [x] **Step 1: Write the failing tests**

```python
import asyncio
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def make_agent(lang="zh"):
    spec = importlib.util.find_spec("agent.memory_injection")
    assert spec is not None
    module = importlib.import_module("agent.memory_injection")

    class DummyAgent(module.MemoryInjectionMixin):
        def __init__(self):
            self._session_ctx = SimpleNamespace(has_history=True)
            self.persona = SimpleNamespace(lang=lang)
            self.user_name = "Codex"
            self._relevant_facts = "fresh facts"
            self._user_profile = "static profile"
            self._relevant_episodes = "fresh episodes"
            self._episode_summary = "static episode"
            self._foresight_text = "bring umbrella"
            self._relevant_profile = "likes concise answers"
            self._search_relevant_used = 0
            self.collect_calls = 0

        async def _collect_search_results(self):
            self.collect_calls += 1

        def _memory_injection_budget(self, context):
            return 100, 80

        def _blend_injection(self, relevant, static, budget):
            return f"{relevant}|{static}|{budget}"

    return DummyAgent()


def test_memory_injection_appends_chinese_sections_and_counts_relevant_use():
    agent = make_agent(lang="zh")

    prompt = asyncio.run(agent._inject_memory_context("BASE", {"conversation_depth": 0.5}))

    assert prompt.startswith("BASE")
    assert "[关于Codex的偏好] fresh facts|static profile|100" in prompt
    assert "[与Codex过去发生的事] fresh episodes|static episode|80" in prompt
    assert "[近期值得关心] bring umbrella" in prompt
    assert "[Codex的画像] likes concise answers" in prompt
    assert agent.collect_calls == 1
    assert agent._search_relevant_used == 1


def test_memory_injection_appends_english_sections():
    agent = make_agent(lang="en")

    prompt = asyncio.run(agent._inject_memory_context("BASE", {"conversation_depth": 0.5}))

    assert "[Codex's preferences] fresh facts|static profile|100" in prompt
    assert "[Past interactions with Codex] fresh episodes|static episode|80" in prompt
    assert "[Worth noting] bring umbrella" in prompt
    assert "[Codex's profile] likes concise answers" in prompt


def test_memory_injection_skips_when_session_has_no_history():
    agent = make_agent(lang="zh")
    agent._session_ctx = SimpleNamespace(has_history=False)

    prompt = asyncio.run(agent._inject_memory_context("BASE", {"conversation_depth": 0.5}))

    assert prompt == "BASE"
    assert agent.collect_calls == 0
    assert agent._search_relevant_used == 0


def test_chat_agent_delegates_memory_injection_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.memory_injection import MemoryInjectionMixin" in source
    assert "MemoryInjectionMixin" in source
    assert source.count("_inject_memory_context(") == 2
    assert "await self._collect_search_results()" not in source
    assert "[关于{name}的偏好]" not in source
    assert "[Past interactions with {name}]" not in source
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_memory_injection.py -q`

Expected: FAIL because `agent.memory_injection` does not exist and `ChatAgent` still has inline memory injection.

### Task 2: Add MemoryInjectionMixin

**Files:**
- Create: `agent/memory_injection.py`
- Test: `tests/test_memory_injection.py`

- [x] **Step 1: Implement the mixin**

Create `agent/memory_injection.py` with a protocol-typed host and:

```python
class MemoryInjectionMixin:
    async def _inject_memory_context(self, prompt: str, context: dict) -> str:
        host = cast(_MemoryInjectionHost, self)
        if not host._session_ctx or not host._session_ctx.has_history:
            return prompt

        await host._collect_search_results()
        profile_budget, episode_budget = host._memory_injection_budget(context)
        profile_text = host._blend_injection(
            host._relevant_facts,
            host._user_profile,
            profile_budget,
        )
        episode_text = host._blend_injection(
            host._relevant_episodes,
            host._episode_summary,
            episode_budget,
        )
        name = host.user_name or "你"
        sections = _memory_sections(
            lang=host.persona.lang,
            name=name,
            profile_text=profile_text,
            episode_text=episode_text,
            foresight_text=host._foresight_text,
            relevant_profile=host._relevant_profile,
        )
        if host._relevant_facts or host._relevant_episodes or host._relevant_profile:
            host._search_relevant_used += 1
        return prompt + "".join(sections)
```

The helper `_memory_sections()` should return localized `\n\n[...] ...` section strings.

- [x] **Step 2: Run the new tests**

Run: `.venv/bin/python -m pytest tests/test_memory_injection.py -q`

Expected: the behavior tests pass; the ChatAgent delegation test still fails until Task 3.

### Task 3: Delegate ChatAgent Step 8.5

**Files:**
- Modify: `agent/chat_agent.py`
- Test: `tests/test_memory_injection.py`
- Test: `tests/test_bilingual_parser.py`

- [x] **Step 1: Import and inherit the mixin**

Add:

```python
from agent.memory_injection import MemoryInjectionMixin
```

Add `MemoryInjectionMixin` to the `ChatAgent` base class list.

- [x] **Step 2: Replace both inline Step 8.5 blocks**

In `_chat_inner`, replace the inline memory injection block with:

```python
single_prompt = await self._inject_memory_context(single_prompt, context)
```

In `chat_stream`, replace the matching inline memory injection block with the same call.

- [x] **Step 3: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_memory_injection.py tests/test_bilingual_parser.py tests/test_modality_execution.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification

**Files:**
- Verify: `agent/memory_injection.py`
- Verify: `agent/chat_agent.py`
- Verify: `tests/test_memory_injection.py`

- [x] **Step 1: Run static checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 2: Run compile check**

Run: `.venv/bin/python -m py_compile agent/memory_injection.py agent/chat_agent.py`

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

- Spec coverage: The plan covers shared normal/stream ChatAgent memory injection, localization, metrics, and no-history bypass.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `_inject_memory_context`, `MemoryInjectionMixin`, and `_memory_sections` are named consistently across tests and implementation.
