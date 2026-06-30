# Backend Live Chat Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional live backend chat smoke that validates one real `/api/chat` turn, session status, and display history through a temporary runtime data directory.

**Architecture:** Reuse `backend_runtime_smoke` for uvicorn lifecycle, auth, JSON GETs, readiness, formatting, and temp `OPENHER_DATA_DIR`. Add a focused `backend_chat_smoke.py` for POST `/api/chat`, skip-on-chat-unavailable behavior, session status verification, and persisted history assertions. Expose it through Makefile, compile gates, README, and tests.

**Tech Stack:** Python 3.11+, urllib, FastAPI/Uvicorn live process, pytest, Makefile.

---

### Task 1: Script Contract Tests

**Files:**
- Create: `tests/test_backend_chat_smoke.py`
- Modify: `tests/test_quality_gates.py`
- Modify: `tests/test_integration_smoke_profile.py`

- [ ] **Step 1: Write failing script contract and helper tests**

Create `tests/test_backend_chat_smoke.py` with tests asserting that `scripts/integration/backend_chat_smoke.py` exists, uses `backend_runtime_smoke`, starts uvicorn indirectly, reads `OPENHER_API_TOKEN`, sets `OPENHER_DATA_DIR`, checks `/api/chat`, `/api/session/{session_id}/status`, and `/api/chat/history/{persona_id}`. Include unit tests for `chat_unavailable_reason`, `request_json_post`, and response-shape helpers.

- [ ] **Step 2: Write failing Makefile and README contract tests**

Extend `tests/test_quality_gates.py` to require `backend-chat-smoke` in `.PHONY`, compile target, and run target. Extend `tests/test_integration_smoke_profile.py` to require `make backend-chat-smoke` and a README note that it may call a real LLM and skips when chat is unavailable.

- [ ] **Step 3: Verify RED**

Run:

```bash
source .venv/bin/activate
python -m pytest tests/test_backend_chat_smoke.py tests/test_quality_gates.py::test_makefile_exposes_local_quality_gate_targets tests/test_integration_smoke_profile.py::test_makefile_and_readme_document_integration_smoke -q
```

Expected: FAIL because the new script and Makefile/docs references do not exist.

### Task 2: Implement Live Chat Smoke

**Files:**
- Create: `scripts/integration/backend_chat_smoke.py`
- Modify: `Makefile`
- Modify: `README.md`

- [ ] **Step 1: Implement `backend_chat_smoke.py`**

Add a CLI that loads `.env`, starts uvicorn with temp `OPENHER_DATA_DIR`, waits for `/api/status`, skips if `capabilities.chat.available` is false, POSTs to `/api/chat` when available, checks session status and history, redacts failures, prints sorted result fields, and exits 0 on success or skipped chat.

- [ ] **Step 2: Add Makefile target and compile gate**

Add `backend-chat-smoke` to `.PHONY`, compile `scripts/integration/backend_chat_smoke.py`, and run it from the new target.

- [ ] **Step 3: Update README**

Document `make backend-chat-smoke` in the development quality checks section and explain that it starts real uvicorn, exercises `/api/chat`, and may call the configured LLM.

- [ ] **Step 4: Verify focused tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tests/test_backend_chat_smoke.py tests/test_quality_gates.py::test_makefile_exposes_local_quality_gate_targets tests/test_integration_smoke_profile.py::test_makefile_and_readme_document_integration_smoke -q
```

Expected: PASS.

### Task 3: Runtime Verification and Finish

**Files:**
- All changed files

- [ ] **Step 1: Run live smokes**

Run:

```bash
source .venv/bin/activate
make backend-chat-smoke
make backend-runtime-smoke
make backend-websocket-smoke
make backend-acceptance-smoke
```

Expected: all exit 0. `backend-chat-smoke` may report skipped only when chat is unavailable.

- [ ] **Step 2: Run full gates**

Run:

```bash
source .venv/bin/activate
make check
swift build --package-path desktop/OpenHer
make integration-smoke
```

Expected: all exit 0, with optional media providers allowed to skip when keys are absent.

- [ ] **Step 3: Commit, merge, and push**

Run:

```bash
git status --short
git add docs/superpowers/specs/2026-06-30-backend-live-chat-smoke-design.md docs/superpowers/plans/2026-06-30-backend-live-chat-smoke.md scripts/integration/backend_chat_smoke.py tests/test_backend_chat_smoke.py tests/test_quality_gates.py tests/test_integration_smoke_profile.py Makefile README.md
git commit -m "test: add backend live chat smoke"
git checkout main
git pull --ff-only origin main
git merge --ff-only codex/backend-live-chat-smoke
git push origin main
```

Expected: merge fast-forwards and push succeeds.
