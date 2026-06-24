"""WebSocket chat turn processing."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import os
from typing import Any, Awaitable, Callable, Optional

from agent.output_router import stream_to_ws as default_stream_to_ws
from server.media import audio_format_for_path
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
    ) -> None:
        self.registry = registry
        self.get_or_create_session = get_or_create_session
        self.chat_log_store = chat_log_store
        self.stream_to_ws = stream_to_ws
        self.sleep = sleep
        self.audio_format_resolver = audio_format_resolver

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

        await self._deliver_completed_turn(
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

    async def _deliver_completed_turn(
        self,
        *,
        websocket: Any,
        agent: Any,
        session_id: str,
        persona_id: str,
        client_id: Optional[str],
        merged_text: str,
        clean_reply_text: str,
        debug_mode: bool,
    ) -> None:
        status = agent.get_status()
        if debug_mode:
            status["debug"] = agent.get_debug_status()

        image_path = status.pop("image_path", None)
        audio_path = status.pop("audio_path", None)
        image_url = self._image_url(image_path)
        if image_path and image_url:
            print(f"  [delivery] 📷 image_path={image_path}, image_url={image_url}")

        segments = status.pop("segments", None)
        delays_ms = status.pop("delays_ms", None)
        modality = status.get("modality", "文字")

        if modality == "静默":
            await websocket.send_json({
                "type": "silence",
                "session_id": session_id,
                **{k: v for k, v in status.items()},
            })
            print("  [silence] 🤫 角色选择静默，客户端不显示消息")
        elif segments and isinstance(segments, list) and len(segments) > 1:
            await self._deliver_segments(
                websocket=websocket,
                session_id=session_id,
                segments=segments,
                delays_ms=delays_ms,
                modality=modality,
                image_url=image_url,
                status=status,
            )
        else:
            await websocket.send_json({
                "type": "chat_end",
                "reply": clean_reply_text,
                "modality": modality,
                "image_url": image_url,
                **{k: v for k, v in status.items()},
            })

        await self._deliver_audio(websocket, audio_path)
        self._clear_pending_retry(agent)
        await self._deliver_pending_retry(websocket, agent)
        self._log_and_persist_turn(
            persona_id=persona_id,
            client_id=client_id,
            merged_text=merged_text,
            clean_reply_text=clean_reply_text,
            modality=modality,
            image_url=image_url,
            segments=segments,
        )

    async def _deliver_segments(
        self,
        *,
        websocket: Any,
        session_id: str,
        segments: list[Any],
        delays_ms: Any,
        modality: str,
        image_url: Optional[str],
        status: dict[str, Any],
    ) -> None:
        for index, segment in enumerate(segments):
            delay = delays_ms[index] if delays_ms and index < len(delays_ms) else 0
            if index > 0:
                await websocket.send_json({
                    "type": "chat_start",
                    "session_id": session_id,
                })
                await self.sleep(max(delay, 300) / 1000.0)
            await websocket.send_json({
                "type": "chat_end",
                "reply": segment,
                "modality": modality,
                "image_url": image_url if index == 0 else None,
                **{k: v for k, v in status.items()},
            })
        print(f"  [skill] ✂️ Delivered {len(segments)} segments")

    async def _deliver_audio(self, websocket: Any, audio_path: Optional[str]) -> None:
        if not audio_path or not os.path.isfile(audio_path):
            return
        try:
            with open(audio_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()
            await websocket.send_json({
                "type": "tts_audio",
                "audio": audio_b64,
                "format": self.audio_format_resolver(audio_path),
            })
            print(f"  [skill] 🔊 Audio delivered: {os.path.basename(audio_path)}")
        except Exception as e:
            print(f"  [skill] ⚠ Audio delivery failed: {e}")

    def _clear_pending_retry(self, agent: Any) -> None:
        if hasattr(agent, "_pending_retry") and agent._pending_retry:
            print("  [skill] 🧹 Cleared _pending_retry (already delivered via status)")
            agent._pending_retry = None

    async def _deliver_pending_retry(self, websocket: Any, agent: Any) -> None:
        retry = getattr(agent, "_pending_retry", None)
        if not retry:
            return
        await self.sleep(5)
        print(f"  [skill] 🔄 Delivering retry {retry['modality']}...")
        retry_image_url = self._image_url(retry.get("image_path"))
        await websocket.send_json({
            "type": "chat_end",
            "reply": retry["reply"],
            "modality": retry["modality"],
            "image_url": retry_image_url,
        })
        await self._deliver_audio(websocket, retry.get("audio_path"))
        agent._pending_retry = None

    def _log_and_persist_turn(
        self,
        *,
        persona_id: str,
        client_id: Optional[str],
        merged_text: str,
        clean_reply_text: str,
        modality: str,
        image_url: Optional[str],
        segments: Any,
    ) -> None:
        print(f"  [chat] 👤 {merged_text[:60]}")
        print(f"  [chat] 🤖 {clean_reply_text[:120]}")

        if not self.chat_log_store or not client_id:
            return
        try:
            if segments and isinstance(segments, list) and len(segments) > 1:
                self.chat_log_store.save_turn(
                    client_id=client_id,
                    persona_id=persona_id,
                    user_msg=merged_text,
                    agent_reply=segments[0],
                    modality=modality,
                    image_url=image_url,
                )
                for segment in segments[1:]:
                    self.chat_log_store.save_message(
                        client_id=client_id,
                        persona_id=persona_id,
                        role="assistant",
                        content=segment,
                        modality=modality,
                    )
            else:
                self.chat_log_store.save_turn(
                    client_id=client_id,
                    persona_id=persona_id,
                    user_msg=merged_text,
                    agent_reply=clean_reply_text,
                    modality=modality,
                    image_url=image_url,
                )
        except Exception as e:
            print(f"  [chat_log] save error: {e}")

    def _image_url(self, image_path: Optional[str]) -> Optional[str]:
        if not image_path:
            return None
        parts = image_path.replace("\\", "/").split("/")
        selfie_idx = parts.index("selfie") if "selfie" in parts else -1
        if selfie_idx >= 0:
            return "/api/selfie/" + "/".join(parts[selfie_idx + 1:])
        return f"/api/selfie/{os.path.basename(image_path)}"
