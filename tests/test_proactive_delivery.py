"""Proactive outbox delivery boundary tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class FakeStateStore:
    def __init__(self):
        self.try_send_calls: list[tuple[str, str, str]] = []
        self.failed_calls: list[tuple[str, str, str]] = []
        self.delivered_calls: list[tuple[str, str, str]] = []

    def outbox_try_send(self, user_id: str, persona_id: str, tick_id: str):
        self.try_send_calls.append((user_id, persona_id, tick_id))
        return {"tick_id": tick_id}

    def outbox_mark_failed(self, user_id: str, persona_id: str, tick_id: str) -> None:
        self.failed_calls.append((user_id, persona_id, tick_id))

    def outbox_mark_delivered(self, user_id: str, persona_id: str, tick_id: str) -> None:
        self.delivered_calls.append((user_id, persona_id, tick_id))


class FakeWebSocket:
    def __init__(self):
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


class FailingWebSocket:
    async def send_json(self, _msg: dict[str, Any]) -> None:
        raise RuntimeError("closed")


class FakeEverMemos:
    available = True

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def store_proactive_turn(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class FakeAgent:
    def __init__(self, result: dict[str, Any]):
        self.result = result
        self.persona = SimpleNamespace(name="Luna")
        self._group_id = "group-1"
        self.chat_calls: list[tuple[str, bool]] = []

    async def chat(self, stimulus: str, is_proactive: bool = False):
        self.chat_calls.append((stimulus, is_proactive))
        return self.result


def proactive_row() -> dict[str, str]:
    return {
        "user_id": "user-1",
        "persona_id": "luna",
        "tick_id": "tick-1",
        "reply": "原始主动表达",
        "drive_id": "connection",
    }


async def test_proactive_outbox_delivery_reprocesses_segments_and_marks_delivered():
    from server.proactive_delivery import ProactiveOutboxDeliveryService

    state_store = FakeStateStore()
    evermemos = FakeEverMemos()
    websocket = FakeWebSocket()
    ws_connections = {"session-1": {websocket}}
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    agent = FakeAgent({
        "reply": "aggregate reply",
        "modality": "文字",
        "segments": ["第一句", "第二句"],
        "delays_ms": [0, 1],
    })
    service = ProactiveOutboxDeliveryService(
        state_store=state_store,
        evermemos=evermemos,
        ws_connections=ws_connections,
        sleep=fake_sleep,
    )

    result = await service.deliver(agent, "session-1", proactive_row())

    assert state_store.try_send_calls == [("user-1", "luna", "tick-1")]
    assert len(agent.chat_calls) == 1
    assert agent.chat_calls[0][1] is True
    assert "原始主动表达" in agent.chat_calls[0][0]
    assert sleep_calls == [0.3]
    assert websocket.sent == [
        {
            "type": "chat_end",
            "reply": "第一句",
            "modality": "文字",
            "proactive": True,
            "drive": "connection",
            "persona": "Luna",
        },
        {
            "type": "chat_start",
            "session_id": "session-1",
        },
        {
            "type": "chat_end",
            "reply": "第二句",
            "modality": "文字",
            "proactive": True,
            "drive": "connection",
            "persona": "Luna",
        },
    ]
    assert evermemos.calls == [
        {
            "user_id": "user-1",
            "persona_id": "luna",
            "persona_name": "Luna",
            "group_id": "group-1",
            "reply": "aggregate reply",
            "tick_id": "tick-1",
        }
    ]
    assert state_store.failed_calls == []
    assert state_store.delivered_calls == [("user-1", "luna", "tick-1")]
    assert result.attempted is True
    assert result.delivered is True
    assert result.ws_push_ok is True
    assert result.ws_push_failed is False
    assert result.sent_count == 1
    assert result.reply == "aggregate reply"


async def test_proactive_outbox_delivery_marks_failed_when_no_websocket_accepts():
    from server.proactive_delivery import ProactiveOutboxDeliveryService

    state_store = FakeStateStore()
    websocket = FailingWebSocket()
    session_connections = {"session-1": {websocket}}
    service = ProactiveOutboxDeliveryService(
        state_store=state_store,
        evermemos=None,
        ws_connections=session_connections,
    )

    result = await service.deliver(
        FakeAgent({"reply": "hello", "modality": "文字"}),
        "session-1",
        proactive_row(),
    )

    assert session_connections["session-1"] == set()
    assert state_store.failed_calls == [("user-1", "luna", "tick-1")]
    assert state_store.delivered_calls == []
    assert result.attempted is True
    assert result.delivered is False
    assert result.ws_push_ok is False
    assert result.ws_push_failed is True


def test_proactive_service_delegates_outbox_delivery_boundary():
    source = (ROOT / "server/proactive_service.py").read_text(encoding="utf-8")

    assert "from server.proactive_delivery import" in source
    assert "ProactiveOutboxDeliveryService" in source
    assert "delivery_service" in source
    assert "self.delivery_service.deliver(" in source
    assert ".send_json(" not in source
    assert "store_proactive_turn(" not in source
    assert "outbox_try_send(" not in source
    assert "outbox_mark_failed(" not in source
    assert "outbox_mark_delivered(" not in source
