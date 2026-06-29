# Backend Runtime Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live backend runtime smoke command that starts the real uvicorn app, verifies core HTTP routes, and reliably stops the process.

**Architecture:** Keep the existing in-process `backend-acceptance-smoke` as the deterministic no-server check. Add `scripts/integration/backend_runtime_smoke.py` as an opt-in live-process smoke that chooses a free localhost port, starts `python -m uvicorn main:app`, polls `/api/status`, calls persona and history endpoints, then terminates or kills the child process during cleanup.

**Tech Stack:** Python 3.11+, stdlib `subprocess`/`socket`/`urllib`, existing FastAPI app, Makefile targets, pytest source/helper contract tests.

---

### Task 1: Runtime Smoke Contract Tests

**Files:**
- Create: `tests/test_backend_runtime_smoke.py`
- Modify: `tests/test_quality_gates.py`
- Modify: `tests/test_integration_smoke_profile.py`

- [ ] **Step 1: Add source/helper tests**

Create `tests/test_backend_runtime_smoke.py` requiring:

```python
source = SCRIPT.read_text(encoding="utf-8")
assert "subprocess.Popen" in source
assert "-m" in source and "uvicorn" in source and "main:app" in source
assert "def find_free_port()" in source
assert "def start_server" in source
assert "def wait_for_status" in source
assert "def stop_server" in source
assert "def check_live_personas" in source
assert "def check_live_history" in source
assert "OPENHER_API_TOKEN" in source
assert "redact_known_secrets" in source
```

Also load the module and test `find_free_port()` returns a bindable integer, and `stop_server()` terminates a dummy long-running Python subprocess.

- [ ] **Step 2: Require Makefile target and compile coverage**

Update `test_makefile_exposes_local_quality_gate_targets()` to require `backend-runtime-smoke` and:

```python
assert "$(PYTHON) -m py_compile scripts/integration/backend_runtime_smoke.py" in text
assert "$(PYTHON) scripts/integration/backend_runtime_smoke.py" in text
```

- [ ] **Step 3: Require README docs**

Update `test_makefile_and_readme_document_integration_smoke()` to assert README mentions `make backend-acceptance-smoke`, `make backend-runtime-smoke`, `真实 uvicorn`, and `默认测试和 make check 不会启动后端进程`.

- [ ] **Step 4: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_backend_runtime_smoke.py tests/test_quality_gates.py::test_makefile_exposes_local_quality_gate_targets tests/test_integration_smoke_profile.py::test_makefile_and_readme_document_integration_smoke -q
```

Expected: FAIL because `backend_runtime_smoke.py`, Makefile target, and README docs do not exist yet.

### Task 2: Runtime Smoke Implementation

**Files:**
- Create: `scripts/integration/backend_runtime_smoke.py`
- Modify: `Makefile`
- Modify: `README.md`

- [ ] **Step 1: Implement port and request helpers**

Add `find_free_port()`, `request_json(base_url, path, token)`, and `format_result(name, result)` helpers. Use `urllib.request` so no extra runtime dependency is introduced.

- [ ] **Step 2: Implement process lifecycle**

Add `start_server(port)` returning a `subprocess.Popen` and temp log handle. Start:

```python
[sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)]
```

Add `stop_server(process)` that terminates, waits, and kills on timeout.

- [ ] **Step 3: Implement readiness polling**

Add `wait_for_status(base_url, process, log_file, timeout, token)` that polls `/api/status` until status is `running`, fails early if the process exits, and includes a redacted log tail on failure.

- [ ] **Step 4: Implement live route checks**

Add:

```python
check_live_status(status_body)
check_live_personas(base_url, token)
check_live_history(base_url, token, persona_id)
```

The checks should validate capabilities/provider keys, a non-empty persona list, and empty history for a unique smoke client id.

- [ ] **Step 5: Implement CLI**

`main()` loads `.env`, reads `OPENHER_API_TOKEN` for auth, runs the smoke with `--timeout` defaulting to 30 seconds, prints `runtime_status`, `runtime_personas`, and `runtime_history` lines, redacts failures, stops the process in `finally`, and exits non-zero on failure.

- [ ] **Step 6: Wire Makefile**

Add `backend-runtime-smoke` to `.PHONY`, compile the script in `compile`, and add:

```make
backend-runtime-smoke:
	$(PYTHON) scripts/integration/backend_runtime_smoke.py
```

- [ ] **Step 7: Document smoke targets**

Update README development quality checks to list `make backend-acceptance-smoke` and `make backend-runtime-smoke`, and explain that runtime smoke starts a real uvicorn backend while default tests and `make check` do not.

- [ ] **Step 8: Verify GREEN**

Run the focused test command from Task 1. Expected: PASS.

### Task 3: Runtime Verification and Integration

**Files:**
- Verify repository behavior.

- [ ] **Step 1: Run new live runtime smoke**

Run: `make backend-runtime-smoke`

Expected: server starts on a free port, route checks pass, and the process is stopped.

- [ ] **Step 2: Run existing deterministic backend smoke**

Run: `make backend-acceptance-smoke`

Expected: PASS.

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
git add Makefile README.md scripts/integration/backend_runtime_smoke.py tests/test_backend_runtime_smoke.py tests/test_quality_gates.py tests/test_integration_smoke_profile.py docs/superpowers/plans/2026-06-29-backend-runtime-smoke.md
git commit -m "test: add backend runtime smoke"
git checkout main
git pull --ff-only
git merge codex/backend-runtime-smoke
git push origin main
```

Expected: commit succeeds, merge is clean, push succeeds.
