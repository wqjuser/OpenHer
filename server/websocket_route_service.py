"""Accepted WebSocket connection-loop orchestration."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Optional

from starlette.websockets import WebSocketDisconnect


SleepFunc = Callable[[float], Awaitable[Any]]
TaskFactory = Callable[[Coroutine[Any, Any, Any]], asyncio.Task[Any]]


class WebSocketRouteService:
    """Routes accepted WebSocket messages to focused WebSocket services."""

    def __init__(
        self,
        *,
        registry: Any,
        session_manager: Any = None,
        chat_turn_service: Any = None,
        tts_service: Any = None,
        persona_switch_service: Any = None,
        demo_command_service: Any = None,
        debounce_grace_sec: float = 2.0,
        debounce_fallback_sec: float = 3.0,
        sleep: SleepFunc = asyncio.sleep,
        create_task: TaskFactory = asyncio.create_task,
    ) -> None:
        self.registry = registry
        self.session_manager = session_manager
        self.chat_turn_service = chat_turn_service
        self.tts_service = tts_service
        self.persona_switch_service = persona_switch_service
        self.demo_command_service = demo_command_service
        self.debounce_grace_sec = debounce_grace_sec
        self.debounce_fallback_sec = debounce_fallback_sec
        self.sleep = sleep
        self.create_task = create_task

    async def handle_connection(
        self,
        websocket: Any,
        *,
        initial_session_id: Optional[str] = None,
        initial_agent: Any = None,
    ) -> None:
        session_id = initial_session_id
        agent = initial_agent
        msg_buffer: list[dict[str, Any]] = []
        typing_active = False
        debounce_task: asyncio.Task[Any] | None = None
        connection_closed = False

        async def flush_buffer() -> None:
            nonlocal msg_buffer, debounce_task, agent, session_id
            if connection_closed:
                msg_buffer = []
                debounce_task = None
                return
            if not msg_buffer:
                return

            msgs = msg_buffer
            msg_buffer = []
            debounce_task = None

            if self.chat_turn_service:
                result = await self.chat_turn_service.handle_messages(
                    websocket=websocket,
                    messages=msgs,
                    agent=agent,
                    session_id=session_id,
                )
                session_id = result.session_id
                agent = result.agent

        async def schedule_flush(delay: float) -> None:
            nonlocal debounce_task
            if debounce_task and not debounce_task.done():
                debounce_task.cancel()

            async def wait_and_flush() -> None:
                try:
                    await self.sleep(delay)
                    if connection_closed:
                        return
                    await flush_buffer()
                except asyncio.CancelledError:
                    raise
                except RuntimeError as e:
                    print(f"[ws] flush skipped after connection close: {e}")
                except Exception as e:
                    print(f"[ws] flush task error: {type(e).__name__}: {e}")

            debounce_task = self.create_task(wait_and_flush())

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "content": "Invalid JSON"})
                    continue

                msg_type = msg.get("type", "")
                client_id = msg.get("client_id")
                if client_id:
                    self.registry.register_client(client_id, websocket)

                if msg_type == "typing":
                    typing_active = msg.get("active", False)
                    print(
                        f"  [debounce] typing={'active' if typing_active else 'inactive'}, "
                        f"buffer={len(msg_buffer)}"
                    )
                    if not typing_active and msg_buffer:
                        await schedule_flush(self.debounce_grace_sec)
                        print(f"  [debounce] ⏱ scheduled flush in {self.debounce_grace_sec}s")
                    continue

                if msg_type == "chat":
                    text = msg.get("content", "").strip()
                    if not text:
                        continue
                    msg_buffer.append(msg)
                    print(
                        f"  [debounce] 📥 buffered msg #{len(msg_buffer)}: "
                        f"'{text[:30]}', typing_active={typing_active}"
                    )
                    await schedule_flush(self.debounce_fallback_sec)

                elif msg_type == "tts_request":
                    if self.tts_service:
                        await self.tts_service.handle_request(
                            websocket,
                            agent,
                            msg.get("content", ""),
                        )

                elif msg_type == "status":
                    if agent:
                        await websocket.send_json({
                            "type": "status",
                            **agent.get_status(),
                        })

                elif msg_type == "switch_persona":
                    if self.persona_switch_service:
                        switch_result = await self.persona_switch_service.switch(
                            websocket=websocket,
                            current_session_id=session_id,
                            persona_id=msg.get("persona_id", ""),
                            user_name=msg.get("user_name"),
                            client_id=msg.get("client_id"),
                        )
                        if switch_result:
                            session_id, agent = switch_result

                elif msg_type.startswith("demo_"):
                    if self.demo_command_service:
                        demo_result = await self.demo_command_service.handle(
                            websocket=websocket,
                            message=msg,
                            agent=agent,
                            session_id=session_id,
                        )
                        if demo_result.handled:
                            session_id = demo_result.session_id
                            agent = demo_result.agent

        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"[ws] 未预期异常: {type(e).__name__}: {e}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "content": f"服务端异常: {str(e)[:200]}",
                })
            except Exception:
                pass
        finally:
            connection_closed = True
            if debounce_task and not debounce_task.done():
                debounce_task.cancel()
                try:
                    await debounce_task
                except asyncio.CancelledError:
                    pass
            msg_buffer.clear()
            self.registry.unregister_websocket(websocket)
            if session_id and self.session_manager:
                self.session_manager.remove(session_id)
            print(f"[ws] 连接关闭: session={session_id}")
