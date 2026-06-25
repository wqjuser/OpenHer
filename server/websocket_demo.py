"""WebSocket helpers for demo-only workflows."""

from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, Protocol

import yaml
from starlette.websockets import WebSocketDisconnect

from agent.demo_controller import DemoController
from server.proactive_ws_push import ProactivePushPayload, ProactiveWebSocketPushService


SleepFunc = Callable[[float], Awaitable[Any]]
DemoControllerFactory = Callable[[Any], Any]
GetOrCreateSession = Callable[[Optional[str], str, Optional[str], Optional[str]], tuple[str, Any]]


class ProactiveDelivery(Protocol):
    async def deliver_forced_proactive(
        self,
        *,
        websocket: Any,
        agent: Any,
        session_id: Optional[str],
        proactive_result: dict[str, Any],
    ) -> Optional[str]:
        ...


@dataclass(frozen=True)
class WebSocketDemoCommandResult:
    """Result of handling a demo WebSocket command."""

    handled: bool
    session_id: Optional[str]
    agent: Any


class WebSocketDemoProactiveService:
    """Routes forced demo proactive messages through the full chat engine."""

    def __init__(
        self,
        sleep: SleepFunc = asyncio.sleep,
        push_service: Optional[ProactiveWebSocketPushService] = None,
    ) -> None:
        self.push_service = push_service or ProactiveWebSocketPushService(sleep=sleep)

    async def deliver_forced_proactive(
        self,
        *,
        websocket: Any,
        agent: Any,
        session_id: Optional[str],
        proactive_result: dict[str, Any],
    ) -> Optional[str]:
        """Re-express a demo proactive impulse and send it to the WebSocket."""
        if not proactive_result.get("proactive_fired"):
            return None

        raw_reply = proactive_result.get("proactive_reply", "")
        stimulus = (
            "[系统指令] 你现在想主动对用户说话。以下是你想表达的内容，请用你认为的方式表达出来：\n"
            f"{raw_reply}"
        )
        engine_result = await agent.chat(stimulus, is_proactive=True)
        reply = engine_result.get("reply", raw_reply)
        modality = engine_result.get("modality", "文字")
        segments = engine_result.get("segments")
        delays_ms = engine_result.get("delays_ms")

        await self.push_service.push(
            websocket,
            session_id=session_id,
            payload=ProactivePushPayload(
                reply=reply,
                modality=modality,
                segments=segments,
                delays_ms=delays_ms,
            ),
        )

        return reply


class WebSocketDemoCommandService:
    """Handles demo-only WebSocket commands outside the main chat loop."""

    def __init__(
        self,
        *,
        get_or_create_session: GetOrCreateSession,
        presets_file: str,
        demo_controller_factory: DemoControllerFactory = DemoController,
        proactive_delivery: Optional[ProactiveDelivery] = None,
        proactive_timeout_seconds: float = 30,
    ) -> None:
        self.get_or_create_session = get_or_create_session
        self.presets_file = presets_file
        self.demo_controller_factory = demo_controller_factory
        self.proactive_delivery = proactive_delivery
        self.proactive_timeout_seconds = proactive_timeout_seconds

    async def handle(
        self,
        *,
        websocket: Any,
        message: dict[str, Any],
        agent: Any,
        session_id: Optional[str],
    ) -> WebSocketDemoCommandResult:
        """Handle a demo command, returning updated session state."""
        msg_type = message.get("type", "")

        if msg_type == "demo_time_jump":
            return await self._handle_time_jump(websocket, message, agent, session_id)
        if msg_type == "demo_inject":
            return await self._handle_inject(websocket, message, agent, session_id)
        if msg_type == "demo_scenario":
            return await self._handle_scenario(websocket, message, agent, session_id)
        if msg_type == "demo_presets":
            return await self._handle_presets(websocket, agent, session_id)
        if msg_type == "demo_force_proactive":
            return await self._handle_force_proactive(websocket, agent, session_id)
        if msg_type == "demo_inject_memory":
            return await self._handle_inject_memory(websocket, message, agent, session_id)

        return WebSocketDemoCommandResult(
            handled=False,
            session_id=session_id,
            agent=agent,
        )

    async def _handle_time_jump(
        self,
        websocket: Any,
        message: dict[str, Any],
        agent: Any,
        session_id: Optional[str],
    ) -> WebSocketDemoCommandResult:
        if not agent:
            return self._handled(session_id, agent)

        hours = float(message.get("hours", 1))
        demo = self.demo_controller_factory(agent)
        result = demo.time_jump(hours)
        print(
            "  [demo] ⏩ time_jump "
            f"+{hours}h → temp={result.get('temperature', 0):.3f}, "
            f"frust={result.get('total_frustration', 0):.2f}",
            flush=True,
        )
        await websocket.send_json({"type": "demo_state", **result})

        try:
            pro_result = await asyncio.wait_for(
                demo.force_proactive(simulated_hours=hours),
                timeout=self.proactive_timeout_seconds,
            )
            reply = await self._deliver_forced_proactive(
                websocket=websocket,
                agent=agent,
                session_id=session_id,
                proactive_result=pro_result,
            )
            if reply is not None:
                print(f"  [demo] 💭 自驱消息(engine): {reply[:40]}", flush=True)
            else:
                print(f"  [demo] 💭 no impulse after +{hours}h", flush=True)
            await websocket.send_json({"type": "demo_state", **pro_result})
        except asyncio.TimeoutError:
            print(
                f"  [demo] ⏰ proactive tick timeout ({self.proactive_timeout_seconds:g}s)",
                flush=True,
            )
        except WebSocketDisconnect:
            raise
        except Exception as exc:
            print(f"  [demo] ❌ proactive after jump failed: {exc}", flush=True)
            traceback.print_exc()

        return self._handled(session_id, agent)

    async def _handle_inject(
        self,
        websocket: Any,
        message: dict[str, Any],
        agent: Any,
        session_id: Optional[str],
    ) -> WebSocketDemoCommandResult:
        if not agent:
            return self._handled(session_id, agent)

        overrides = message.get("overrides", {})
        if not isinstance(overrides, dict):
            overrides = {}
        demo = self.demo_controller_factory(agent)
        result = demo.inject_state(overrides)
        print(
            "  [demo] 🎚️ inject → "
            f"temp={result.get('temperature', 0):.3f}, "
            f"frust={result.get('total_frustration', 0):.2f}",
            flush=True,
        )
        await websocket.send_json({"type": "demo_state", **result})
        return self._handled(session_id, agent)

    async def _handle_scenario(
        self,
        websocket: Any,
        message: dict[str, Any],
        agent: Any,
        session_id: Optional[str],
    ) -> WebSocketDemoCommandResult:
        if not agent:
            return self._handled(session_id, agent)

        scenario_id = str(message.get("scenario_id", ""))
        demo = self.demo_controller_factory(agent)
        demo.load_presets_file(self.presets_file)
        result = demo.apply_scenario(scenario_id)
        print(
            f"  [demo] 🎚️ scenario '{scenario_id}' → "
            f"temp={result.get('temperature', 0):.3f}",
            flush=True,
        )
        await websocket.send_json({"type": "demo_state", **result})

        try:
            pro_result = await asyncio.wait_for(
                demo.force_proactive(),
                timeout=self.proactive_timeout_seconds,
            )
            reply = await self._deliver_forced_proactive(
                websocket=websocket,
                agent=agent,
                session_id=session_id,
                proactive_result=pro_result,
            )
            if reply is not None:
                print(f"  [demo] 💭 自驱消息(engine): {reply[:40]}", flush=True)
            else:
                print(f"  [demo] 💭 no impulse after scenario '{scenario_id}'", flush=True)
            await websocket.send_json({"type": "demo_state", **pro_result})
        except asyncio.TimeoutError:
            print(
                f"  [demo] ⏰ proactive tick timeout ({self.proactive_timeout_seconds:g}s)",
                flush=True,
            )
        except WebSocketDisconnect:
            raise
        except Exception as exc:
            print(f"  [demo] ❌ proactive after scenario failed: {exc}", flush=True)
            traceback.print_exc()

        return self._handled(session_id, agent)

    async def _handle_presets(
        self,
        websocket: Any,
        agent: Any,
        session_id: Optional[str],
    ) -> WebSocketDemoCommandResult:
        try:
            data = yaml.safe_load(Path(self.presets_file).read_text(encoding="utf-8")) or {}
            await websocket.send_json({
                "type": "demo_presets",
                "presets": data.get("presets", []),
                "scenarios": data.get("scenarios", {}),
            })
        except WebSocketDisconnect:
            raise
        except Exception as exc:
            await websocket.send_json({
                "type": "error",
                "content": f"Failed to load presets: {exc}",
            })
        return self._handled(session_id, agent)

    async def _handle_force_proactive(
        self,
        websocket: Any,
        agent: Any,
        session_id: Optional[str],
    ) -> WebSocketDemoCommandResult:
        if not agent:
            return self._handled(session_id, agent)

        demo = self.demo_controller_factory(agent)
        result = await demo.force_proactive()
        fired = result.get("proactive_fired", False)
        if fired:
            reply = result.get("proactive_reply", "")
            modality = result.get("proactive_modality", "文字")
            await websocket.send_json({
                "type": "proactive",
                "content": reply,
                "modality": modality,
            })
            print(f"  [demo] 💭 proactive fired: {reply[:40]}")
        else:
            print("  [demo] 💭 proactive: no impulse / silence")
        await websocket.send_json({"type": "demo_state", **result})
        return self._handled(session_id, agent)

    async def _handle_inject_memory(
        self,
        websocket: Any,
        message: dict[str, Any],
        agent: Any,
        session_id: Optional[str],
    ) -> WebSocketDemoCommandResult:
        current_session_id = session_id
        current_agent = agent
        persona_id = str(message.get("persona_id", "") or "")
        client_id = str(message.get("client_id", "") or "")

        persona = getattr(current_agent, "persona", None)
        active_persona_id = getattr(persona, "persona_id", None)
        if current_agent and persona_id and active_persona_id and active_persona_id != persona_id:
            print(
                "  [demo] memory inject: persona mismatch "
                f"{active_persona_id} → {persona_id}, resetting"
            )
            current_session_id = None
            current_agent = None

        if not current_agent and persona_id:
            try:
                current_session_id, current_agent = self.get_or_create_session(
                    None,
                    persona_id,
                    None,
                    client_id,
                )
                print(f"  [demo] auto-created session for memory inject: {persona_id}")
            except Exception as exc:
                print(f"  [demo] failed to auto-create session: {exc}")

        if current_agent:
            content = str(message.get("content", "") or "")
            category = str(message.get("category", "preference") or "preference")
            if content:
                demo = self.demo_controller_factory(current_agent)
                result = await demo.inject_memory(content, category)
                await websocket.send_json({"type": "demo_memory", **result})
            else:
                await websocket.send_json({
                    "type": "error",
                    "content": "memory content is empty",
                })
        else:
            print("  [demo] ⚠️ no agent for memory inject — send a chat first")

        return self._handled(current_session_id, current_agent)

    async def _deliver_forced_proactive(
        self,
        *,
        websocket: Any,
        agent: Any,
        session_id: Optional[str],
        proactive_result: dict[str, Any],
    ) -> Optional[str]:
        if self.proactive_delivery:
            return await self.proactive_delivery.deliver_forced_proactive(
                websocket=websocket,
                agent=agent,
                session_id=session_id,
                proactive_result=proactive_result,
            )
        if proactive_result.get("proactive_fired"):
            return proactive_result.get("proactive_reply", "")
        return None

    @staticmethod
    def _handled(session_id: Optional[str], agent: Any) -> WebSocketDemoCommandResult:
        return WebSocketDemoCommandResult(
            handled=True,
            session_id=session_id,
            agent=agent,
        )
