"""WebSocket demo command service tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import unittest
from typing import Any


class WebSocketDemoCommandServiceTests(unittest.TestCase):
    def test_demo_scenario_applies_preset_and_delivers_forced_proactive(self):
        from server.websocket_demo import WebSocketDemoCommandService

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        class FakeDemoController:
            instances: list["FakeDemoController"] = []

            def __init__(self, agent):
                self.agent = agent
                self.loaded: list[str] = []
                FakeDemoController.instances.append(self)

            def load_presets_file(self, path):
                self.loaded.append(path)

            def apply_scenario(self, scenario_id):
                return {
                    "applied_scenario": scenario_id,
                    "temperature": 0.5,
                }

            async def force_proactive(self, simulated_hours: float = 0):
                return {
                    "temperature": 0.6,
                    "proactive_fired": True,
                    "proactive_reply": "raw impulse",
                }

        class FakeProactiveDelivery:
            def __init__(self):
                self.calls: list[dict[str, Any]] = []

            async def deliver_forced_proactive(self, **kwargs):
                self.calls.append(kwargs)
                return "rewritten impulse"

        proactive_delivery = FakeProactiveDelivery()
        ws = FakeWebSocket()
        agent = object()

        with tempfile.NamedTemporaryFile(suffix=".yaml") as presets:
            service = WebSocketDemoCommandService(
                demo_controller_factory=FakeDemoController,
                proactive_delivery=proactive_delivery,
                get_or_create_session=lambda *_args: (_ for _ in ()).throw(AssertionError("not used")),
                presets_file=presets.name,
            )
            result = asyncio.run(service.handle(
                websocket=ws,
                message={"type": "demo_scenario", "scenario_id": "about_to_snap"},
                agent=agent,
                session_id="session-1",
            ))

        self.assertTrue(result.handled)
        self.assertEqual(result.session_id, "session-1")
        self.assertIs(result.agent, agent)
        self.assertEqual(FakeDemoController.instances[0].loaded, [presets.name])
        self.assertEqual(len(proactive_delivery.calls), 1)
        self.assertIs(proactive_delivery.calls[0]["websocket"], ws)
        self.assertIs(proactive_delivery.calls[0]["agent"], agent)
        self.assertEqual(proactive_delivery.calls[0]["session_id"], "session-1")
        self.assertEqual(ws.sent, [
            {
                "type": "demo_state",
                "applied_scenario": "about_to_snap",
                "temperature": 0.5,
            },
            {
                "type": "demo_state",
                "temperature": 0.6,
                "proactive_fired": True,
                "proactive_reply": "raw impulse",
            },
        ])

    def test_demo_scenario_propagates_websocket_disconnect_during_delivery(self):
        from starlette.websockets import WebSocketDisconnect

        from server.websocket_demo import WebSocketDemoCommandService

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        class FakeDemoController:
            def __init__(self, agent):
                self.agent = agent

            def load_presets_file(self, path):
                pass

            def apply_scenario(self, scenario_id):
                return {"applied_scenario": scenario_id, "temperature": 0.5}

            async def force_proactive(self, simulated_hours: float = 0):
                return {"proactive_fired": True, "proactive_reply": "raw impulse"}

        class DisconnectingDelivery:
            async def deliver_forced_proactive(self, **kwargs):
                raise WebSocketDisconnect(code=1006)

        service = WebSocketDemoCommandService(
            demo_controller_factory=FakeDemoController,
            proactive_delivery=DisconnectingDelivery(),
            get_or_create_session=lambda *_args: (_ for _ in ()).throw(AssertionError("not used")),
            presets_file=str(Path("unused.yaml")),
        )

        with self.assertRaises(WebSocketDisconnect):
            asyncio.run(service.handle(
                websocket=FakeWebSocket(),
                message={"type": "demo_scenario", "scenario_id": "about_to_snap"},
                agent=object(),
                session_id="session-1",
            ))

    def test_demo_inject_memory_autocreates_matching_session(self):
        from server.websocket_demo import WebSocketDemoCommandService

        class FakePersona:
            persona_id = "luna"

        class FakeAgent:
            persona = FakePersona()

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        class FakeDemoController:
            def __init__(self, agent):
                self.agent = agent

            async def inject_memory(self, content, category):
                return {
                    "injected": True,
                    "content": content,
                    "category": category,
                    "agent_id": id(self.agent),
                }

        created_calls: list[tuple[Any, ...]] = []
        new_agent = FakeAgent()

        def get_or_create(session_id, persona_id, user_name, client_id):
            created_calls.append((session_id, persona_id, user_name, client_id))
            return "new-session", new_agent

        service = WebSocketDemoCommandService(
            demo_controller_factory=FakeDemoController,
            proactive_delivery=None,
            get_or_create_session=get_or_create,
            presets_file=str(Path("unused.yaml")),
        )
        ws = FakeWebSocket()

        result = asyncio.run(service.handle(
            websocket=ws,
            message={
                "type": "demo_inject_memory",
                "persona_id": "luna",
                "client_id": "client-1",
                "content": "喜欢美式咖啡",
                "category": "preference",
            },
            agent=None,
            session_id=None,
        ))

        self.assertTrue(result.handled)
        self.assertEqual(result.session_id, "new-session")
        self.assertIs(result.agent, new_agent)
        self.assertEqual(created_calls, [(None, "luna", None, "client-1")])
        self.assertEqual(ws.sent, [{
            "type": "demo_memory",
            "injected": True,
            "content": "喜欢美式咖啡",
            "category": "preference",
            "agent_id": id(new_agent),
        }])


if __name__ == "__main__":
    unittest.main()
