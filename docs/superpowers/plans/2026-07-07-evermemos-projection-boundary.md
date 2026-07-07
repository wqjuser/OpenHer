# EverMemOS Projection Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract EverMemOS response projection from the async HTTP client into pure tested helpers.

**Architecture:** Add `providers/memory/evermemos/projection.py` for deterministic conversion from raw EverMemOS memory records to `SessionContext`, relevant-memory snippets, and relationship priors. Keep `EverMemOSClient` responsible for requests, fallback execution, logging, errors, and circuit breaker state.

**Tech Stack:** Python 3.11+, dataclasses, pytest, pyright.

## Global Constraints

- Do not change `EverMemOSClient` public method signatures.
- Do not change HTTP route order, payload shapes, or fallback behavior.
- Keep provider, memory, and network calls mocked in tests.
- Preserve configured item limits and current Chinese snippet formatting.

---

### Task 1: Add Projection Boundary Tests

**Files:**
- Create: `tests/test_evermemos_projection.py`
- Modify: `tests/test_evermemos_modules.py`

**Interfaces:**
- Consumes: expected module path `providers.memory.evermemos.projection`.
- Produces: tests for `empty_session_context`, `flatten_memory_results`, `build_session_context_from_memories`, `extract_search_memories`, `build_relevant_memory_projection`, and `relationship_vector_from_context`.

- [x] **Step 1: Write failing projection tests**

Create tests that import `providers.memory.evermemos.projection` and assert exact outputs for session context aggregation, search response flattening, relevant-memory snippets, and relationship vector values.

- [x] **Step 2: Update support module boundary tests**

Update `tests/test_evermemos_modules.py` to require the projection module and assert the client imports from it.

- [x] **Step 3: Run red tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_evermemos_projection.py tests/test_evermemos_modules.py -v
```

Expected: FAIL because `providers.memory.evermemos.projection` does not exist and the client does not import it yet.

### Task 2: Implement Projection Module

**Files:**
- Create: `providers/memory/evermemos/projection.py`

**Interfaces:**
- Produces:
  - `RelevantMemoryProjection`
  - `empty_session_context() -> SessionContext`
  - `flatten_memory_results(results: Iterable[Mapping[str, Any] | None]) -> list[Mapping[str, Any]]`
  - `build_session_context_from_memories(memories: Iterable[Mapping[str, Any]], config: Mapping[str, Any]) -> SessionContext`
  - `extract_search_memories(data: Mapping[str, Any]) -> list[Mapping[str, Any]]`
  - `build_relevant_memory_projection(memories: Iterable[Mapping[str, Any]], config: Mapping[str, Any]) -> RelevantMemoryProjection`
  - `relationship_vector_from_context(ctx: SessionContext) -> dict[str, float]`

- [x] **Step 1: Add pure projection helpers**

Implement the helpers by moving the existing profile, fact, episode, foresight, depth, pending foresight, search-memory flattening, and relevant snippet logic out of `EverMemOSClient`.

- [x] **Step 2: Run projection tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_evermemos_projection.py -v
```

Expected: PASS.

### Task 3: Refactor Client To Use Projection Helpers

**Files:**
- Modify: `providers/memory/evermemos/evermemos_client.py`
- Modify: `tests/test_evermemos_modules.py`

**Interfaces:**
- Consumes: projection helpers from Task 2.
- Produces: same public `EverMemOSClient` behavior with deterministic projection delegated.

- [x] **Step 1: Replace inline session context projection**

Update `load_session_context` to use `empty_session_context`, `flatten_memory_results`, and `build_session_context_from_memories`.

- [x] **Step 2: Replace inline relationship projection**

Update `relationship_vector` to delegate to `relationship_vector_from_context`.

- [x] **Step 3: Replace inline search projection**

Update `search_relevant_memories` to use `extract_search_memories` and `build_relevant_memory_projection`.

- [x] **Step 4: Run EverMemOS focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_evermemos_projection.py tests/test_evermemos_modules.py tests/test_security_regressions.py::EverMemOSLoggingRegressionTests -v
```

Expected: PASS.

### Task 4: Verify, Commit, Push

**Files:**
- Modify: `docs/superpowers/plans/2026-07-07-evermemos-projection-boundary.md`

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
git add docs/superpowers/specs/2026-07-07-evermemos-projection-boundary-design.md docs/superpowers/plans/2026-07-07-evermemos-projection-boundary.md providers/memory/evermemos/projection.py providers/memory/evermemos/evermemos_client.py tests/test_evermemos_projection.py tests/test_evermemos_modules.py
git commit -m "refactor: extract evermemos projection helpers"
git push origin main
```
