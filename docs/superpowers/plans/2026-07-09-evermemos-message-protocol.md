# EverMemOS Message Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move remaining EverMemOS message and health fallback request shapes into `protocol.py`.

**Architecture:** Reuse the existing `providers/memory/evermemos/protocol.py` module. Do not add a new storage service; the client keeps side effects.

**Tech Stack:** Python 3.11+, pytest, pyright.

## Global Constraints

- Do not change `EverMemOSClient` public method signatures.
- Do not change route order or fallback behavior.
- Keep provider and network calls mocked.

---

### Task 1: Add Protocol Tests

**Files:**
- Modify: `tests/test_evermemos_protocol.py`

**Interfaces:**
- Produces tests for `build_oss_health_search_body`, `build_memory_flush_body`, `build_turn_messages`, `build_proactive_messages`, and `build_session_flush_messages`.

- [x] **Step 1: Write failing tests**

Add exact payload assertions for the new protocol builders.

- [x] **Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_evermemos_protocol.py -v
```

Expected: FAIL because the builders do not exist yet.

### Task 2: Implement Builders And Use Them

**Files:**
- Modify: `providers/memory/evermemos/protocol.py`
- Modify: `providers/memory/evermemos/evermemos_client.py`

**Interfaces:**
- Produces:
  - `build_oss_health_search_body() -> dict[str, object]`
  - `build_memory_flush_body(user_id: str, group_id: str) -> dict[str, object]`
  - `build_turn_messages(...) -> list[dict[str, object]]`
  - `build_proactive_messages(...) -> list[dict[str, object]]`
  - `build_session_flush_messages(persona_id: str, timestamp_ms: int) -> list[dict[str, object]]`

- [x] **Step 1: Implement pure builders**

Add the functions to `protocol.py`.

- [x] **Step 2: Refactor client call sites**

Replace inline dictionaries in `verify_connection`, `_post_memories`, `store_turn`, `store_proactive_turn`, and `close_session`.

- [x] **Step 3: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_evermemos_protocol.py tests/test_security_regressions.py::EverMemOSLoggingRegressionTests -v
```

Expected: PASS.

### Task 3: Verify, Commit, Push

**Files:**
- Modify: `docs/superpowers/plans/2026-07-09-evermemos-message-protocol.md`

- [x] **Step 1: Mark completed steps**

Update this plan with completed checkboxes.

- [x] **Step 2: Run gates**

Run:

```bash
make check
make doctor backend-acceptance-smoke backend-runtime-smoke backend-chat-smoke desktop-acceptance-smoke desktop-build
```

Expected: all commands exit 0. Optional doctor warnings are acceptable.

- [ ] **Step 3: Commit and push**

Run:

```bash
git add docs/superpowers/specs/2026-07-09-evermemos-message-protocol-design.md docs/superpowers/plans/2026-07-09-evermemos-message-protocol.md providers/memory/evermemos/protocol.py providers/memory/evermemos/evermemos_client.py tests/test_evermemos_protocol.py
git commit -m "refactor: centralize evermemos message builders"
git push origin main
```
