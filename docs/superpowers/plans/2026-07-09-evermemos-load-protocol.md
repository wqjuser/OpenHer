# EverMemOS Load Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move session-load memory type mapping and legacy list body construction into `protocol.py`.

**Architecture:** Reuse `providers/memory/evermemos/protocol.py`; no new module.

**Tech Stack:** Python 3.11+, pytest, pyright.

## Global Constraints

- Do not change `EverMemOSClient` public methods.
- Do not change session-load route order.
- Keep network calls mocked.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `tests/test_evermemos_protocol.py`

- [x] **Step 1: Add exact protocol assertions**

Test `load_memory_v1_type`, `load_memory_collection_key`, and `build_legacy_list_body`.

- [x] **Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_evermemos_protocol.py -v
```

Expected: FAIL because the helpers do not exist yet.

### Task 2: Implement And Use Helpers

**Files:**
- Modify: `providers/memory/evermemos/protocol.py`
- Modify: `providers/memory/evermemos/evermemos_client.py`

- [x] **Step 1: Add helpers**

Add the pure helpers to `protocol.py`.

- [x] **Step 2: Replace inline client logic**

Use the helpers inside `load_session_context`.

- [x] **Step 3: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_evermemos_protocol.py tests/test_evermemos_projection.py tests/test_security_regressions.py::EverMemOSLoggingRegressionTests -v
```

Expected: PASS.

### Task 3: Verify And Ship

- [x] **Step 1: Mark completed steps**

Update this plan.

- [x] **Step 2: Run gates**

Run:

```bash
make check
make doctor backend-acceptance-smoke backend-runtime-smoke backend-chat-smoke desktop-acceptance-smoke desktop-build
```

Expected: all commands exit 0. Optional doctor warnings are acceptable.

- [x] **Step 3: Commit and push**

Run:

```bash
git add docs/superpowers/specs/2026-07-09-evermemos-load-protocol-design.md docs/superpowers/plans/2026-07-09-evermemos-load-protocol.md providers/memory/evermemos/protocol.py providers/memory/evermemos/evermemos_client.py tests/test_evermemos_protocol.py
git commit -m "refactor: centralize evermemos load protocol"
git push origin main
```
