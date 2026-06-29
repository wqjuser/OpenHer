# Backend WebSocket Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live backend WebSocket smoke command that starts the real backend process, connects to `/ws/chat`, and verifies structured WebSocket error events without calling the LLM.

**Architecture:** Reuse `scripts/integration/backend_runtime_smoke.py` for port selection, uvicorn startup, readiness polling, and process cleanup. Add `scripts/integration/backend_websocket_smoke.py` for the WebSocket-specific checks using the existing `websockets` dependency. The smoke should send invalid JSON and a `status` message with no active agent, then assert `Invalid JSON` and `code=service_unavailable` responses.

**Tech Stack:** Python 3.11+, `websockets`, existing runtime smoke helpers, Makefile targets, pytest source/helper contract tests.

---

### Task 1: WebSocket Smoke Contract Tests

**Files:**
- Create: `tests/test_backend_websocket_smoke.py`
- Modify: `tests/test_quality_gates.py`
- Modify: `tests/test_integration_smoke_profile.py`

- [ ] **Step 1: Add script source/helper tests**

Create `tests/test_backend_websocket_smoke.py` requiring:

```python
source = SCRIPT.read_text(encoding="utf-8")
assert "websockets.connect" in source
assert "backend_runtime_smoke" in source
assert "async def check_websocket_errors" in source
assert "def websocket_url" in source
assert "Invalid JSON" in source
assert "service_unavailable" in source
assert "OPENHER_API_TOKEN" in source
assert "redact_known_secrets" in source
```

Also import the module and test `websocket_url("http://127.0.0.1:8123", "") == "ws://127.0.0.1:8123/ws/chat"` and that token query parameters are URL-encoded.

- [ ] **Step 2: Require Makefile target and compile coverage**

Update `test_makefile_exposes_local_quality_gate_targets()` to require `backend-websocket-smoke` and:

```python
assert "$(PYTHON) -m py_compile scripts/integration/backend_websocket_smoke.py" in text
assert "$(PYTHON) scripts/integration/backend_websocket_smoke.py" in text
```

- [ ] **Step 3: Require README docs**

Update `test_makefile_and_readme_document_integration_smoke()` to assert README mentions `make backend-websocket-smoke`, `真实 WebSocket`, and `service_unavailable`.

- [ ] **Step 4: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_backend_websocket_smoke.py tests/test_quality_gates.py::test_makefile_exposes_local_quality_gate_targets tests/test_integration_smoke_profile.py::test_makefile_and_readme_document_integration_smoke -q
```

Expected: FAIL because the script, Makefile target, and README docs do not exist yet.

### Task 2: WebSocket Smoke Implementation

**Files:**
- Create: `scripts/integration/backend_websocket_smoke.py`
- Modify: `Makefile`
- Modify: `README.md`

- [ ] **Step 1: Implement WebSocket URL helper**

Add `websocket_url(base_url, token)` that converts `http://` to `ws://`, `https://` to `wss://`, appends `/ws/chat`, and adds a URL-encoded `token` query parameter only when token is present.

- [ ] **Step 2: Implement WebSocket checks**

Add `async def check_websocket_errors(uri)`:

```python
async with websockets.connect(uri, open_timeout=8, ping_interval=None) as websocket:
    await websocket.send("{not-json")
    invalid = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))
    assert invalid["type"] == "error"
    assert invalid["content"] == "Invalid JSON"

    await websocket.send(json.dumps({"type": "status", "client_id": SMOKE_CLIENT_ID}))
    unavailable = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))
    assert unavailable["type"] == "error"
    assert unavailable["code"] == "service_unavailable"
```

- [ ] **Step 3: Implement runtime orchestration**

`async def run_smoke(timeout)` should load `.env`, read `OPENHER_API_TOKEN`, start uvicorn with runtime helpers, wait for `/api/status`, connect to WebSocket, run checks, return `websocket_invalid_json` and `websocket_service_unavailable` results, and stop the process in `finally`.

- [ ] **Step 4: Implement CLI**

`main()` should parse `--timeout`, run the async smoke, print concise result lines, redact failures with `redact_known_secrets`, and return non-zero on failure.

- [ ] **Step 5: Wire Makefile**

Add `backend-websocket-smoke` to `.PHONY`, compile the script in `compile`, and add:

```make
backend-websocket-smoke:
	$(PYTHON) scripts/integration/backend_websocket_smoke.py
```

- [ ] **Step 6: Document smoke target**

Update README development quality checks to list `make backend-websocket-smoke`, and explain that it starts a real backend process and verifies WebSocket `Invalid JSON` and `service_unavailable` events without calling the LLM.

- [ ] **Step 7: Verify GREEN**

Run the focused test command from Task 1. Expected: PASS.

### Task 3: Verification and Integration

**Files:**
- Verify repository behavior.

- [ ] **Step 1: Run new live WebSocket smoke**

Run: `make backend-websocket-smoke`

Expected: server starts on a free port, WebSocket checks pass, and the process is stopped.

- [ ] **Step 2: Run existing backend smokes**

Run:

```bash
make backend-runtime-smoke
make backend-acceptance-smoke
```

Expected: both pass.

- [ ] **Step 3: Run full quality gate**

Run: `make check`

Expected: Pyright, compile, pytest, and diff check pass.

- [ ] **Step 4: Build desktop**

Run: `cd desktop/OpenHer && swift build`

Expected: PASS.

- [ ] **Step 5: Run live provider smoke**

Run: `make integration-smoke`

Expected: configured live providers pass; optional media providers may skip.

- [ ] **Step 6: Commit, merge, and push**

Run:

```bash
git add Makefile README.md scripts/integration/backend_websocket_smoke.py tests/test_backend_websocket_smoke.py tests/test_quality_gates.py tests/test_integration_smoke_profile.py docs/superpowers/plans/2026-06-29-backend-websocket-smoke.md
git commit -m "test: add backend websocket smoke"
git checkout main
git pull --ff-only
git merge codex/backend-websocket-smoke
git push origin main
```

Expected: commit succeeds, merge is clean, push succeeds.
