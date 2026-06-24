"""WebSocket chat turn service tests."""

from __future__ import annotations

import asyncio
import unittest
from typing import Any


class WebSocketChatTurnServiceTests(unittest.TestCase):
    def test_handle_messages_registers_session_delivers_segments_and_logs_turn(self):
        from server.websocket_chat import WebSocketChatTurnService
        from server.websocket_registry import WebSocketConnectionRegistry

        class FakePersona:
            persona_id = "luna"

        class FakeAgent:
            persona = FakePersona()
            history: list[Any] = []

            async def chat_stream(self, _text):
                if False:
                    yield ""

            def get_status(self):
                return {
                    "modality": "文字",
                    "segments": ["第一句", "第二句"],
                    "delays_ms": [0, 1],
                    "temperature": 0.2,
                }

            def get_debug_status(self):
                return {"debug_key": "debug_value"}

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        class FakeChatLogStore:
            def __init__(self):
                self.saved_messages: list[dict[str, Any]] = []
                self.saved_turns: list[dict[str, Any]] = []

            def save_message(self, **kwargs):
                self.saved_messages.append(kwargs)

            def save_turn(self, **kwargs):
                self.saved_turns.append(kwargs)

        async def fake_stream_to_ws(_raw_stream, _send, *, on_feel_done=None, on_reply_complete=None):
            if on_feel_done:
                await on_feel_done()
            if on_reply_complete:
                await on_reply_complete("完整回复", "文字")

        sleep_calls: list[float] = []

        async def fake_sleep(delay: float):
            sleep_calls.append(delay)

        agent = FakeAgent()
        websocket = FakeWebSocket()
        registry = WebSocketConnectionRegistry()
        chat_log = FakeChatLogStore()

        def get_or_create(session_id, persona_id, user_name, client_id):
            self.assertIsNone(session_id)
            self.assertEqual(persona_id, "luna")
            self.assertEqual(user_name, "Tester")
            self.assertEqual(client_id, "client-1")
            return "session-1", agent

        service = WebSocketChatTurnService(
            registry=registry,
            get_or_create_session=get_or_create,
            chat_log_store=chat_log,
            stream_to_ws=fake_stream_to_ws,
            sleep=fake_sleep,
        )

        result = asyncio.run(service.handle_messages(
            websocket=websocket,
            messages=[
                {
                    "type": "chat",
                    "content": "你好",
                    "persona_id": "luna",
                    "user_name": "Tester",
                    "client_id": "client-1",
                    "greeting": "初次见面",
                    "debug": True,
                },
                {
                    "type": "chat",
                    "content": "第二句用户输入",
                    "persona_id": "luna",
                    "client_id": "client-1",
                },
            ],
            agent=None,
            session_id=None,
        ))

        self.assertEqual(result.session_id, "session-1")
        self.assertIs(result.agent, agent)
        self.assertEqual(registry.connections_for_session("session-1"), {websocket})
        self.assertIs(registry.latest_client("client-1"), websocket)
        self.assertEqual(sleep_calls, [0.3])
        self.assertEqual(websocket.sent, [
            {
                "type": "chat_start",
                "session_id": "session-1",
                "user_content": "你好\n第二句用户输入",
            },
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
        ])
        self.assertEqual(chat_log.saved_messages, [
            {
                "client_id": "client-1",
                "persona_id": "luna",
                "role": "assistant",
                "content": "初次见面",
                "modality": "文字",
            },
            {
                "client_id": "client-1",
                "persona_id": "luna",
                "role": "assistant",
                "content": "第二句",
                "modality": "文字",
            },
        ])
        self.assertEqual(chat_log.saved_turns[0]["user_msg"], "你好\n第二句用户输入")
        self.assertEqual(chat_log.saved_turns[0]["agent_reply"], "第一句")


if __name__ == "__main__":
    unittest.main()
