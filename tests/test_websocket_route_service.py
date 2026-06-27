"""WebSocket route service boundary tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from starlette.websockets import WebSocketDisconnect


ROOT = Path(__file__).resolve().parents[1]


class FakeWebSocket:
    def __init__(self, messages: list[dict[str, Any] | str]):
        self.messages = list(messages)
        self.sent: list[dict[str, Any]] = []

    async def receive_text(self) -> str:
        if not self.messages:
            await asyncio.sleep(0)
            raise WebSocketDisconnect(code=1000)
        message = self.messages.pop(0)
        if isinstance(message, str):
            return message
        return json.dumps(message)

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent.append(message)


class FakeRegistry:
    def __init__(self):
        self.register_client_calls: list[tuple[str, Any]] = []
        self.unregister_websocket_calls: list[Any] = []

    def register_client(self, client_id: str, websocket: Any) -> None:
        self.register_client_calls.append((client_id, websocket))

    def unregister_websocket(self, websocket: Any) -> None:
        self.unregister_websocket_calls.append(websocket)


class FakeSessionManager:
    def __init__(self):
        self.removed: list[str] = []

    def remove(self, session_id: str) -> None:
        self.removed.append(session_id)


class FakeAgent:
    def __init__(self, persona_id: str = "luna", status: dict[str, Any] | None = None):
        self.persona = SimpleNamespace(persona_id=persona_id)
        self.status = status or {"temperature": 0.2}

    def get_status(self) -> dict[str, Any]:
        return dict(self.status)


async def test_websocket_route_service_handles_invalid_json_status_and_cleanup():
    from server.websocket_route_service import WebSocketRouteService

    websocket = FakeWebSocket([
        "not-json",
        {"type": "status", "client_id": "client-1"},
    ])
    registry = FakeRegistry()
    session_manager = FakeSessionManager()
    agent = FakeAgent()
    service = WebSocketRouteService(
        registry=registry,
        session_manager=session_manager,
    )

    await service.handle_connection(
        websocket,
        initial_session_id="session-1",
        initial_agent=agent,
    )

    assert websocket.sent == [
        {"type": "error", "content": "Invalid JSON"},
        {"type": "status", "temperature": 0.2},
    ]
    assert registry.register_client_calls == [("client-1", websocket)]
    assert registry.unregister_websocket_calls == [websocket]
    assert session_manager.removed == ["session-1"]


async def test_websocket_route_service_dispatches_tts_switch_and_demo_commands():
    from server.websocket_route_service import WebSocketRouteService

    class FakeTtsService:
        def __init__(self):
            self.calls: list[tuple[Any, str]] = []

        async def handle_request(self, websocket: Any, agent: Any, content: str) -> None:
            self.calls.append((agent, content))
            await websocket.send_json({"type": "tts_seen", "content": content})

    class FakePersonaSwitchService:
        def __init__(self, next_agent: Any):
            self.next_agent = next_agent
            self.calls: list[dict[str, Any]] = []

        async def switch(self, **kwargs: Any) -> tuple[str, Any]:
            self.calls.append(kwargs)
            return "session-2", self.next_agent

    class FakeDemoCommandService:
        def __init__(self, next_agent: Any):
            self.next_agent = next_agent
            self.calls: list[dict[str, Any]] = []

        async def handle(self, **kwargs: Any) -> SimpleNamespace:
            self.calls.append(kwargs)
            return SimpleNamespace(
                handled=True,
                session_id="session-3",
                agent=self.next_agent,
            )

    agent_a = FakeAgent("luna", {"temperature": 0.1})
    agent_b = FakeAgent("iris", {"temperature": 0.2})
    agent_c = FakeAgent("vivian", {"temperature": 0.3})
    websocket = FakeWebSocket([
        {"type": "tts_request", "content": "hello"},
        {
            "type": "switch_persona",
            "persona_id": "iris",
            "client_id": "client-1",
            "user_name": "Tester",
        },
        {"type": "demo_presets"},
    ])
    registry = FakeRegistry()
    session_manager = FakeSessionManager()
    tts_service = FakeTtsService()
    switch_service = FakePersonaSwitchService(agent_b)
    demo_service = FakeDemoCommandService(agent_c)
    service = WebSocketRouteService(
        registry=registry,
        session_manager=session_manager,
        tts_service=tts_service,
        persona_switch_service=switch_service,
        demo_command_service=demo_service,
    )

    await service.handle_connection(
        websocket,
        initial_session_id="session-1",
        initial_agent=agent_a,
    )

    assert tts_service.calls == [(agent_a, "hello")]
    assert switch_service.calls == [{
        "websocket": websocket,
        "current_session_id": "session-1",
        "persona_id": "iris",
        "user_name": "Tester",
        "client_id": "client-1",
    }]
    assert demo_service.calls == [{
        "websocket": websocket,
        "message": {"type": "demo_presets"},
        "agent": agent_b,
        "session_id": "session-2",
    }]
    assert session_manager.removed == ["session-3"]


async def test_websocket_route_service_buffers_chat_messages_before_flush():
    from server.websocket_route_service import WebSocketRouteService

    class FakeChatTurnService:
        def __init__(self):
            self.calls: list[dict[str, Any]] = []
            self.next_agent = FakeAgent("luna", {"temperature": 0.4})

        async def handle_messages(self, **kwargs: Any) -> SimpleNamespace:
            self.calls.append(kwargs)
            return SimpleNamespace(session_id="session-2", agent=self.next_agent)

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    websocket = FakeWebSocket([
        {"type": "chat", "content": "第一句", "persona_id": "luna"},
        {"type": "chat", "content": "第二句", "persona_id": "luna"},
        {"type": "typing", "active": False},
    ])
    chat_service = FakeChatTurnService()
    registry = FakeRegistry()
    session_manager = FakeSessionManager()
    service = WebSocketRouteService(
        registry=registry,
        session_manager=session_manager,
        chat_turn_service=chat_service,
        debounce_grace_sec=0,
        debounce_fallback_sec=0,
        sleep=fake_sleep,
    )

    await service.handle_connection(websocket)

    assert len(chat_service.calls) == 1
    assert chat_service.calls[0]["websocket"] is websocket
    assert chat_service.calls[0]["messages"] == [
        {"type": "chat", "content": "第一句", "persona_id": "luna"},
        {"type": "chat", "content": "第二句", "persona_id": "luna"},
    ]
    assert chat_service.calls[0]["agent"] is None
    assert chat_service.calls[0]["session_id"] is None
    assert 0 in sleep_calls
    assert session_manager.removed == ["session-2"]


def test_websocket_route_delegates_connection_loop_to_route_service_boundary():
    source = (ROOT / "server/routes/websocket.py").read_text(encoding="utf-8")
    route_body = source.split("async def websocket_chat", 1)[1]

    assert "from server.websocket_route_service import WebSocketRouteService" in source
    assert "service.handle_connection(ws)" in route_body
    assert "json.loads" not in source
    assert "asyncio.create_task" not in source
    assert "ctx.ws_chat_turn_service.handle_messages" not in source
    assert "ctx.ws_tts_service.handle_request" not in source
    assert "ctx.persona_switch_service.switch" not in source
    assert "ctx.ws_demo_command_service.handle" not in source


def test_app_context_and_bootstrap_expose_websocket_route_service_boundary():
    context_source = (ROOT / "server/context.py").read_text(encoding="utf-8")
    bootstrap_source = (ROOT / "server/bootstrap.py").read_text(encoding="utf-8")

    assert "from server.websocket_route_service import WebSocketRouteService" in context_source
    assert "ws_route_service: WebSocketRouteService | None = None" in context_source
    assert "from server.websocket_route_service import WebSocketRouteService" in bootstrap_source
    assert "context.ws_route_service = WebSocketRouteService(" in bootstrap_source
    assert '"ws_route_service": context.ws_route_service' in bootstrap_source
