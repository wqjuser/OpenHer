# LLM Unavailable Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the backend start and expose diagnostics when the configured LLM provider is unavailable, instead of failing during bootstrap.

**Architecture:** Use `get_llm_config()["available"]` during startup before constructing `LLMClient`. When LLM is unavailable, keep non-chat services alive, expose `/api/status`, media/persona/history routes, and wire chat runtime with `ChatApiService(session_manager=None, ...)` so chat requests return HTTP 503 through the existing route mapping. Skip session manager, WebSocket chat/session services, cron, and proactive heartbeat when no LLM client exists.

**Tech Stack:** Python 3.11+, pytest, existing bootstrap boundary tests, existing FastAPI route/service error mapping.

---

### Task 1: Add Failing Bootstrap Contract Test

**Files:**
- Modify: `tests/test_server_bootstrap.py`

- [x] **Step 1: Add bootstrap degradation contract test**

Add a source-level bootstrap contract test asserting startup reads LLM availability before constructing `LLMClient`, assigns `context.llm_client = None` when unavailable, wires `ChatApiService(session_manager=None, ...)`, and only starts session/proactive runtime when both LLM client and session manager exist:

```python
def test_bootstrap_degrades_when_llm_provider_is_unavailable():
    bootstrap_source = (ROOT / "server" / "bootstrap.py").read_text(encoding="utf-8")

    assert 'llm_available = bool(llm_cfg.get("available", True))' in bootstrap_source
    assert "context.llm_client = None" in bootstrap_source
    assert "LLM provider" in bootstrap_source
    assert "ChatApiService(" in bootstrap_source
    assert "session_manager=None" in bootstrap_source
    assert "context.session_agent_factory = None" in bootstrap_source
    assert "context.session_manager = None" in bootstrap_source
    assert "if context.llm_client and context.session_manager:" in bootstrap_source
    assert "context.proactive_service = None" in bootstrap_source
    assert "context.proactive_task = None" in bootstrap_source
```

- [x] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_server_bootstrap.py::test_bootstrap_degrades_when_llm_provider_is_unavailable -q
```

Expected: fail because bootstrap currently constructs `LLMClient` unconditionally.

### Task 2: Implement Startup Degradation

**Files:**
- Modify: `server/bootstrap.py`

- [x] **Step 3: Guard LLM client construction**

Change startup so it does:

```python
llm_cfg = get_llm_config()
llm_available = bool(llm_cfg.get("available", True))
if llm_available:
    context.llm_client = LLMClient(...)
else:
    context.llm_client = None
    missing_key = llm_cfg.get("missing_key_env") or f"{llm_cfg['provider'].upper()}_API_KEY"
    print(f"⚠ LLM provider '{llm_cfg['provider']}' 未配置 {missing_key}，已禁用聊天会话和主动消息")
```

- [x] **Step 4: Split LLM-dependent runtime wiring**

After memory setup, wrap session factory, session manager, WebSocket chat, demo command, and proactive service creation in:

```python
if context.llm_client and context.session_manager:
    ...
else:
    context.session_agent_factory = None
    context.session_manager = None
    context.chat_api_service = ChatApiService(session_manager=None, chat_log_store=context.chat_log_store)
    context.persona_switch_service = None
    context.ws_chat_turn_service = None
    context.ws_demo_command_service = None
    context.ws_route_service = WebSocketRouteService(...)
    context.proactive_service = None
    context.proactive_task = None
```

Keep `ws_tts_service`, `media_api_service`, persona APIs, stores, and `/api/status` available.

- [x] **Step 5: Guard cron startup**

Only start cron scheduler when `cron_skills` exists and `context.llm_client` is available, because cron message generation calls the LLM.

- [x] **Step 6: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_server_bootstrap.py tests/test_chat_api_service.py tests/test_server_routes.py -q
```

Expected: all selected bootstrap/chat/route tests pass.

### Task 3: Verify And Ship

**Files:**
- Verify: full Python checks
- Verify: live provider smoke
- Verify: macOS Swift package build

- [x] **Step 7: Run full checks**

Run:

```bash
source .venv/bin/activate && make check
```

- [x] **Step 8: Run runtime smoke and desktop build**

Run:

```bash
source .venv/bin/activate && make integration-smoke
cd desktop/OpenHer && swift build
```

- [x] **Step 9: Commit, merge to main, and push**

Commit message:

```bash
git commit -m "fix: allow startup without llm credentials"
```
