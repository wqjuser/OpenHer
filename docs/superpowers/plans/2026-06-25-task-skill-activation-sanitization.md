# Task Skill Activation Sanitization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent blank task-skill activation responses from being logged as unknown skills and normalize valid activation ids before lookup.

**Architecture:** Keep the existing prompt-driven ReAct loop in `TaskSkillEngine`, but add one small normalization boundary for skill ids emitted by the LLM. Empty or non-string activation values will be treated the same as "no skill needed"; non-empty ids will be stripped and lowercased before lookup, activation, and legacy `execute()` use.

**Tech Stack:** Python 3.11+, pytest, existing `TaskSkillEngine` ReAct tests.

---

### Task 1: Lock Blank And Whitespace Activation Behavior With Failing Tests

**Files:**
- Modify: `tests/test_skill_engine.py`
- Verify: `agent/skills/task_skill_engine.py`

- [x] **Step 1: Add blank activation regression test**

In `TestReactLoop`, add a test whose mock LLM returns:

```python
ChatResponse(content='{"activate": "", "thought": "no tool"}')
```

Call:

```python
result = await engine.react_loop("随便聊聊", MockLLM())
captured = capsys.readouterr()
```

Assert:
- `result is None`;
- `"Unknown skill"` is not in `captured.out`.

- [x] **Step 2: Add whitespace/case normalization test**

In `TestReactLoop`, add a test whose first mock response is:

```python
{"activate": " WEATHER ", "thought": "用户问天气"}
```

Then return an execute action and finally `{"done": true}`. Assert the weather skill executes and the observation contains `Beijing: 22C`.

- [x] **Step 3: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_skill_engine.py::TestReactLoop -q`

Expected: FAIL because blank activate logs `Unknown skill` and whitespace activation does not resolve to `weather`.

### Task 2: Add Skill Id Normalization Boundary

**Files:**
- Modify: `agent/skills/task_skill_engine.py`
- Test: `tests/test_skill_engine.py`

- [x] **Step 1: Implement `_normalize_skill_id()`**

Add:

```python
@staticmethod
def _normalize_skill_id(raw_skill_id: object) -> Optional[str]:
    if not isinstance(raw_skill_id, str):
        return None
    skill_id = raw_skill_id.strip().lower()
    return skill_id or None
```

- [x] **Step 2: Use normalization in `react_loop()`**

Replace:

```python
skill_id = parsed["activate"].lower()
```

with:

```python
skill_id = self._normalize_skill_id(parsed.get("activate"))
if not skill_id:
    break
```

Then use the normalized `skill_id` for lookup and activation.

- [x] **Step 3: Use normalization in legacy `execute()`**

Replace:

```python
skill_id = skill_id.lower()
```

with:

```python
normalized_skill_id = self._normalize_skill_id(skill_id)
skill_id = normalized_skill_id or ""
```

Preserve the existing unknown-skill `SkillExecutionResult` behavior for blank direct `execute()` calls.

- [x] **Step 4: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_skill_engine.py -q`

Expected: all SkillEngine tests pass.

### Task 3: Full Verification And Release

**Files:**
- Verify: `agent/skills/task_skill_engine.py`
- Verify: `tests/test_skill_engine.py`

- [x] **Step 1: Run static and compile checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

Run: `.venv/bin/python -m py_compile agent/skills/task_skill_engine.py tests/test_skill_engine.py`

Expected: exit code 0.

- [x] **Step 2: Run full tests**

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: full suite passes with the known skipped WebSocket integration test unchanged.

- [x] **Step 3: Run repository hygiene checks**

Run: `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0.

- [x] **Step 4: Run service smoke**

Start: `PORT=8782 ./run.sh`

Check:
- `GET /api/status`;
- WebSocket `demo_presets`;
- `POST /api/chat`.

Expected: backend starts and the REST chat path still returns a normal response through the configured provider.

- [x] **Step 5: Commit, merge, and push**

Run:

```bash
git add agent/skills/task_skill_engine.py tests/test_skill_engine.py docs/superpowers/plans/2026-06-25-task-skill-activation-sanitization.md
git commit -m "fix: sanitize task skill activation ids"
git switch main
git pull --ff-only
git merge --no-ff codex/task-skill-activation-sanitization -m "merge: task skill activation sanitization"
git push origin main
```

### Self-Review

- Spec coverage: The plan addresses the observed blank `Unknown skill` runtime noise and improves normalization for valid skill ids.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `_normalize_skill_id()`, `react_loop()`, and `execute()` use the same normalized id semantics.
