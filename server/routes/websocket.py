"""WebSocket chat route."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.context import context_from_websocket
from server.security import request_has_api_token


router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """WebSocket endpoint for real-time persona chat with Genome v10."""
    ctx = context_from_websocket(ws)
    if not request_has_api_token(
        ws.headers.get("Authorization"),
        ws.query_params.get("token"),
    ):
        await ws.close(code=1008)
        return
    await ws.accept()
    session_id = None
    agent = None

    msg_buffer: list[dict] = []
    typing_active = False
    debounce_task: asyncio.Task | None = None
    connection_closed = False
    debounce_grace_sec = 2.0
    debounce_fallback_sec = 3.0

    async def flush_buffer():
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

        if ctx.ws_chat_turn_service:
            result = await ctx.ws_chat_turn_service.handle_messages(
                websocket=ws,
                messages=msgs,
                agent=agent,
                session_id=session_id,
            )
            session_id = result.session_id
            agent = result.agent

    async def schedule_flush(delay: float):
        nonlocal debounce_task
        if debounce_task and not debounce_task.done():
            debounce_task.cancel()

        async def wait_and_flush():
            try:
                await asyncio.sleep(delay)
                if connection_closed:
                    return
                await flush_buffer()
            except asyncio.CancelledError:
                raise
            except RuntimeError as e:
                print(f"[ws] flush skipped after connection close: {e}")
            except Exception as e:
                print(f"[ws] flush task error: {type(e).__name__}: {e}")

        debounce_task = asyncio.create_task(wait_and_flush())

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "content": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "")
            client_id = msg.get("client_id")
            if client_id:
                ctx.ws_registry.register_client(client_id, ws)

            if msg_type == "typing":
                typing_active = msg.get("active", False)
                print(
                    f"  [debounce] typing={'active' if typing_active else 'inactive'}, "
                    f"buffer={len(msg_buffer)}"
                )
                if not typing_active and msg_buffer:
                    await schedule_flush(debounce_grace_sec)
                    print(f"  [debounce] ⏱ scheduled flush in {debounce_grace_sec}s")
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
                await schedule_flush(debounce_fallback_sec)

            elif msg_type == "tts_request":
                if ctx.ws_tts_service:
                    await ctx.ws_tts_service.handle_request(ws, agent, msg.get("content", ""))

            elif msg_type == "status":
                if agent:
                    await ws.send_json({
                        "type": "status",
                        **agent.get_status(),
                    })

            elif msg_type == "switch_persona":
                if ctx.persona_switch_service:
                    switch_result = await ctx.persona_switch_service.switch(
                        websocket=ws,
                        current_session_id=session_id,
                        persona_id=msg.get("persona_id", ""),
                        user_name=msg.get("user_name"),
                        client_id=msg.get("client_id"),
                    )
                    if switch_result:
                        session_id, agent = switch_result

            elif msg_type.startswith("demo_"):
                if ctx.ws_demo_command_service:
                    demo_result = await ctx.ws_demo_command_service.handle(
                        websocket=ws,
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
            await ws.send_json({"type": "error", "content": f"服务端异常: {str(e)[:200]}"})
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
        ctx.ws_registry.unregister_websocket(ws)
        if session_id and ctx.session_manager:
            ctx.session_manager.remove(session_id)
        print(f"[ws] 连接关闭: session={session_id}")
