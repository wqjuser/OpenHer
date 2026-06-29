"""Regression tests for security and contract fixes.

These tests intentionally avoid importing package ``__init__`` files so they can
run in a minimal Python environment while provider dependencies are absent.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ParserRegressionTests(unittest.TestCase):
    def test_english_modality_aliases_are_canonical(self):
        parser = load_module("openher_parser_direct", "agent/parser.py")

        self.assertEqual(parser._parse_modality("text"), "文字")
        self.assertEqual(parser._parse_modality("voice"), "语音")
        self.assertEqual(parser._parse_modality("silence"), "静默")
        self.assertEqual(parser._parse_modality("emoji"), "表情")
        self.assertEqual(parser._parse_modality("photo"), "照片")
        self.assertEqual(parser._parse_modality("split"), "多条拆分")
        self.assertEqual(
            parser.extract_reply(
                "[Inner Monologue]nervous\n"
                "[Final Reply]hello\n"
                "[Expression Mode]voice message because feeling emotional"
            )[2],
            "语音",
        )

    def test_unknown_modality_defaults_to_text(self):
        parser = load_module("openher_parser_direct_unknown", "agent/parser.py")

        self.assertEqual(parser._parse_modality("something random"), "文字")
        self.assertEqual(parser._parse_modality(""), "文字")


class SandboxRegressionTests(unittest.TestCase):
    def test_shell_metacharacters_are_rejected(self):
        sandbox = load_module("openher_sandbox_direct", "agent/skills/sandbox_executor.py")

        result = asyncio.run(sandbox.execute_shell("echo safe; echo injected"))

        self.assertFalse(result["success"])
        self.assertIn("not allowed", result["stderr"].lower())

    def test_shell_does_not_expand_environment_variables(self):
        sandbox = load_module("openher_sandbox_no_expand", "agent/skills/sandbox_executor.py")

        result = asyncio.run(sandbox.execute_shell("printf %s $HOME"))

        self.assertTrue(result["success"])
        self.assertEqual(result["stdout"], "$HOME")


class PathSecurityRegressionTests(unittest.TestCase):
    def test_safe_child_path_rejects_parent_escape(self):
        path_security = load_module("openher_path_security", "engine/path_security.py")
        base = ROOT / ".cache" / "selfie"

        with self.assertRaises(ValueError):
            path_security.safe_child_path(base, "../../README.md")

    def test_safe_child_path_accepts_nested_child(self):
        path_security = load_module("openher_path_security_child", "engine/path_security.py")
        base = ROOT / ".cache" / "selfie"

        resolved = path_security.safe_child_path(base, "luna/photo.png")

        self.assertEqual(resolved, (base / "luna" / "photo.png").resolve())

    def test_selfie_handler_uses_repo_root_media_paths(self):
        from skills.modality.selfie_gen import handler

        self.assertEqual(
            handler.get_idimage_dir("luna"),
            ROOT / "persona" / "personas" / "luna" / "idimage",
        )
        self.assertEqual(
            handler.get_selfie_cache_dir("luna"),
            ROOT / ".cache" / "selfie" / "luna",
        )


class TTSResultRegressionTests(unittest.TestCase):
    def test_tts_result_carries_mime_type_and_format(self):
        tts_base = load_module("openher_tts_base_direct", "providers/speech/tts/base.py")

        result = tts_base.TTSResult(success=True, audio_path="/tmp/a.wav", mime_type="audio/wav")

        self.assertEqual(result.mime_type, "audio/wav")
        self.assertEqual(result.audio_format, "wav")


class MediaServingRegressionTests(unittest.TestCase):
    def test_media_type_uses_file_signature_before_extension(self):
        import tempfile
        import main

        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            tmp.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01")
            tmp.flush()

            self.assertEqual(main._media_type_for_file(tmp.name), "image/jpeg")


class LightweightImportRegressionTests(unittest.TestCase):
    def test_lightweight_submodules_do_not_require_provider_dependencies(self):
        importlib.import_module("agent.parser")
        importlib.import_module("engine.chat_log_store")
        importlib.import_module("engine.genome.style_memory")


class ChatHistoryContractTests(unittest.TestCase):
    def test_display_chat_log_is_not_restored_into_agent_history(self):
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")

        self.assertEqual(
            main_source.count("agent.history = ["),
            0,
            "chat.db display history must not be restored into agent.history",
        )

    def test_session_reuse_uses_client_id_and_persona_id(self):
        session_source = (ROOT / "server" / "session_manager.py").read_text(encoding="utf-8")

        self.assertNotIn("getattr(agent_candidate.persona, 'id'", session_source)
        self.assertIn('getattr(agent_candidate.persona, "persona_id", None) == persona_id', session_source)
        self.assertIn('getattr(agent_candidate, "_client_id", None) == client_id', session_source)


class SessionManagerRegressionTests(unittest.TestCase):
    def test_session_manager_reuses_session_by_persona_and_client_id(self):
        from server.session_agent_factory import SessionAgentFactory
        from server.session_manager import SessionManager

        class Persona:
            persona_id = "luna"

        class PersonaLoader:
            def get(self, persona_id):
                return Persona() if persona_id == "luna" else None

        class FakeAgent:
            def __init__(self, **kwargs):
                self.persona = kwargs["persona"]
                self.user_id = kwargs["user_id"]
                self._client_id = None
                self.pre_warm_count = 0

            def pre_warm(self):
                self.pre_warm_count += 1

        agent_factory = SessionAgentFactory(
            persona_loader=cast(Any, PersonaLoader()),
            llm_client=cast(Any, None),
            task_skill_engine=cast(Any, None),
            modality_skill_engine=cast(Any, None),
            memory_store=cast(Any, None),
            state_store=None,
            evermemos=None,
            genome_data_dir="/tmp/openher-test",
            agent_factory=FakeAgent,
        )
        manager = SessionManager(
            agent_factory=agent_factory,
            state_store=None,
            evermemos=None,
        )
        first_sid, first_agent = manager.get_or_create(None, "luna", None, "client-1")
        second_sid, second_agent = manager.get_or_create(None, "luna", None, "client-1")

        fake_first_agent = cast(Any, first_agent)
        self.assertEqual(first_sid, second_sid)
        self.assertIs(first_agent, second_agent)
        self.assertEqual(fake_first_agent.user_id, first_sid)
        self.assertEqual(fake_first_agent._client_id, "client-1")
        self.assertEqual(fake_first_agent.pre_warm_count, 1)


class WebSocketRegistryRegressionTests(unittest.TestCase):
    def test_registry_tracks_session_peers_and_latest_client_socket(self):
        from server.websocket_registry import WebSocketConnectionRegistry

        registry = WebSocketConnectionRegistry()
        first_ws = object()
        second_ws = object()

        registry.register_session("session-1", first_ws)
        registry.register_session("session-1", second_ws)
        registry.register_client("client-1", first_ws)
        registry.register_client("client-1", second_ws)

        self.assertEqual(registry.connections_for_session("session-1"), {first_ws, second_ws})
        self.assertIs(registry.latest_client("client-1"), second_ws)

        registry.unregister_session("session-1", first_ws)

        self.assertEqual(registry.connections_for_session("session-1"), {second_ws})

        registry.unregister_websocket(second_ws)

        self.assertEqual(registry.connections_for_session("session-1"), set())
        self.assertIsNone(registry.latest_client("client-1"))


class DemoInjectServiceRegressionTests(unittest.TestCase):
    def test_send_builds_demo_inject_message_for_latest_client_socket(self):
        from server.demo_inject import DemoInjectService
        from server.websocket_registry import WebSocketConnectionRegistry

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        ws = FakeWebSocket()
        registry = WebSocketConnectionRegistry()
        registry.register_client("client-1", ws)
        service = DemoInjectService(registry)

        result = asyncio.run(service.send({
            "client_id": "client-1",
            "action": "switch_tab",
            "tab": 2,
        }))

        self.assertEqual(result, {"ok": True, "sent_to": 1})
        self.assertEqual(ws.sent, [{
            "type": "demo_inject",
            "action": "switch_tab",
            "content": "",
            "persona_id": "",
            "scenario_id": "",
            "hours": 0,
            "tab": 2,
            "category": "",
        }])

    def test_send_failure_unregisters_stale_client_socket(self):
        from server.demo_inject import DemoInjectSendFailed, DemoInjectService
        from server.websocket_registry import WebSocketConnectionRegistry

        class FailingWebSocket:
            async def send_json(self, msg):
                raise RuntimeError("closed")

        registry = WebSocketConnectionRegistry()
        registry.register_client("client-1", FailingWebSocket())
        service = DemoInjectService(registry)

        with self.assertRaises(DemoInjectSendFailed):
            asyncio.run(service.send({
                "client_id": "client-1",
                "action": "switch_tab",
            }))

        self.assertIsNone(registry.latest_client("client-1"))


class WebSocketTTSServiceRegressionTests(unittest.TestCase):
    def test_tts_request_sends_base64_audio_with_resolved_persona_voice(self):
        import tempfile
        from server.ws_tts import WebSocketTTSService

        class FakeResult:
            success = True
            error = None
            audio_format = None

            def __init__(self, audio_path):
                self.audio_path = audio_path

        class FakeTTSEngine:
            def __init__(self, audio_path):
                self.audio_path = audio_path
                self.calls = []

            async def synthesize(self, **kwargs):
                self.calls.append(kwargs)
                return FakeResult(self.audio_path)

        class FakePersona:
            persona_id = "luna"

        class FakeAgent:
            persona = FakePersona()

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            audio.write(b"abc")
            audio.flush()

            tts_engine = FakeTTSEngine(audio.name)
            ws = FakeWebSocket()
            service = WebSocketTTSService(
                tts_engine=cast(Any, tts_engine),
                voice_resolver=lambda persona_id: f"{persona_id}-voice",
            )

            asyncio.run(service.handle_request(cast(Any, ws), cast(Any, FakeAgent()), "hello"))

        self.assertEqual(tts_engine.calls, [{"text": "hello", "voice_preset": "luna-voice"}])
        self.assertEqual(ws.sent, [{
            "type": "tts_audio",
            "audio": "YWJj",
            "format": "wav",
        }])

    def test_tts_request_sends_error_when_synthesis_fails(self):
        from server.ws_tts import WebSocketTTSService

        class FakeResult:
            success = False
            audio_path = None
            audio_format = None
            error = "no voice"

        class FakeTTSEngine:
            async def synthesize(self, **kwargs):
                return FakeResult()

        class FakePersona:
            persona_id = "luna"

        class FakeAgent:
            persona = FakePersona()

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        ws = FakeWebSocket()
        service = WebSocketTTSService(
            tts_engine=cast(Any, FakeTTSEngine()),
            voice_resolver=lambda persona_id: "voice",
        )

        asyncio.run(service.handle_request(cast(Any, ws), cast(Any, FakeAgent()), "hello"))

        self.assertEqual(ws.sent, [{
            "type": "error",
            "content": "TTS 失败: no voice",
        }])


class WebSocketPersonaSwitchServiceRegressionTests(unittest.TestCase):
    def test_switch_cleans_old_session_registers_new_session_and_notifies_client(self):
        from server.websocket_persona_switch import WebSocketPersonaSwitchService
        from server.websocket_registry import WebSocketConnectionRegistry

        class FakePersona:
            name = "Luna"

        class FakeAgent:
            persona = FakePersona()

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        removed_sessions: list[str] = []
        get_calls: list[tuple[Any, ...]] = []

        def get_or_create(session_id, persona_id, user_name, client_id):
            get_calls.append((session_id, persona_id, user_name, client_id))
            return "new-session", FakeAgent()

        registry = WebSocketConnectionRegistry()
        ws = FakeWebSocket()
        registry.register_session("old-session", ws)
        service = WebSocketPersonaSwitchService(
            registry=registry,
            get_or_create_session=get_or_create,
            remove_session=removed_sessions.append,
        )

        result = asyncio.run(service.switch(
            websocket=ws,
            current_session_id="old-session",
            persona_id="luna",
            user_name="Tester",
            client_id="client-1",
        ))

        self.assertIsNotNone(result)
        new_session_id, new_agent = cast(Any, result)
        self.assertEqual(new_session_id, "new-session")
        self.assertIsInstance(new_agent, FakeAgent)
        self.assertEqual(removed_sessions, ["old-session"])
        self.assertEqual(get_calls, [(None, "luna", "Tester", "client-1")])
        self.assertEqual(registry.connections_for_session("old-session"), set())
        self.assertEqual(registry.connections_for_session("new-session"), {ws})
        self.assertEqual(ws.sent, [{
            "type": "persona_switched",
            "session_id": "new-session",
            "persona": "Luna",
        }])

    def test_switch_sends_error_when_persona_does_not_exist(self):
        from server.websocket_persona_switch import WebSocketPersonaSwitchService
        from server.websocket_registry import WebSocketConnectionRegistry

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        removed_sessions: list[str] = []

        def get_or_create(session_id, persona_id, user_name, client_id):
            raise ValueError("角色 'missing' 不存在")

        registry = WebSocketConnectionRegistry()
        ws = FakeWebSocket()
        registry.register_session("old-session", ws)
        service = WebSocketPersonaSwitchService(
            registry=registry,
            get_or_create_session=get_or_create,
            remove_session=removed_sessions.append,
        )

        result = asyncio.run(service.switch(
            websocket=ws,
            current_session_id="old-session",
            persona_id="missing",
            user_name=None,
            client_id=None,
        ))

        self.assertIsNone(result)
        self.assertEqual(removed_sessions, ["old-session"])
        self.assertEqual(registry.connections_for_session("old-session"), set())
        self.assertEqual(ws.sent, [{
            "type": "error",
            "content": "角色 'missing' 不存在",
        }])


class WebSocketDemoProactiveServiceRegressionTests(unittest.TestCase):
    def test_forced_proactive_is_reprocessed_and_delivered_as_segments(self):
        from server.websocket_demo import WebSocketDemoProactiveService

        class FakeAgent:
            def __init__(self):
                self.calls: list[tuple[str, bool]] = []

            async def chat(self, stimulus, is_proactive=False):
                self.calls.append((stimulus, is_proactive))
                return {
                    "reply": "ignored aggregate reply",
                    "modality": "文字",
                    "segments": ["第一句", "第二句"],
                    "delays_ms": [0, 1],
                }

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        sleep_calls: list[float] = []

        async def fake_sleep(delay: float):
            sleep_calls.append(delay)

        agent = FakeAgent()
        ws = FakeWebSocket()
        service = WebSocketDemoProactiveService(sleep=fake_sleep)

        delivered = asyncio.run(service.deliver_forced_proactive(
            websocket=ws,
            agent=agent,
            session_id="session-1",
            proactive_result={
                "proactive_fired": True,
                "proactive_reply": "原始主动表达",
            },
        ))

        self.assertEqual(delivered, "ignored aggregate reply")
        self.assertEqual(len(agent.calls), 1)
        self.assertTrue(agent.calls[0][1])
        self.assertIn("原始主动表达", agent.calls[0][0])
        self.assertEqual(sleep_calls, [0.3])
        self.assertEqual(ws.sent, [
            {"type": "chat_end", "reply": "第一句", "modality": "文字", "proactive": True},
            {"type": "chat_start", "session_id": "session-1"},
            {"type": "chat_end", "reply": "第二句", "modality": "文字", "proactive": True},
        ])

    def test_forced_proactive_noops_when_nothing_fired(self):
        from server.websocket_demo import WebSocketDemoProactiveService

        class FakeAgent:
            async def chat(self, stimulus, is_proactive=False):
                raise AssertionError("chat should not run without a proactive impulse")

        class FakeWebSocket:
            def __init__(self):
                self.sent: list[dict[str, Any]] = []

            async def send_json(self, msg):
                self.sent.append(msg)

        ws = FakeWebSocket()
        service = WebSocketDemoProactiveService()

        delivered = asyncio.run(service.deliver_forced_proactive(
            websocket=ws,
            agent=FakeAgent(),
            session_id="session-1",
            proactive_result={"proactive_fired": False},
        ))

        self.assertIsNone(delivered)
        self.assertEqual(ws.sent, [])


class ProactiveDeliveryContractTests(unittest.TestCase):
    def test_outbox_is_not_delivered_when_no_websocket_send_succeeds(self):
        from server.proactive_service import ProactiveService

        class FakeStateStore:
            def __init__(self):
                self.failed = 0
                self.delivered = 0

            def outbox_try_send(self, user_id, persona_id, tick_id):
                return {"tick_id": tick_id}

            def outbox_mark_failed(self, user_id, persona_id, tick_id):
                self.failed += 1

            def outbox_mark_delivered(self, user_id, persona_id, tick_id):
                self.delivered += 1

        class FakePersona:
            name = "Luna"

        class FakeAgent:
            persona = FakePersona()
            _group_id = "group-1"

            async def chat(self, stimulus, is_proactive=False):
                return {"reply": "hello", "modality": "文字"}

        class FailingWebSocket:
            async def send_json(self, msg):
                raise RuntimeError("closed")

        state_store = FakeStateStore()
        service = ProactiveService(
            state_store=cast(Any, state_store),
            session_manager=cast(Any, None),
            evermemos=None,
            ws_connections={"session-1": {cast(Any, FailingWebSocket())}},
            persist_agent=lambda agent: None,
            instance_id="test",
            config={},
            interval_seconds=1,
            initial_delay_seconds=0,
        )

        asyncio.run(service.deliver_message(
            cast(Any, FakeAgent()),
            "session-1",
            {
                "user_id": "user-1",
                "persona_id": "luna",
                "tick_id": "tick-1",
                "reply": "raw hello",
                "drive_id": "social",
            },
        ))

        self.assertEqual(state_store.failed, 1)
        self.assertEqual(state_store.delivered, 0)
        self.assertEqual(service.metrics["ws_push_fail"], 1)
        self.assertEqual(service.metrics["outbox_delivered"], 0)


class CORSRegressionTests(unittest.TestCase):
    def test_cors_origins_are_configured_from_env_not_wildcard(self):
        from server.security import cors_origins_from_env

        with patch.dict(
            os.environ,
            {"OPENHER_CORS_ORIGINS": "*, http://localhost:3000, http://127.0.0.1:8000"},
        ):
            origins = cors_origins_from_env()

        self.assertNotIn("*", origins)
        self.assertEqual(origins, ["http://localhost:3000", "http://127.0.0.1:8000"])


class ServerBoundaryRegressionTests(unittest.TestCase):
    def test_provider_error_details_redact_configured_secrets(self):
        from server.errors import external_error_detail

        with patch.dict(os.environ, {"OPENHER_TEST_SECRET": "super-secret-value"}):
            detail = external_error_detail(
                "Provider failed",
                RuntimeError("bad key super-secret-value"),
            )

        self.assertIn("Provider failed: RuntimeError", detail)
        self.assertIn("[redacted]", detail)
        self.assertNotIn("super-secret-value", detail)


class APIAuthRegressionTests(unittest.TestCase):
    def test_optional_api_token_protects_http_and_websocket_entrypoints(self):
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")
        websocket_source = (ROOT / "server" / "routes" / "websocket.py").read_text(encoding="utf-8")

        self.assertIn("OPENHER_API_TOKEN", main_source)
        self.assertIn('server_app.middleware("http")(require_api_token)', main_source)
        self.assertIn("Authorization", main_source)
        self.assertIn("await ws.close(code=1008)", websocket_source)


class FastAPILifespanRegressionTests(unittest.TestCase):
    def test_server_uses_lifespan_instead_of_deprecated_on_event_hooks(self):
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("@app.on_event", main_source)
        self.assertIn("lifespan=", main_source)
        self.assertIn("@asynccontextmanager", main_source)


class ExternalEndpointErrorTests(unittest.TestCase):
    def test_external_endpoint_failures_return_json_errors(self):
        from fastapi.testclient import TestClient
        import main
        from server.context import AppContext, SessionManagerService, TTSEngineService

        class FailingAgent:
            async def chat(self, _message):
                raise RuntimeError("provider unavailable")

        class FailingSessionManager:
            def get_or_create(self, *_args):
                return "sid", FailingAgent()

            def persist_agent(self, _agent):
                raise AssertionError("failing agent should not be persisted")

        class FailingTTS:
            async def synthesize(self, **_kwargs):
                raise RuntimeError("tts unavailable")

        class FailingImageProvider:
            async def generate(self, **_kwargs):
                raise RuntimeError("image unavailable")

        context = AppContext()
        context.session_manager = cast(SessionManagerService, FailingSessionManager())
        context.tts_engine = cast(TTSEngineService, FailingTTS())
        app = main.create_app(context)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-image-key"}):
            with patch("providers.registry.get_image_gen", return_value=FailingImageProvider()):
                client = TestClient(app, raise_server_exceptions=False)
                chat_resp = client.post(
                    "/api/chat",
                    json={"message": "hi", "persona_id": "luna", "client_id": "qa"},
                )
                tts_resp = client.get("/api/tts?text=hi")
                image_resp = client.post("/api/image?prompt=portrait")

        for resp, label in (
            (chat_resp, "chat"),
            (tts_resp, "tts"),
            (image_resp, "image"),
        ):
            self.assertEqual(resp.status_code, 502, label)
            self.assertTrue(resp.headers["content-type"].startswith("application/json"), label)
            self.assertIn("detail", resp.json(), label)

    def test_external_failed_results_return_bad_gateway(self):
        from fastapi.testclient import TestClient
        import main
        from server.context import AppContext, TTSEngineService

        class FailedResult:
            success = False
            audio_path = None
            image_path = None
            error = "provider rejected request"

        class FailedTTS:
            async def synthesize(self, **_kwargs):
                return FailedResult()

        class FailedImageProvider:
            async def generate(self, **_kwargs):
                return FailedResult()

        context = AppContext()
        context.tts_engine = cast(TTSEngineService, FailedTTS())
        app = main.create_app(context)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-image-key"}):
            with patch("providers.registry.get_image_gen", return_value=FailedImageProvider()):
                client = TestClient(app, raise_server_exceptions=False)
                tts_resp = client.get("/api/tts?text=hi")
                image_resp = client.post("/api/image?prompt=portrait")

        self.assertEqual(tts_resp.status_code, 502)
        self.assertEqual(image_resp.status_code, 502)
        self.assertIn("provider rejected request", tts_resp.json()["detail"])
        self.assertIn("provider rejected request", image_resp.json()["detail"])

    def test_image_endpoint_returns_service_unavailable_when_unconfigured(self):
        from fastapi.testclient import TestClient
        import main
        from server.context import AppContext
        from server.media_api_service import MediaApiService

        context = AppContext()
        context.media_api_service = MediaApiService(
            tts_engine=None,
            image_cache_dir=ROOT / ".cache" / "image",
            image_available=False,
            image_unavailable_reason="GEMINI_API_KEY",
        )
        app = main.create_app(context)

        client = TestClient(app, raise_server_exceptions=False)
        image_resp = client.post("/api/image?prompt=portrait")

        self.assertEqual(image_resp.status_code, 503)
        self.assertTrue(image_resp.headers["content-type"].startswith("application/json"))
        self.assertIn("GEMINI_API_KEY", image_resp.json()["detail"])


class DeepSeekProviderRegressionTests(unittest.TestCase):
    def test_deepseek_is_available_as_openai_compatible_provider(self):
        registry_source = (ROOT / "providers/registry.py").read_text(encoding="utf-8")
        api_yaml = (ROOT / "providers/api.yaml").read_text(encoding="utf-8")
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("DeepSeekLLMProvider", registry_source)
        self.assertIn('"deepseek": DeepSeekLLMProvider', registry_source)
        self.assertIn("DEEPSEEK_API_KEY", api_yaml)
        self.assertIn('base_url: "https://api.deepseek.com"', api_yaml)
        self.assertIn("deepseek-v4-pro", api_yaml)
        self.assertIn("DEEPSEEK_API_KEY", env_example)

    def test_deepseek_provider_uses_expected_defaults(self):
        deepseek = importlib.import_module("providers.llm.deepseek")

        self.assertEqual(deepseek.DeepSeekLLMProvider.PROVIDER_NAME, "deepseek")
        self.assertEqual(deepseek.DeepSeekLLMProvider.DEFAULT_BASE_URL, "https://api.deepseek.com")
        self.assertEqual(deepseek.DeepSeekLLMProvider.DEFAULT_API_KEY_ENV, "DEEPSEEK_API_KEY")
        self.assertEqual(deepseek.DeepSeekLLMProvider.DEFAULT_MODEL, "deepseek-v4-pro")

    def test_provider_base_url_can_be_configured_from_generic_env(self):
        from providers import api_config
        from providers import config as provider_config
        from providers.registry import get_llm

        with patch.dict(
            os.environ,
            {
                "DEFAULT_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-openai-key",
                "OPENAI_BASE_URL": "https://openai.example.test/v1",
            },
        ):
            api_config.reload()
            provider_config.reload()

            api_cfg = api_config.get_llm_config()
            provider = get_llm(provider="openai")

        try:
            api_config.reload()
            provider_config.reload()
        finally:
            self.assertEqual(api_cfg["provider"], "openai")
            self.assertEqual(api_cfg["api_key"], "test-openai-key")
            self.assertEqual(api_cfg["base_url"], "https://openai.example.test/v1")
            self.assertEqual(provider.base_url, "https://openai.example.test/v1")

    def test_llm_base_url_can_override_any_active_provider(self):
        from providers import api_config
        from providers import config as provider_config
        from providers.registry import get_llm

        with patch.dict(
            os.environ,
            {
                "DEFAULT_PROVIDER": "deepseek",
                "DEEPSEEK_API_KEY": "test-deepseek-key",
                "LLM_BASE_URL": "https://llm-gateway.example.test",
            },
        ):
            api_config.reload()
            provider_config.reload()

            api_cfg = api_config.get_llm_config()
            provider = get_llm(provider="deepseek")

        try:
            api_config.reload()
            provider_config.reload()
        finally:
            self.assertEqual(api_cfg["base_url"], "https://llm-gateway.example.test")
            self.assertEqual(provider.base_url, "https://llm-gateway.example.test")

    def test_llm_api_key_can_override_any_active_provider(self):
        from providers import api_config
        from providers import config as provider_config
        from providers.registry import get_llm

        with patch.dict(
            os.environ,
            {
                "DEFAULT_PROVIDER": "deepseek",
                "LLM_API_KEY": "test-global-llm-key",
            },
            clear=True,
        ):
            api_config.reload()
            provider_config.reload()

            api_cfg = api_config.get_llm_config()
            provider = get_llm(provider="deepseek")

        try:
            api_config.reload()
            provider_config.reload()
        finally:
            self.assertEqual(api_cfg["api_key"], "test-global-llm-key")
            self.assertEqual(provider.provider_name, "deepseek")


class EverMemOSLoggingRegressionTests(unittest.TestCase):
    def test_evermemos_api_key_enables_cloud_default_url(self):
        from providers import api_config

        with patch.dict(os.environ, {"EVERMEMOS_API_KEY": "cloud-key"}, clear=True):
            api_config.reload()
            mem_cfg = api_config.get_memory_config()

        try:
            api_config.reload()
        finally:
            self.assertTrue(mem_cfg["enabled"])
            self.assertEqual(mem_cfg["base_url"], "https://api.evermind.ai/api/v1")
            self.assertEqual(mem_cfg["api_key"], "cloud-key")

    def test_evermemos_env_precedence_prefers_provider_specific_values(self):
        from providers import api_config

        with patch.dict(
            os.environ,
            {
                "EVERMEMOS_API_KEY": "evermemos-key",
                "MEMORY_API_KEY": "generic-memory-key",
                "EVERMEMOS_BASE_URL": "https://evermemos.example.test/api/v1",
                "MEMORY_BASE_URL": "https://memory.example.test/api/v1",
            },
            clear=True,
        ):
            api_config.reload()
            mem_cfg = api_config.get_memory_config()

        try:
            api_config.reload()
        finally:
            self.assertTrue(mem_cfg["enabled"])
            self.assertEqual(mem_cfg["base_url"], "https://evermemos.example.test/api/v1")
            self.assertEqual(mem_cfg["api_key"], "evermemos-key")

    def test_evermemos_client_uses_generic_memory_env_fallbacks(self):
        ever = importlib.import_module("providers.memory.evermemos.evermemos_client")

        class FakeAsyncClient:
            def __init__(self, *, base_url, headers, timeout, trust_env):
                self.base_url = base_url
                self.headers = headers
                self.timeout = timeout
                self.trust_env = trust_env

        with patch.dict(
            os.environ,
            {
                "MEMORY_API_KEY": "generic-memory-key",
                "MEMORY_BASE_URL": "https://memory.example.test",
            },
            clear=True,
        ):
            with patch.object(ever, "httpx", SimpleNamespace(AsyncClient=FakeAsyncClient)):
                client = ever.EverMemOSClient()

        self.assertTrue(client.available)
        self.assertEqual(client._base_url, "https://memory.example.test/api/v1")
        self.assertEqual(client._api_key, "generic-memory-key")
        self.assertEqual(client._client.headers["Authorization"], "Bearer generic-memory-key")

    def test_store_turn_reports_success_as_boolean(self):
        ever = importlib.import_module("providers.memory.evermemos.evermemos_client")

        class Breaker:
            is_open = False
            def __init__(self):
                self.failures = 0
                self.successes = 0
            def record_failure(self):
                self.failures += 1
            def record_success(self):
                self.successes += 1

        class Response:
            status_code = 202
            text = "accepted"

        class WorkingClient:
            async def post(self, *_args, **_kwargs):
                return Response()

        class FailingClient:
            async def post(self, *_args, **_kwargs):
                raise RuntimeError("evermemos down")

        async def exercise(client):
            instance = ever.EverMemOSClient.__new__(ever.EverMemOSClient)
            instance._initialized = True
            instance._client = client
            instance._cb = Breaker()
            return await instance.store_turn(
                user_id="u",
                persona_id="luna",
                persona_name="Luna",
                user_name="QA",
                group_id="g",
                user_message="hi",
                agent_reply="hello",
            )

        self.assertTrue(asyncio.run(exercise(WorkingClient())))
        self.assertFalse(asyncio.run(exercise(FailingClient())))

    def test_store_turn_sends_cloud_required_messages_body(self):
        ever = importlib.import_module("providers.memory.evermemos.evermemos_client")

        class Breaker:
            is_open = False
            def record_failure(self):
                pass
            def record_success(self):
                pass

        class Response:
            status_code = 202
            text = "accepted"

        class CapturingClient:
            def __init__(self):
                self.payloads = []

            async def post(self, _path, **kwargs):
                self.payloads.append(kwargs["json"])
                return Response()

        async def exercise(client):
            instance = ever.EverMemOSClient.__new__(ever.EverMemOSClient)
            instance._initialized = True
            instance._client = client
            instance._cb = Breaker()
            await instance.store_turn(
                user_id="u",
                persona_id="luna",
                persona_name="Luna",
                user_name="QA",
                group_id="g",
                user_message="hi",
                agent_reply="hello",
            )

        client = CapturingClient()
        asyncio.run(exercise(client))

        self.assertEqual(len(client.payloads), 1)
        self.assertEqual(client.payloads[0]["user_id"], "u")
        self.assertEqual(client.payloads[0]["session_id"], "g")
        self.assertEqual(client.payloads[0]["app_id"], "openher")
        self.assertEqual(client.payloads[0]["project_id"], "openher")
        self.assertEqual([message["role"] for message in client.payloads[0]["messages"]], ["user", "assistant"])
        self.assertEqual([message["content"] for message in client.payloads[0]["messages"]], ["hi", "hello"])
        self.assertEqual([message["sender_id"] for message in client.payloads[0]["messages"]], ["u", "luna"])
        self.assertTrue(all(isinstance(message["timestamp"], int) for message in client.payloads[0]["messages"]))

    def test_search_uses_official_cloud_filters_payload(self):
        ever = importlib.import_module("providers.memory.evermemos.evermemos_client")

        class Breaker:
            is_open = False
            def record_failure(self):
                pass
            def record_success(self):
                pass

        class Response:
            status_code = 200
            text = "ok"
            def json(self):
                return {"data": {"episodes": [], "profiles": []}}

        class CapturingClient:
            def __init__(self):
                self.requests = []

            async def request(self, method, path, **kwargs):
                self.requests.append((method, path, kwargs["json"]))
                return Response()

        async def exercise(client):
            instance = ever.EverMemOSClient.__new__(ever.EverMemOSClient)
            instance._initialized = True
            instance._client = client
            instance._cb = Breaker()
            await instance.search_relevant_memories(
                query="where did we test memories?",
                user_id="u",
                group_id="g",
            )

        client = CapturingClient()
        asyncio.run(exercise(client))

        self.assertEqual(client.requests[0][1], "/memories/search")
        self.assertEqual(
            client.requests[0][2],
            {
                "filters": {"user_id": "u"},
                "query": "where did we test memories?",
                "method": "keyword",
                "top_k": 5,
            },
        )

    def test_verify_connection_uses_official_search_payload(self):
        ever = importlib.import_module("providers.memory.evermemos.evermemos_client")

        class Response:
            status_code = 200
            text = "ok"

        class CapturingClient:
            def __init__(self):
                self.requests = []

            async def request(self, method, path, **kwargs):
                self.requests.append((method, path, kwargs["json"]))
                return Response()

        async def exercise(client):
            instance = ever.EverMemOSClient.__new__(ever.EverMemOSClient)
            instance._initialized = True
            instance._client = client
            return await instance.verify_connection()

        client = CapturingClient()
        self.assertTrue(asyncio.run(exercise(client)))

        self.assertEqual(client.requests[0][0], "POST")
        self.assertEqual(client.requests[0][1], "/memories/search")
        self.assertEqual(
            client.requests[0][2],
            {
                "filters": {"user_id": "__healthcheck__"},
                "query": "__healthcheck__",
                "method": "keyword",
                "top_k": 1,
            },
        )

    def test_success_log_is_only_printed_after_true_store_result(self):
        mixin_source = (ROOT / "agent/evermemos_mixin.py").read_text(encoding="utf-8")

        self.assertIn("stored = await self.evermemos.store_turn", mixin_source)
        self.assertIn("if stored:", mixin_source)
        self.assertIn("else:", mixin_source)


class SwiftClientAuthRegressionTests(unittest.TestCase):
    def test_desktop_client_sends_optional_api_token(self):
        app_state = (ROOT / "desktop/OpenHer/Sources/AppState.swift").read_text(encoding="utf-8")
        api_client = (ROOT / "desktop/OpenHer/Sources/Services/APIClient.swift").read_text(encoding="utf-8")
        websocket = (ROOT / "desktop/OpenHer/Sources/Services/WebSocketManager.swift").read_text(encoding="utf-8")
        settings = (ROOT / "desktop/OpenHer/Sources/Views/Settings/SettingsView.swift").read_text(encoding="utf-8")
        persona_card = (ROOT / "desktop/OpenHer/Sources/Views/Discovery/PersonaCard.swift").read_text(encoding="utf-8")
        awakening = (ROOT / "desktop/OpenHer/Sources/Views/Discovery/AwakeningView.swift").read_text(encoding="utf-8")
        message_row = (ROOT / "desktop/OpenHer/Sources/Views/Conversation/MessageRow.swift").read_text(encoding="utf-8")

        self.assertIn("apiToken", app_state)
        self.assertIn("authenticatedMediaURL", app_state)
        self.assertIn("Authorization", api_client)
        self.assertIn("apiToken", api_client)
        self.assertIn("URLRequest", websocket)
        self.assertIn("Authorization", websocket)
        self.assertIn("SecureField", settings)
        self.assertIn("authenticatedMediaURL", persona_card)
        self.assertIn("authenticatedMediaURL", awakening)
        self.assertIn("authenticatedMediaURL", message_row)


class SwiftWarningRegressionTests(unittest.TestCase):
    def test_api_client_has_no_dead_chat_history_decoder(self):
        api_client = (ROOT / "desktop/OpenHer/Sources/Services/APIClient.swift").read_text(encoding="utf-8")

        self.assertNotIn("func fetchChatHistory(personaId:", api_client)
        self.assertNotIn("Will be handled differently below", api_client)

    def test_connection_monitoring_replaces_existing_timer(self):
        connection_manager = (
            ROOT / "desktop/OpenHer/Sources/Services/ConnectionManager.swift"
        ).read_text(encoding="utf-8")

        start_body = connection_manager.split("func startMonitoring()", 1)[1].split("func stopMonitoring()", 1)[0]
        self.assertIn("stopMonitoring()", start_body)


class SetupScriptRegressionTests(unittest.TestCase):
    def test_setup_script_rejects_unsupported_new_python(self):
        setup_source = (ROOT / "setup.sh").read_text(encoding="utf-8")

        self.assertIn("PY_MIN_MINOR=11", setup_source)
        self.assertIn("PY_MAX_MINOR=13", setup_source)
        self.assertIn('"$PY_MINOR" -gt "$PY_MAX_MINOR"', setup_source)


class RunScriptRegressionTests(unittest.TestCase):
    def test_run_script_validates_venv_python_by_executing_it(self):
        run_source = (ROOT / "run.sh").read_text(encoding="utf-8")

        self.assertNotIn("head -1 \"$VENV_PYTHON\"", run_source)
        self.assertIn("$VENV_PYTHON\" -c", run_source)
        self.assertIn("sys.version_info", run_source)

    def test_background_start_waits_for_server_port(self):
        run_source = (ROOT / "run.sh").read_text(encoding="utf-8")

        self.assertIn("STARTUP_TIMEOUT", run_source)
        self.assertIn("for _ in $(seq 1 \"$STARTUP_TIMEOUT\")", run_source)
        self.assertNotIn("sleep 2\n    if lsof", run_source)


class IntegrationTestPortRegressionTests(unittest.TestCase):
    def test_websocket_e2e_tests_follow_run_script_default_port(self):
        websocket_source = (ROOT / "tests/test_websocket.py").read_text(encoding="utf-8")
        single_pass_source = (ROOT / "tests/test_single_pass_e2e.py").read_text(encoding="utf-8")

        self.assertNotIn("localhost:8800", websocket_source)
        self.assertNotIn("localhost:8800", single_pass_source)
        self.assertIn("OPENHER_TEST_WS_URI", websocket_source)
        self.assertIn("OPENHER_TEST_WS_URI", single_pass_source)
        self.assertIn("os.getenv(\"PORT\", \"8000\")", websocket_source)
        self.assertIn("os.getenv(\"PORT\", \"8000\")", single_pass_source)


if __name__ == "__main__":
    unittest.main()
