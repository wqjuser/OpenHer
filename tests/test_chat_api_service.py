"""REST chat API service boundary tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from server.schemas import ChatRequest


ROOT = Path(__file__).resolve().parents[1]


class FakeAgent:
    def __init__(self, result: dict[str, Any] | None = None):
        self.result = result or {
            "reply": "你好",
            "modality": "文字",
            "image_path": "/tmp/selfie/luna.png",
        }
        self.chat_calls: list[str] = []
        self.status = {"temperature": 0.42, "mood": "curious"}

    async def chat(self, message: str) -> dict[str, Any]:
        self.chat_calls.append(message)
        return self.result

    def get_status(self) -> dict[str, Any]:
        return dict(self.status)


class FailingAgent:
    async def chat(self, _message: str) -> dict[str, Any]:
        raise RuntimeError("provider unavailable")

    def get_status(self) -> dict[str, Any]:
        raise AssertionError("status should not be read after provider failure")


class FakeSessionManager:
    def __init__(self, agent: Any):
        self.agent = agent
        self.get_or_create_calls: list[tuple[Any, ...]] = []
        self.get_entry_calls: list[str] = []
        self.persisted_agents: list[Any] = []

    def get_or_create(
        self,
        session_id: str | None,
        persona_id: str,
        user_name: str | None,
        client_id: str | None,
    ) -> tuple[str, Any]:
        self.get_or_create_calls.append((session_id, persona_id, user_name, client_id))
        return "session-1", self.agent

    def persist_agent(self, agent: Any) -> None:
        self.persisted_agents.append(agent)

    def get_entry(self, session_id: str) -> tuple[Any, float] | None:
        self.get_entry_calls.append(session_id)
        if session_id == "session-1":
            return self.agent, 123.0
        return None


class FakeChatLogStore:
    def __init__(self):
        self.saved_turns: list[dict[str, Any]] = []
        self.loaded_messages: list[dict[str, Any]] = [{
            "id": 42,
            "role": "user",
            "content": "hello",
        }]
        self.total = 1
        self.load_calls: list[tuple[Any, ...]] = []
        self.count_calls: list[tuple[Any, ...]] = []

    def save_turn(self, **kwargs: Any) -> None:
        self.saved_turns.append(kwargs)

    def load_messages(
        self,
        client_id: str,
        persona_id: str,
        limit: int,
        before_id: int | None = None,
    ) -> list[dict[str, Any]]:
        self.load_calls.append((client_id, persona_id, limit, before_id))
        return self.loaded_messages

    def count_messages(self, client_id: str, persona_id: str) -> int:
        self.count_calls.append((client_id, persona_id))
        return self.total


async def test_chat_api_service_processes_turn_persists_agent_and_saves_display_log():
    from server.chat_api_service import ChatApiService

    agent = FakeAgent()
    session_manager = FakeSessionManager(agent)
    chat_log_store = FakeChatLogStore()
    service = ChatApiService(
        session_manager=session_manager,
        chat_log_store=chat_log_store,
    )

    result = await service.chat(ChatRequest(
        message="hi",
        persona_id="luna",
        session_id=None,
        user_name="Codex",
        client_id="client-1",
    ))

    assert session_manager.get_or_create_calls == [(None, "luna", "Codex", "client-1")]
    assert agent.chat_calls == ["hi"]
    assert session_manager.persisted_agents == [agent]
    assert chat_log_store.saved_turns == [{
        "client_id": "client-1",
        "persona_id": "luna",
        "user_msg": "hi",
        "agent_reply": "你好",
        "modality": "文字",
    }]
    assert result.to_response() == {
        "session_id": "session-1",
        "response": "你好",
        "modality": "文字",
        "image_url": "/api/selfie/luna.png",
        "temperature": 0.42,
        "mood": "curious",
    }


async def test_chat_api_service_wraps_provider_failure_without_persisting_agent():
    from server.chat_api_service import ChatApiProviderError, ChatApiService

    agent = FailingAgent()
    session_manager = FakeSessionManager(agent)
    service = ChatApiService(session_manager=session_manager, chat_log_store=None)

    try:
        await service.chat(ChatRequest(message="hi", persona_id="luna"))
    except ChatApiProviderError as exc:
        assert isinstance(exc.original, RuntimeError)
        assert "provider unavailable" in str(exc.original)
    else:
        raise AssertionError("expected ChatApiProviderError")

    assert session_manager.persisted_agents == []


def test_chat_api_service_reads_session_status_and_wraps_missing_session():
    from server.chat_api_service import (
        ChatApiService,
        ChatApiServiceUnavailable,
        ChatApiSessionNotFound,
    )

    agent = FakeAgent()
    session_manager = FakeSessionManager(agent)
    service = ChatApiService(session_manager=session_manager, chat_log_store=None)

    assert service.session_status("session-1") == agent.status
    assert session_manager.get_entry_calls == ["session-1"]

    try:
        service.session_status("missing-session")
    except ChatApiSessionNotFound as exc:
        assert "Session not found" in str(exc)
    else:
        raise AssertionError("expected ChatApiSessionNotFound")

    unavailable_service = ChatApiService(session_manager=None, chat_log_store=None)
    try:
        unavailable_service.session_status("session-1")
    except ChatApiServiceUnavailable as exc:
        assert "Session manager is not initialized" in str(exc)
    else:
        raise AssertionError("expected ChatApiServiceUnavailable")


def test_chat_api_service_reads_display_history_or_empty_fallback():
    from server.chat_api_service import ChatApiService

    store = FakeChatLogStore()
    service = ChatApiService(session_manager=None, chat_log_store=store)

    response = service.chat_history(
        persona_id="luna",
        client_id="client-1",
        limit=25,
        before_id=42,
    )

    assert response == {"messages": store.loaded_messages, "total": 1}
    assert store.load_calls == [("client-1", "luna", 25, 42)]
    assert store.count_calls == [("client-1", "luna")]

    empty_service = ChatApiService(session_manager=None, chat_log_store=None)
    assert empty_service.chat_history(
        persona_id="luna",
        client_id="client-1",
        limit=25,
        before_id=None,
    ) == {"messages": [], "total": 0}


def test_chat_route_delegates_post_chat_turn_to_service_boundary():
    source = (ROOT / "server/routes/chat.py").read_text(encoding="utf-8")
    chat_api_body = source.split("async def chat_api", 1)[1].split("@router.get", 1)[0]

    assert "from server.chat_api_service import" in source
    assert "ChatApiService" in source
    assert "ChatApiProviderError" in source
    assert "result = await service.chat(req)" in chat_api_body
    assert "return result.to_response()" in chat_api_body
    assert "get_or_create(" not in chat_api_body
    assert "agent.chat(" not in chat_api_body
    assert "persist_agent(" not in chat_api_body
    assert "save_turn(" not in chat_api_body
    assert "os.path.basename" not in chat_api_body


def test_chat_routes_delegate_session_status_and_history_to_service_boundary():
    source = (ROOT / "server/routes/chat.py").read_text(encoding="utf-8")
    session_body = source.split("async def session_status", 1)[1].split("@router.get", 1)[0]
    history_body = source.split("async def get_chat_history", 1)[1]

    assert "ChatApiSessionNotFound" in source
    assert "service.session_status(session_id)" in session_body
    assert "service.chat_history(" in history_body
    assert "ctx.session_manager.get_entry" not in session_body
    assert "agent.get_status()" not in session_body
    assert "ctx.chat_log_store.load_messages" not in history_body
    assert "ctx.chat_log_store.count_messages" not in history_body


def test_app_context_and_bootstrap_expose_chat_api_service_boundary():
    context_source = (ROOT / "server/context.py").read_text(encoding="utf-8")
    bootstrap_source = (ROOT / "server/bootstrap.py").read_text(encoding="utf-8")

    assert "from server.chat_api_service import ChatApiService" in context_source
    assert "chat_api_service: ChatApiService | None = None" in context_source
    assert "from server.chat_api_service import ChatApiService" in bootstrap_source
    assert "context.chat_api_service = ChatApiService(" in bootstrap_source
    assert '"chat_api_service": context.chat_api_service' in bootstrap_source
