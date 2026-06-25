"""WebSocket chat turn processing."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from agent.output_router import stream_to_ws as default_stream_to_ws
from server.media import audio_format_for_path
from server.websocket_delivery import WebSocketCompletedTurnDeliveryService
from server.websocket_registry import WebSocketConnectionRegistry


GetOrCreateSession = Callable[[Optional[str], str, Optional[str], Optional[str]], tuple[str, Any]]
SleepFunc = Callable[[float], Awaitable[Any]]
StreamToWsFunc = Callable[..., Awaitable[None]]


@dataclass
class WebSocketChatTurnResult:
    """Updated session state after processing a WebSocket chat turn."""

    session_id: Optional[str]
    agent: Any


class WebSocketChatTurnService:
    """Processes one debounced chat turn and delivers frontend events."""

    def __init__(
        self,
        *,
        registry: WebSocketConnectionRegistry,
        get_or_create_session: GetOrCreateSession,
        chat_log_store: Any = None,
        stream_to_ws: StreamToWsFunc = default_stream_to_ws,
        sleep: SleepFunc = asyncio.sleep,
        audio_format_resolver: Callable[[str], str] = audio_format_for_path,
        delivery_service: Optional[WebSocketCompletedTurnDeliveryService] = None,
    ) -> None:
        self.registry = registry
        self.get_or_create_session = get_or_create_session
        self.chat_log_store = chat_log_store
        self.stream_to_ws = stream_to_ws
        self.sleep = sleep
        self.delivery_service = delivery_service or WebSocketCompletedTurnDeliveryService(
            chat_log_store=chat_log_store,
            sleep=sleep,
            audio_format_resolver=audio_format_resolver,
        )

    async def handle_messages(
        self,
        *,
        websocket: Any,
        messages: list[dict[str, Any]],
        agent: Any,
        session_id: Optional[str],
    ) -> WebSocketChatTurnResult:
        """Merge buffered chat messages and process them as a single turn."""
        if not messages:
            return WebSocketChatTurnResult(session_id=session_id, agent=agent)

        first = messages[0]
        merged_text = "\n".join(m.get("content", "").strip() for m in messages)
        persona_id = first.get("persona_id", "")
        user_name = first.get("user_name")
        client_id = first.get("client_id")
        debug_mode = first.get("debug", False)

        if not persona_id or not merged_text.strip():
            return WebSocketChatTurnResult(session_id=session_id, agent=agent)

        current_agent = agent
        current_session_id = session_id
        if (
            current_agent
            and hasattr(current_agent, "persona")
            and current_agent.persona.persona_id != persona_id
        ):
            print(
                f"  [session] persona changed {current_agent.persona.persona_id} → {persona_id}, resetting session"
            )
            current_session_id = None
            current_agent = None

        try:
            current_session_id, current_agent = self.get_or_create_session(
                current_session_id or first.get("session_id"),
                persona_id,
                user_name,
                client_id,
            )
        except ValueError as e:
            await websocket.send_json({"type": "error", "content": str(e)})
            return WebSocketChatTurnResult(session_id=current_session_id, agent=current_agent)

        if len(messages) > 1:
            print(f"  [debounce] 📦 merged {len(messages)} messages into one turn")

        self._save_display_greeting(first, current_agent, persona_id, client_id)
        self.registry.register_session(current_session_id, websocket)
        if client_id:
            self.registry.register_client(client_id, websocket)

        clean_reply_text = ""

        try:
            async def ws_send(msg: dict[str, Any]) -> None:
                for peer in self.registry.connections_for_session(current_session_id):
                    try:
                        await peer.send_json(msg)
                    except Exception:
                        self.registry.unregister_session(current_session_id, peer)

            async def on_feel_done() -> None:
                await ws_send({
                    "type": "chat_start",
                    "session_id": current_session_id,
                    "user_content": merged_text,
                })

            async def on_complete(reply: str, _modality: str) -> None:
                nonlocal clean_reply_text
                clean_reply_text = reply

            await self.stream_to_ws(
                current_agent.chat_stream(merged_text),
                ws_send,
                on_feel_done=on_feel_done,
                on_reply_complete=on_complete,
            )
        except Exception as e:
            print(f"[ws] stream 错误: {e}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "content": f"LLM 响应异常: {type(e).__name__}: {str(e)[:200]}",
                })
            except Exception:
                pass
            return WebSocketChatTurnResult(session_id=current_session_id, agent=current_agent)

        await self.delivery_service.deliver_completed_turn(
            websocket=websocket,
            agent=current_agent,
            session_id=current_session_id,
            persona_id=persona_id,
            client_id=client_id,
            merged_text=merged_text,
            clean_reply_text=clean_reply_text,
            debug_mode=debug_mode,
        )
        return WebSocketChatTurnResult(session_id=current_session_id, agent=current_agent)

    def _save_display_greeting(
        self,
        first_message: dict[str, Any],
        agent: Any,
        persona_id: str,
        client_id: Optional[str],
    ) -> None:
        greeting = first_message.get("greeting")
        if not greeting or not agent or len(getattr(agent, "history", [])) != 0:
            return

        print(f"  [greeting] display-only (not in model state): {greeting[:40]}")
        if not self.chat_log_store or not client_id:
            return
        try:
            self.chat_log_store.save_message(
                client_id=client_id,
                persona_id=persona_id,
                role="assistant",
                content=greeting,
                modality="文字",
            )
        except Exception as e:
            print(f"  [greeting] chat_log save error: {e}")
