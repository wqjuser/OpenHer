"""Completed WebSocket turn delivery and persistence."""

from __future__ import annotations

import asyncio
import base64
import os
from typing import Any, Awaitable, Callable, Optional

from server.media import audio_format_for_path


SleepFunc = Callable[[float], Awaitable[Any]]


class WebSocketCompletedTurnDeliveryService:
    """Delivers completed chat turns to one client and persists display logs."""

    def __init__(
        self,
        *,
        chat_log_store: Any = None,
        sleep: SleepFunc = asyncio.sleep,
        audio_format_resolver: Callable[[str], str] = audio_format_for_path,
    ) -> None:
        self.chat_log_store = chat_log_store
        self.sleep = sleep
        self.audio_format_resolver = audio_format_resolver

    async def deliver_completed_turn(
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
