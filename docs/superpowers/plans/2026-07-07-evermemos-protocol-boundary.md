# EverMemOS Protocol Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract EverMemOS request payload and route rules into a pure protocol module.

**Architecture:** Add `providers/memory/evermemos/protocol.py` for request-shape builders. Keep `EverMemOSClient` responsible for side effects, fallback execution, response parsing, logging, and circuit breaker updates.

**Tech Stack:** Python 3.11+, pytest, pyright, httpx-compatible async client stubs.

## Global Constraints

- Do not change EverMemOS runtime behavior or public method signatures.
- Keep provider, memory, and network calls mocked in tests.
- Preserve official cloud search payload shape: `filters`, `query`, `method`, `top_k`.
- Preserve OSS and legacy fallback route order.

---

### Task 1: Add Protocol Boundary Tests

**Files:**
- Create: `tests/test_evermemos_protocol.py`
- Modify: `tests/test_evermemos_modules.py`

**Interfaces:**
- Consumes: expected protocol module path `providers.memory.evermemos.protocol`.
- Produces: tests for `build_memory_batch_body`, `build_legacy_memory_payload`, `build_cloud_search_body`, `build_oss_search_body`, `build_legacy_search_body`, `build_health_search_body`, and memory get builders.

- [x] **Step 1: Write failing protocol payload tests**

Create tests that import the protocol module and assert exact payloads for official search, OSS search fallback, legacy search fallback, batch storage, legacy storage, health check, v1 get, and compatibility get.

- [x] **Step 2: Update module boundary test**

Update `tests/test_evermemos_modules.py` to require `providers.memory.evermemos.protocol` and assert `EverMemOSClient` imports its builders.

- [x] **Step 3: Run red tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_evermemos_protocol.py tests/test_evermemos_modules.py -v
```

Expected: FAIL because `providers.memory.evermemos.protocol` does not exist.

### Task 2: Implement Protocol Module

**Files:**
- Create: `providers/memory/evermemos/protocol.py`

**Interfaces:**
- Produces pure functions:
  - `normalize_search_method(retrieve_method: str) -> str`
  - `search_top_k(config: Mapping[str, Any]) -> int`
  - `build_health_search_body() -> dict[str, object]`
  - `build_cloud_search_body(query: str, user_id: str, method: str, top_k: int) -> dict[str, object]`
  - `build_oss_search_body(query: str, user_id: str, group_id: str, method: str, top_k: int) -> dict[str, object]`
  - `build_legacy_search_body(query: str, user_id: str, group_id: str, retrieve_method: str) -> dict[str, object]`
  - `build_memory_batch_body(user_id: str, group_id: str, messages: list[dict[str, object]]) -> dict[str, object]`
  - `build_legacy_memory_payload(user_id: str, group_id: str, message: Mapping[str, Any], flush: bool, message_id: str | None = None) -> dict[str, object]`
  - `build_v1_get_body(user_id: str, memory_type: str, page_size: int = 20) -> dict[str, object]`
  - `build_compat_get_body(user_id: str, memory_type: str, page_size: int = 20) -> dict[str, object]`

- [x] **Step 1: Add pure builders**

Implement the protocol functions with constants `APP_ID = "openher"`, `PROJECT_ID = "openher"`, `STORE_PATHS = ("/memories", "/memory/add")`, and `GET_PATHS = ("/memory/get", "/memories/get")`.

- [x] **Step 2: Run protocol tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_evermemos_protocol.py -v
```

Expected: PASS.

### Task 3: Refactor Client To Use Protocol Builders

**Files:**
- Modify: `providers/memory/evermemos/evermemos_client.py`
- Modify: `tests/test_evermemos_modules.py`

**Interfaces:**
- Consumes: protocol functions from Task 2.
- Produces: same `EverMemOSClient` public behavior with request construction delegated to protocol builders.

- [x] **Step 1: Replace inline health/search/store/get bodies**

Update `EverMemOSClient` imports and replace inline dictionaries with calls to protocol builders.

- [x] **Step 2: Run EverMemOS focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_evermemos_protocol.py tests/test_evermemos_modules.py tests/test_security_regressions.py::EverMemOSLoggingRegressionTests -v
```

Expected: PASS.

### Task 4: Verify, Commit, Push

**Files:**
- Modify: `docs/superpowers/plans/2026-07-07-evermemos-protocol-boundary.md`

**Interfaces:**
- Produces: committed and pushed `main`.

- [x] **Step 1: Mark completed checkboxes**

Update this plan with completed steps.

- [x] **Step 2: Run repository gates**

Run:

```bash
make check
make doctor backend-acceptance-smoke backend-runtime-smoke backend-chat-smoke desktop-acceptance-smoke desktop-build
```

Expected: all commands exit 0. `make doctor` may report optional warnings for unconfigured optional providers or backups.

- [ ] **Step 3: Commit and push**

Run:

```bash
git add docs/superpowers/specs/2026-07-07-evermemos-protocol-boundary-design.md docs/superpowers/plans/2026-07-07-evermemos-protocol-boundary.md providers/memory/evermemos/protocol.py providers/memory/evermemos/evermemos_client.py tests/test_evermemos_protocol.py tests/test_evermemos_modules.py
git commit -m "refactor: extract evermemos protocol builders"
git push origin main
```
