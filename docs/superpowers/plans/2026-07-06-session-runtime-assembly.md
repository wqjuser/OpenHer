# Session Runtime Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move REST chat, session lifecycle, and WebSocket service construction out of `server/bootstrap.py` into a focused session runtime module.

**Architecture:** Add `server/session_runtime.py` with `SessionRuntimeServices` and `build_session_runtime_services()`. Bootstrap will call the builder, assign returned services to `AppContext`, and continue owning cron scheduler/proactive heartbeat orchestration.

**Tech Stack:** Python 3.11+, dataclasses, pytest, pyright, existing FastAPI/WebSocket server services and Makefile gates.

---

### Task 1: Add Session Runtime Boundary Tests

**Files:**
- Create: `tests/test_session_runtime.py`
- Modify: `tests/test_server_bootstrap.py`
- Modify: `tests/test_chat_api_service.py`
- Modify: `tests/test_session_agent_factory.py`
- Modify: `tests/test_websocket_route_service.py`

- [x] **Step 1: Add session runtime available-path test**

Create `tests/test_session_runtime.py`:

```python
"""Session runtime assembly boundary tests."""

from __future__ import annotations

from typing import Any


class FakeService:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_session_runtime_builds_available_session_and_websocket_services(tmp_path):
    from server.session_runtime import build_session_runtime_services

    calls: dict[str, list[dict[str, Any]]] = {
        "agent_factory": [],
        "session_manager": [],
        "chat_api": [],
        "persona_switch": [],
        "ws_chat": [],
        "demo": [],
        "route": [],
    }

    def factory(name: str):
        def _factory(**kwargs: Any) -> FakeService:
            calls[name].append(kwargs)
            return FakeService(**kwargs)
        return _factory

    llm_client = object()
    persona_loader = object()
    task_skill_engine = object()
    modality_skill_engine = object()
    memory_store = object()
    state_store = object()
    evermemos = object()
    chat_log_store = object()
    ws_registry = object()
    ws_tts_service = object()
    ws_demo_proactive_service = object()

    def get_or_create_session(*_args: Any) -> tuple[str, object]:
        return ("sid", object())

    def remove_session(_session_id: str) -> None:
        return None

    runtime = build_session_runtime_services(
        base_dir=tmp_path,
        llm_client=llm_client,
        persona_loader=persona_loader,
        task_skill_engine=task_skill_engine,
        modality_skill_engine=modality_skill_engine,
        memory_store=memory_store,
        state_store=state_store,
        evermemos=evermemos,
        genome_data_dir="/tmp/genome",
        chat_log_store=chat_log_store,
        ws_registry=ws_registry,
        ws_tts_service=ws_tts_service,
        ws_demo_proactive_service=ws_demo_proactive_service,
        get_or_create_session=get_or_create_session,
        remove_session=remove_session,
        session_ttl_seconds=123,
        session_agent_factory_factory=factory("agent_factory"),
        session_manager_factory=factory("session_manager"),
        chat_api_service_factory=factory("chat_api"),
        persona_switch_service_factory=factory("persona_switch"),
        ws_chat_turn_service_factory=factory("ws_chat"),
        ws_demo_command_service_factory=factory("demo"),
        ws_route_service_factory=factory("route"),
    )

    assert calls["agent_factory"][0] == {
        "persona_loader": persona_loader,
        "llm_client": llm_client,
        "task_skill_engine": task_skill_engine,
        "modality_skill_engine": modality_skill_engine,
        "memory_store": memory_store,
        "state_store": state_store,
        "evermemos": evermemos,
        "genome_data_dir": "/tmp/genome",
    }
    assert calls["session_manager"][0]["agent_factory"] is runtime.session_agent_factory
    assert calls["session_manager"][0]["state_store"] is state_store
    assert calls["session_manager"][0]["evermemos"] is evermemos
    assert calls["session_manager"][0]["ttl_seconds"] == 123
    assert calls["chat_api"][0] == {
        "session_manager": runtime.session_manager,
        "chat_log_store": chat_log_store,
    }
    assert calls["persona_switch"][0] == {
        "registry": ws_registry,
        "get_or_create_session": get_or_create_session,
        "remove_session": remove_session,
    }
    assert calls["ws_chat"][0] == {
        "registry": ws_registry,
        "get_or_create_session": get_or_create_session,
        "chat_log_store": chat_log_store,
    }
    assert calls["demo"][0] == {
        "get_or_create_session": get_or_create_session,
        "presets_file": str(tmp_path / "demo" / "presets" / "showcase.yaml"),
        "proactive_delivery": ws_demo_proactive_service,
    }
    assert calls["route"][0] == {
        "registry": ws_registry,
        "session_manager": runtime.session_manager,
        "chat_turn_service": runtime.ws_chat_turn_service,
        "tts_service": ws_tts_service,
        "persona_switch_service": runtime.persona_switch_service,
        "demo_command_service": runtime.ws_demo_command_service,
    }
```

- [x] **Step 2: Add unavailable-path degradation test**

Append:

```python
def test_session_runtime_degrades_when_llm_is_unavailable(tmp_path):
    from server.session_runtime import build_session_runtime_services

    chat_api_calls: list[dict[str, Any]] = []
    route_calls: list[dict[str, Any]] = []

    def forbidden_factory(**_kwargs: Any) -> FakeService:
        raise AssertionError("factory should not be called when llm is unavailable")

    def chat_api_factory(**kwargs: Any) -> FakeService:
        chat_api_calls.append(kwargs)
        return FakeService(**kwargs)

    def route_factory(**kwargs: Any) -> FakeService:
        route_calls.append(kwargs)
        return FakeService(**kwargs)

    ws_registry = object()
    ws_tts_service = object()
    chat_log_store = object()

    runtime = build_session_runtime_services(
        base_dir=tmp_path,
        llm_client=None,
        persona_loader=object(),
        task_skill_engine=object(),
        modality_skill_engine=object(),
        memory_store=object(),
        state_store=object(),
        evermemos=None,
        genome_data_dir="/tmp/genome",
        chat_log_store=chat_log_store,
        ws_registry=ws_registry,
        ws_tts_service=ws_tts_service,
        ws_demo_proactive_service=object(),
        get_or_create_session=lambda *_args: ("sid", object()),
        remove_session=lambda _session_id: None,
        session_agent_factory_factory=forbidden_factory,
        session_manager_factory=forbidden_factory,
        chat_api_service_factory=chat_api_factory,
        persona_switch_service_factory=forbidden_factory,
        ws_chat_turn_service_factory=forbidden_factory,
        ws_demo_command_service_factory=forbidden_factory,
        ws_route_service_factory=route_factory,
    )

    assert runtime.session_agent_factory is None
    assert runtime.session_manager is None
    assert runtime.persona_switch_service is None
    assert runtime.ws_chat_turn_service is None
    assert runtime.ws_demo_command_service is None
    assert chat_api_calls == [{"session_manager": None, "chat_log_store": chat_log_store}]
    assert route_calls == [{
        "registry": ws_registry,
        "session_manager": None,
        "chat_turn_service": None,
        "tts_service": ws_tts_service,
        "persona_switch_service": None,
        "demo_command_service": None,
    }]
```

- [x] **Step 3: Update bootstrap and existing source boundary tests**

Update `tests/test_server_bootstrap.py::test_bootstrap_degrades_when_llm_provider_is_unavailable()` with:

```python
assert "from server.session_runtime import build_session_runtime_services" in bootstrap_source
assert "session_runtime = build_session_runtime_services(" in bootstrap_source
assert "context.session_agent_factory = session_runtime.session_agent_factory" in bootstrap_source
assert "context.session_manager = session_runtime.session_manager" in bootstrap_source
assert "context.chat_api_service = session_runtime.chat_api_service" in bootstrap_source
assert "context.persona_switch_service = session_runtime.persona_switch_service" in bootstrap_source
assert "context.ws_chat_turn_service = session_runtime.ws_chat_turn_service" in bootstrap_source
assert "context.ws_demo_command_service = session_runtime.ws_demo_command_service" in bootstrap_source
assert "context.ws_route_service = session_runtime.ws_route_service" in bootstrap_source
assert "SessionAgentFactory(" not in bootstrap_source
assert "SessionManager(" not in bootstrap_source
assert "ChatApiService(" not in bootstrap_source
assert "WebSocketPersonaSwitchService(" not in bootstrap_source
assert "WebSocketChatTurnService(" not in bootstrap_source
assert "WebSocketDemoCommandService(" not in bootstrap_source
assert "WebSocketRouteService(" not in bootstrap_source
```

Update these existing boundary tests:

```python
# tests/test_chat_api_service.py
assert "from server.session_runtime import build_session_runtime_services" in bootstrap_source
assert "context.chat_api_service = session_runtime.chat_api_service" in bootstrap_source
assert "context.chat_api_service = ChatApiService(" not in bootstrap_source

# tests/test_session_agent_factory.py
assert "from server.session_runtime import build_session_runtime_services" in bootstrap_source
assert "context.session_agent_factory = session_runtime.session_agent_factory" in bootstrap_source
assert "SessionAgentFactory(" not in bootstrap_source
assert "agent_factory=session_runtime.session_agent_factory" not in bootstrap_source

# tests/test_websocket_route_service.py
assert "from server.session_runtime import build_session_runtime_services" in bootstrap_source
assert "context.ws_route_service = session_runtime.ws_route_service" in bootstrap_source
assert "context.ws_route_service = WebSocketRouteService(" not in bootstrap_source
```

- [x] **Step 4: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_session_runtime.py tests/test_server_bootstrap.py::test_bootstrap_degrades_when_llm_provider_is_unavailable tests/test_chat_api_service.py::test_app_context_and_bootstrap_expose_chat_api_service_boundary tests/test_session_agent_factory.py::test_bootstrap_wires_session_agent_factory_before_session_manager tests/test_websocket_route_service.py::test_app_context_and_bootstrap_expose_websocket_route_service_boundary -v
```

Expected: FAIL because `server.session_runtime` does not exist and bootstrap still constructs session/WebSocket services inline.

### Task 2: Implement Session Runtime Module

**Files:**
- Create: `server/session_runtime.py`
- Modify: `server/bootstrap.py`

- [x] **Step 1: Add session runtime module**

Create `server/session_runtime.py`:

```python
"""Session and WebSocket runtime service assembly for OpenHer startup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from server.chat_api_service import ChatApiService
from server.session_agent_factory import SessionAgentFactory
from server.session_manager import SessionManager
from server.websocket_chat import WebSocketChatTurnService
from server.websocket_demo import WebSocketDemoCommandService
from server.websocket_persona_switch import WebSocketPersonaSwitchService
from server.websocket_route_service import WebSocketRouteService


GetOrCreateSession = Callable[[Optional[str], str, Optional[str], Optional[str]], tuple[str, Any]]
RemoveSession = Callable[[str], None]
ServiceFactory = Callable[..., Any]


@dataclass(frozen=True)
class SessionRuntimeServices:
    session_agent_factory: SessionAgentFactory | None
    session_manager: SessionManager | None
    chat_api_service: ChatApiService
    persona_switch_service: WebSocketPersonaSwitchService | None
    ws_chat_turn_service: WebSocketChatTurnService | None
    ws_demo_command_service: WebSocketDemoCommandService | None
    ws_route_service: WebSocketRouteService


def build_session_runtime_services(
    *,
    base_dir: Path,
    llm_client: Any | None,
    persona_loader: Any,
    task_skill_engine: Any,
    modality_skill_engine: Any,
    memory_store: Any,
    state_store: Any,
    evermemos: Any | None,
    genome_data_dir: str,
    chat_log_store: Any,
    ws_registry: Any,
    ws_tts_service: Any | None,
    ws_demo_proactive_service: Any,
    get_or_create_session: GetOrCreateSession,
    remove_session: RemoveSession,
    session_ttl_seconds: int,
    session_agent_factory_factory: ServiceFactory = SessionAgentFactory,
    session_manager_factory: ServiceFactory = SessionManager,
    chat_api_service_factory: ServiceFactory = ChatApiService,
    persona_switch_service_factory: ServiceFactory = WebSocketPersonaSwitchService,
    ws_chat_turn_service_factory: ServiceFactory = WebSocketChatTurnService,
    ws_demo_command_service_factory: ServiceFactory = WebSocketDemoCommandService,
    ws_route_service_factory: ServiceFactory = WebSocketRouteService,
) -> SessionRuntimeServices:
    session_agent_factory = None
    session_manager = None
    persona_switch_service = None
    ws_chat_turn_service = None
    ws_demo_command_service = None

    if llm_client:
        session_agent_factory = session_agent_factory_factory(
            persona_loader=persona_loader,
            llm_client=llm_client,
            task_skill_engine=task_skill_engine,
            modality_skill_engine=modality_skill_engine,
            memory_store=memory_store,
            state_store=state_store,
            evermemos=evermemos,
            genome_data_dir=genome_data_dir,
        )
        session_manager = session_manager_factory(
            agent_factory=session_agent_factory,
            state_store=state_store,
            evermemos=evermemos,
            ttl_seconds=session_ttl_seconds,
        )
        chat_api_service = chat_api_service_factory(
            session_manager=session_manager,
            chat_log_store=chat_log_store,
        )
        persona_switch_service = persona_switch_service_factory(
            registry=ws_registry,
            get_or_create_session=get_or_create_session,
            remove_session=remove_session,
        )
        ws_chat_turn_service = ws_chat_turn_service_factory(
            registry=ws_registry,
            get_or_create_session=get_or_create_session,
            chat_log_store=chat_log_store,
        )
        ws_demo_command_service = ws_demo_command_service_factory(
            get_or_create_session=get_or_create_session,
            presets_file=str(Path(base_dir) / "demo" / "presets" / "showcase.yaml"),
            proactive_delivery=ws_demo_proactive_service,
        )
    else:
        chat_api_service = chat_api_service_factory(
            session_manager=None,
            chat_log_store=chat_log_store,
        )

    ws_route_service = ws_route_service_factory(
        registry=ws_registry,
        session_manager=session_manager,
        chat_turn_service=ws_chat_turn_service,
        tts_service=ws_tts_service,
        persona_switch_service=persona_switch_service,
        demo_command_service=ws_demo_command_service,
    )

    return SessionRuntimeServices(
        session_agent_factory=session_agent_factory,
        session_manager=session_manager,
        chat_api_service=chat_api_service,
        persona_switch_service=persona_switch_service,
        ws_chat_turn_service=ws_chat_turn_service,
        ws_demo_command_service=ws_demo_command_service,
        ws_route_service=ws_route_service,
    )
```

- [x] **Step 2: Refactor bootstrap imports**

In `server/bootstrap.py`, remove:

```python
from server.chat_api_service import ChatApiService
from server.session_agent_factory import SessionAgentFactory
from server.session_manager import SessionManager
from server.websocket_chat import WebSocketChatTurnService
from server.websocket_demo import WebSocketDemoCommandService
from server.websocket_persona_switch import WebSocketPersonaSwitchService
from server.websocket_route_service import WebSocketRouteService
```

Add:

```python
from server.session_runtime import build_session_runtime_services
```

- [x] **Step 3: Refactor startup session/WebSocket assembly**

Replace the inline `if context.llm_client: ... else: ... context.ws_route_service = ...` block with:

```python
    session_runtime = build_session_runtime_services(
        base_dir=base_dir,
        llm_client=context.llm_client,
        persona_loader=context.persona_loader,
        task_skill_engine=task_skill_engine,
        modality_skill_engine=modality_skill_engine,
        memory_store=memory_store,
        state_store=state_store,
        evermemos=evermemos,
        genome_data_dir=context.genome_data_dir,
        chat_log_store=chat_log_store,
        ws_registry=context.ws_registry,
        ws_tts_service=context.ws_tts_service,
        ws_demo_proactive_service=context.ws_demo_proactive_service,
        get_or_create_session=lambda session_id, persona_id, user_name=None, client_id=None: _get_or_create_session(
            context, session_id, persona_id, user_name, client_id
        ),
        remove_session=lambda session_id: _remove_session(context, session_id),
        session_ttl_seconds=SESSION_TTL_SECONDS,
    )
    context.session_agent_factory = session_runtime.session_agent_factory
    context.session_manager = session_runtime.session_manager
    context.chat_api_service = session_runtime.chat_api_service
    context.persona_switch_service = session_runtime.persona_switch_service
    context.ws_chat_turn_service = session_runtime.ws_chat_turn_service
    context.ws_demo_command_service = session_runtime.ws_demo_command_service
    context.ws_route_service = session_runtime.ws_route_service
    session_manager = session_runtime.session_manager
```

Then replace:

```python
if context.llm_client and context.session_manager:
```

with:

```python
if context.llm_client and session_manager:
```

and pass `session_manager=session_manager` to `ProactiveService`.

- [x] **Step 4: Run session runtime tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_session_runtime.py tests/test_server_bootstrap.py tests/test_chat_api_service.py::test_app_context_and_bootstrap_expose_chat_api_service_boundary tests/test_session_agent_factory.py::test_bootstrap_wires_session_agent_factory_before_session_manager tests/test_websocket_route_service.py::test_app_context_and_bootstrap_expose_websocket_route_service_boundary -v
```

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-session-runtime-assembly.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so every executed step is checked.

- [x] **Step 2: Run focused session/bootstrap/chat/WebSocket tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_session_runtime.py tests/test_server_bootstrap.py tests/test_chat_api_service.py tests/test_session_agent_factory.py tests/test_websocket_chat_service.py tests/test_websocket_route_service.py tests/test_websocket_demo_commands.py -v
```

Expected: all focused session, chat, and WebSocket tests pass.

- [x] **Step 3: Run repository checks**

Run:

```bash
make check
```

Expected: pyright reports 0 errors and the full pytest suite passes.

- [x] **Step 4: Run runtime/smoke/build gates**

Run:

```bash
make doctor backend-acceptance-smoke backend-runtime-smoke backend-chat-smoke desktop-acceptance-smoke desktop-build
```

Expected: each command exits 0. `make doctor` may report optional warnings for unconfigured optional providers or missing local backups.

- [x] **Step 5: Commit and push**

Run:

```bash
git add docs/superpowers/specs/2026-07-06-session-runtime-assembly-design.md docs/superpowers/plans/2026-07-06-session-runtime-assembly.md server/session_runtime.py server/bootstrap.py tests/test_session_runtime.py tests/test_server_bootstrap.py tests/test_chat_api_service.py tests/test_session_agent_factory.py tests/test_websocket_route_service.py
git commit -m "refactor: extract session runtime assembly"
git push origin main
```
