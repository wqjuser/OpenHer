"""WebSocket completed-turn delivery service tests."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class FakeWebSocket:
    def __init__(self):
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


class FakeChatLogStore:
    def __init__(self):
        self.saved_messages: list[dict[str, Any]] = []
        self.saved_turns: list[dict[str, Any]] = []

    def save_message(self, **kwargs: Any) -> None:
        self.saved_messages.append(kwargs)

    def save_turn(self, **kwargs: Any) -> None:
        self.saved_turns.append(kwargs)


async def test_delivery_service_delivers_segments_and_persists_chat_log():
    from server.websocket_delivery import WebSocketCompletedTurnDeliveryService

    class FakeAgent:
        def get_status(self) -> dict[str, Any]:
            return {
                "modality": "文字",
                "segments": ["第一句", "第二句"],
                "delays_ms": [0, 1],
                "temperature": 0.2,
            }

        def get_debug_status(self) -> dict[str, str]:
            return {"debug_key": "debug_value"}

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    websocket = FakeWebSocket()
    chat_log = FakeChatLogStore()
    service = WebSocketCompletedTurnDeliveryService(
        chat_log_store=chat_log,
        sleep=fake_sleep,
    )

    await service.deliver_completed_turn(
        websocket=websocket,
        agent=FakeAgent(),
        session_id="session-1",
        persona_id="luna",
        client_id="client-1",
        merged_text="你好",
        clean_reply_text="完整回复",
        debug_mode=True,
    )

    assert sleep_calls == [0.3]
    assert websocket.sent == [
        {
            "type": "chat_end",
            "reply": "第一句",
            "modality": "文字",
            "image_url": None,
            "temperature": 0.2,
            "debug": {"debug_key": "debug_value"},
        },
        {
            "type": "chat_start",
            "session_id": "session-1",
        },
        {
            "type": "chat_end",
            "reply": "第二句",
            "modality": "文字",
            "image_url": None,
            "temperature": 0.2,
            "debug": {"debug_key": "debug_value"},
        },
    ]
    assert chat_log.saved_turns == [
        {
            "client_id": "client-1",
            "persona_id": "luna",
            "user_msg": "你好",
            "agent_reply": "第一句",
            "modality": "文字",
            "image_url": None,
        }
    ]
    assert chat_log.saved_messages == [
        {
            "client_id": "client-1",
            "persona_id": "luna",
            "role": "assistant",
            "content": "第二句",
            "modality": "文字",
        }
    ]


async def test_delivery_service_delivers_silence_and_audio_without_client_log(tmp_path):
    from server.websocket_delivery import WebSocketCompletedTurnDeliveryService

    audio_path = tmp_path / "reply.wav"
    audio_path.write_bytes(b"audio-bytes")

    class FakeAgent:
        def get_status(self) -> dict[str, Any]:
            return {
                "modality": "静默",
                "audio_path": str(audio_path),
                "temperature": 0.1,
            }

    websocket = FakeWebSocket()
    chat_log = FakeChatLogStore()
    service = WebSocketCompletedTurnDeliveryService(
        chat_log_store=chat_log,
        audio_format_resolver=lambda _path: "wav",
    )

    await service.deliver_completed_turn(
        websocket=websocket,
        agent=FakeAgent(),
        session_id="session-1",
        persona_id="luna",
        client_id=None,
        merged_text="你好",
        clean_reply_text="",
        debug_mode=False,
    )

    assert websocket.sent == [
        {
            "type": "silence",
            "session_id": "session-1",
            "modality": "静默",
            "temperature": 0.1,
        },
        {
            "type": "tts_audio",
            "audio": base64.b64encode(b"audio-bytes").decode(),
            "format": "wav",
        },
    ]
    assert chat_log.saved_turns == []
    assert chat_log.saved_messages == []


def test_websocket_chat_service_delegates_completed_turn_delivery():
    source = (ROOT / "server/websocket_chat.py").read_text(encoding="utf-8")

    assert (
        "from server.websocket_delivery import WebSocketCompletedTurnDeliveryService"
        in source
    )
    assert "delivery_service" in source
    assert "deliver_completed_turn(" in source
    assert "def _deliver_segments(" not in source
    assert "def _deliver_audio(" not in source
    assert "def _log_and_persist_turn(" not in source
    assert "def _image_url(" not in source
