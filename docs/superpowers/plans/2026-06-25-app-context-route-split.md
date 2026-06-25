# App Context Route Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move OpenHer server assembly out of module globals and split HTTP/WebSocket routes into focused routers without changing public API behavior.

**Architecture:** Add a typed `AppContext` that owns runtime services and is attached to `app.state`. Keep compatibility wrappers in `main.py` while routes migrate. Create `server/routes/*` modules that receive the context from `request.app.state.openher`.

**Tech Stack:** FastAPI lifespan, APIRouter, pytest, pyright, existing server service classes.

---

### Task 1: AppContext Boundary

**Files:**
- Create: `server/context.py`
- Modify: `main.py`
- Test: `tests/test_server_context.py`

- [ ] **Step 1: Write the failing test**

```python
def test_create_app_attaches_app_context():
    import main
    app = main.create_app()
    assert hasattr(app.state, "openher")
    assert app.state.openher.ws_registry is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server_context.py::test_create_app_attaches_app_context -q`
Expected: FAIL because `main.create_app` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `AppContext` with service attributes and `create_app()` that attaches it to `app.state.openher`. Move existing `app = FastAPI(...)` construction into `create_app()` and keep `app = create_app()` at module import.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_server_context.py -q`
Expected: PASS.

### Task 2: Route Module Extraction

**Files:**
- Create: `server/routes/health.py`
- Create: `server/routes/persona.py`
- Create: `server/routes/chat.py`
- Create: `server/routes/media.py`
- Create: `server/routes/demo.py`
- Create: `server/routes/websocket.py`
- Modify: `main.py`
- Test: `tests/test_server_routes.py`

- [ ] **Step 1: Write the failing test**

```python
def test_main_registers_route_modules():
    import main
    app = main.create_app()
    route_names = {getattr(route, "name", "") for route in app.routes}
    assert "api_status" in route_names
    assert "websocket_chat" in route_names
```

- [ ] **Step 2: Run test to verify it fails or protects behavior**

Run: `.venv/bin/python -m pytest tests/test_server_routes.py::test_main_registers_route_modules -q`
Expected: PASS before extraction, then remain PASS after extraction.

- [ ] **Step 3: Move routes one group at a time**

Move status/persona/media/chat/demo/websocket handlers into route modules. Each module exposes `router = APIRouter()` and gets the runtime context with `request.app.state.openher` or `websocket.app.state.openher`.

- [ ] **Step 4: Run route and full server tests**

Run: `.venv/bin/python -m pytest tests/test_server_routes.py tests/test_security_regressions.py tests/test_websocket_chat_service.py tests/test_websocket_demo_commands.py -q`
Expected: PASS.

### Task 3: Verification

**Files:**
- Modify: no production files unless verification reveals a regression.

- [ ] **Step 1: Run static and test verification**

Run:
```bash
.venv/bin/python -m pytest tests/ -v
.venv/bin/pyright
.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py
git diff --check
```

Expected: pytest passes with one skipped WebSocket external-server test, pyright reports 0 errors, compileall exits 0, and diff check is clean.

- [ ] **Step 2: Run server smoke**

Run `PORT=8000 ./run.sh`, call `/api/status`, connect to `/ws/chat`, send `demo_presets`, then stop the server.

Expected: HTTP status returns running metadata, WebSocket returns `demo_presets`, and port 8000 is released after shutdown.
