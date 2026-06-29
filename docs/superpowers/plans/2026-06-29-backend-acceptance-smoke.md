# Backend Acceptance Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic backend acceptance smoke command that verifies the core product HTTP flow without requiring live external provider keys.

**Architecture:** Create `scripts/integration/backend_acceptance_smoke.py` as an in-process FastAPI smoke runner using a minimal `AppContext` with persona services and no live chat session. Add a `make backend-acceptance-smoke` target and compile/quality-gate coverage so the smoke remains discoverable and runnable.

**Tech Stack:** Python 3.11+, FastAPI TestClient, pytest source and behavior tests, existing `AppContext`/route contracts, Makefile quality gates.

---

### Task 1: Smoke Contract Tests

**Files:**
- Modify: `tests/test_quality_gates.py`
- Create: `tests/test_backend_acceptance_smoke.py`

- [ ] **Step 1: Require Makefile and compile integration**

Add assertions to `tests/test_quality_gates.py`:

```python
assert "backend-acceptance-smoke" in text
assert "$(PYTHON) -m py_compile scripts/integration/backend_acceptance_smoke.py" in text
assert "$(PYTHON) scripts/integration/backend_acceptance_smoke.py" in text
```

- [ ] **Step 2: Require script structure and behavior surface**

Create `tests/test_backend_acceptance_smoke.py` with source-contract tests requiring:

```python
source = (ROOT / "scripts/integration/backend_acceptance_smoke.py").read_text(encoding="utf-8")
assert "def build_client()" in source
assert "def check_status" in source
assert "def check_personas" in source
assert "def check_chat_history_empty_state" in source
assert "def check_chat_unavailable" in source
assert "def main() -> int" in source
assert "TestClient" in source
assert "AppContext()" in source
assert "create_app(context)" in source
```

- [ ] **Step 3: Verify tests fail**

Run: `.venv/bin/python -m pytest tests/test_quality_gates.py::test_makefile_exposes_local_quality_gate_targets tests/test_backend_acceptance_smoke.py -q`

Expected: FAIL because the script and Makefile target do not exist yet.

### Task 2: Smoke Script Implementation

**Files:**
- Create: `scripts/integration/backend_acceptance_smoke.py`
- Modify: `Makefile`

- [ ] **Step 1: Implement in-process client creation**

Create `build_client()`:

```python
def build_client() -> TestClient:
    import main
    from persona.loader import PersonaLoader
    from server.context import AppContext
    from server.persona_api_service import PersonaApiService

    context = AppContext()
    personas_dir = ROOT / "persona" / "personas"
    context.persona_loader = PersonaLoader(str(personas_dir))
    context.persona_api_service = PersonaApiService(
        persona_loader=context.persona_loader,
        personas_dir=personas_dir,
    )
    return TestClient(main.create_app(context), raise_server_exceptions=False)
```

- [ ] **Step 2: Implement status check**

`check_status(client)` should call `/api/status`, assert HTTP 200, require `status == "running"`, require `capabilities.chat.available` to be a boolean, and require provider/capability keys. The status check must not require external provider keys to be absent because local `.env` may be configured.

- [ ] **Step 3: Implement persona check**

`check_personas(client)` should call `/api/personas`, assert HTTP 200, require a non-empty `personas` list, and require each checked item to have `persona_id` and `name`.

- [ ] **Step 4: Implement chat history empty-state check**

`check_chat_history_empty_state(client, persona_id)` should call `/api/chat/history/{persona_id}?client_id=__acceptance_smoke__&limit=5`, assert HTTP 200, and require `{"messages": [], "total": 0}` shape.

- [ ] **Step 5: Implement unavailable chat check**

`check_chat_unavailable(client, persona_id)` should POST `/api/chat` with a tiny message and assert HTTP 503 with detail containing `Session manager is not initialized`.

- [ ] **Step 6: Implement CLI output**

`main()` should run checks in order, print concise `status: ... status=ok`, `personas: ... status=ok`, `history: ... status=ok`, `chat_unavailable: ... status=ok` lines, redact exceptions through `redact_known_secrets`, and return non-zero on failure.

- [ ] **Step 7: Add Makefile target**

Add `backend-acceptance-smoke` to `.PHONY`, add compile coverage for the new script, and add:

```make
backend-acceptance-smoke:
	$(PYTHON) scripts/integration/backend_acceptance_smoke.py
```

- [ ] **Step 8: Verify focused tests pass**

Run: `.venv/bin/python -m pytest tests/test_quality_gates.py::test_makefile_exposes_local_quality_gate_targets tests/test_backend_acceptance_smoke.py -q`

Expected: PASS.

### Task 3: Verification and Integration

**Files:**
- Verify repository behavior.

- [ ] **Step 1: Run smoke command**

Run: `make backend-acceptance-smoke`

Expected: all four smoke lines report `ok`.

- [ ] **Step 2: Run full quality gate**

Run: `make check`

Expected: Pyright passes, compile passes, full pytest passes, diff check passes.

- [ ] **Step 3: Build macOS client**

Run: `cd desktop/OpenHer && swift build`

Expected: PASS.

- [ ] **Step 4: Run live provider smoke**

Run: `make integration-smoke`

Expected: configured live providers pass; optional unconfigured media providers may skip.

- [ ] **Step 5: Commit, merge, and push**

Run:

```bash
git add Makefile scripts/integration/backend_acceptance_smoke.py tests/test_backend_acceptance_smoke.py tests/test_quality_gates.py docs/superpowers/plans/2026-06-29-backend-acceptance-smoke.md
git commit -m "test: add backend acceptance smoke"
git checkout main
git pull --ff-only
git merge codex/backend-acceptance-smoke
git push origin main
```

Expected: commit succeeds, merge is clean, push succeeds.
