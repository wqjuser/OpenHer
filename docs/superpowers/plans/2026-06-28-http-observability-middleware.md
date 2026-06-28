# HTTP Observability Middleware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add request correlation and timing headers to every HTTP response so backend/API issues are easier to trace locally and in CI smoke tests.

**Architecture:** Add `server/observability.py` as the boundary for HTTP request id sanitization, process-time calculation, and request logging. `main.create_app()` will register this middleware around the existing auth middleware so normal and unauthorized HTTP responses carry the same observability headers.

**Tech Stack:** FastAPI function middleware, Python stdlib `logging`, pytest, pyright.

---

### Task 1: Red Tests For HTTP Observability

**Files:**
- Create: `tests/test_observability.py`

- [x] **Step 1: Write failing tests**

Add tests that assert:
- `GET /api/status` includes `X-Request-ID` and `X-Process-Time-ms`.
- A valid incoming `X-Request-ID` is preserved.
- Blank or unsafe `X-Request-ID` values are replaced.
- Unauthorized responses still include observability headers when `OPENHER_API_TOKEN` is configured.
- `main.py` imports and registers `add_request_observability`.

- [x] **Step 2: Run tests and verify expected failure**

Run: `.venv/bin/python -m pytest tests/test_observability.py -q`

Expected: FAIL because `server.observability` and middleware registration do not exist yet.

### Task 2: Add Observability Middleware

**Files:**
- Create: `server/observability.py`
- Modify: `main.py`

- [x] **Step 1: Implement request id helpers**

Create `server/observability.py` with:
- `REQUEST_ID_HEADER = "X-Request-ID"`.
- `PROCESS_TIME_HEADER = "X-Process-Time-ms"`.
- `sanitize_request_id(value: str | None) -> str`.
- generated ids using `uuid.uuid4().hex`.

- [x] **Step 2: Implement middleware**

Add `add_request_observability(request, call_next)` that:
- records `time.perf_counter()`,
- stores `request.state.request_id`,
- calls the next middleware/route,
- adds request id and elapsed milliseconds to response headers,
- logs method, path, status, elapsed time, and request id.

- [x] **Step 3: Register middleware**

Import `add_request_observability` in `main.py` and register it in `create_app()` alongside `require_api_token`.

### Task 3: Verification And Delivery

**Files:**
- Test: `tests/test_observability.py`
- Verify: full quality gate

- [x] **Step 1: Run observability tests**

Run: `.venv/bin/python -m pytest tests/test_observability.py -q`

Expected: PASS.

- [x] **Step 2: Run focused HTTP/server tests**

Run: `.venv/bin/python -m pytest tests/test_observability.py tests/test_server_context.py tests/test_server_routes.py tests/test_security_regressions.py::APIAuthRegressionTests tests/test_security_regressions.py::ExternalEndpointErrorTests -q`

Expected: PASS.

- [x] **Step 3: Run full verification**

Run:
- `source .venv/bin/activate && make check`
- `.venv/bin/python -m py_compile server/observability.py main.py tests/test_observability.py`
- `cd desktop/OpenHer && swift build`

Expected: all commands exit 0.

- [x] **Step 4: Commit branch**

Run:
```bash
git add server/observability.py main.py tests/test_observability.py docs/superpowers/plans/2026-06-28-http-observability-middleware.md
git commit -m "feat: add http observability middleware"
```

Expected: branch contains the observability middleware commit.

- [ ] **Step 5: Merge and push**

Run:
```bash
git switch main
git pull --ff-only
git merge --no-ff codex/http-observability-middleware -m "merge: http observability middleware"
git push origin main
```

Expected: `main` contains the observability middleware merge commit and is pushed to `origin/main`.
