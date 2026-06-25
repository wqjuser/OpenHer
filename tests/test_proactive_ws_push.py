"""Shared proactive WebSocket push boundary tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class FakeWebSocket:
    def __init__(self):
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


async def test_push_service_sends_segmented_payload_with_optional_metadata():
    from server.proactive_ws_push import (
        ProactivePushPayload,
        ProactiveWebSocketPushService,
    )

    websocket = FakeWebSocket()
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    service = ProactiveWebSocketPushService(sleep=fake_sleep)

    await service.push(
        websocket,
        session_id="session-1",
        payload=ProactivePushPayload(
            reply="aggregate reply",
            modality="文字",
            segments=["第一句", "第二句"],
            delays_ms=[0, 1],
            drive="connection",
            persona="Luna",
        ),
    )

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


async def test_push_service_sends_single_payload_without_optional_metadata():
    from server.proactive_ws_push import (
        ProactivePushPayload,
        ProactiveWebSocketPushService,
    )

    websocket = FakeWebSocket()
    service = ProactiveWebSocketPushService()

    await service.push(
        websocket,
        session_id="session-1",
        payload=ProactivePushPayload(reply="hello", modality="文字"),
    )

    assert websocket.sent == [
        {
            "type": "proactive",
            "content": "hello",
            "modality": "文字",
        }
    ]


def test_proactive_outbox_delivery_delegates_websocket_push_boundary():
    source = (ROOT / "server/proactive_delivery.py").read_text(encoding="utf-8")

    assert "from server.proactive_ws_push import" in source
    assert "ProactivePushPayload" in source
    assert "ProactiveWebSocketPushService" in source
    assert "self.push_service.push(" in source
    assert "def _send_segments(" not in source


def test_demo_proactive_delivery_delegates_websocket_push_boundary():
    source = (ROOT / "server/websocket_demo.py").read_text(encoding="utf-8")
    service_source = source.split("class WebSocketDemoCommandService", 1)[0]

    assert "from server.proactive_ws_push import" in source
    assert "ProactivePushPayload" in service_source
    assert "ProactiveWebSocketPushService" in service_source
    assert "self.push_service.push(" in service_source
    assert ".send_json(" not in service_source
    assert '"type": "chat_end"' not in service_source
    assert '"type": "proactive"' not in service_source
