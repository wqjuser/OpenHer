"""Shared proactive WebSocket push protocol."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional


SleepFunc = Callable[[float], Awaitable[Any]]


@dataclass(frozen=True)
class ProactivePushPayload:
    reply: str
    modality: str
    segments: Any = None
    delays_ms: Any = None
    drive: Optional[str] = None
    persona: Optional[str] = None


class ProactiveWebSocketPushService:
    """Formats and sends proactive WebSocket messages."""

    def __init__(self, sleep: SleepFunc = asyncio.sleep) -> None:
        self.sleep = sleep

    async def push(
        self,
        websocket: Any,
        *,
        session_id: Optional[str],
        payload: ProactivePushPayload,
    ) -> None:
        """Send a proactive payload as either one message or timed segments."""
        if payload.segments and len(payload.segments) > 1:
            await self._push_segments(websocket, session_id=session_id, payload=payload)
            return

        message: dict[str, Any] = {
            "type": "proactive",
            "content": payload.reply,
            "modality": payload.modality,
        }
        message.update(self._metadata(payload))
        await websocket.send_json(message)

    async def _push_segments(
        self,
        websocket: Any,
        *,
        session_id: Optional[str],
        payload: ProactivePushPayload,
    ) -> None:
        for index, segment in enumerate(payload.segments):
            if index > 0:
                await websocket.send_json({
                    "type": "chat_start",
                    "session_id": session_id,
                })
                delay = (
                    payload.delays_ms[index]
                    if payload.delays_ms and index < len(payload.delays_ms)
                    else 300
                )
                await self.sleep(max(delay, 300) / 1000.0)

            message: dict[str, Any] = {
                "type": "chat_end",
                "reply": segment,
                "modality": payload.modality,
                "proactive": True,
            }
            message.update(self._metadata(payload))
            await websocket.send_json(message)

    def _metadata(self, payload: ProactivePushPayload) -> dict[str, str]:
        metadata: dict[str, str] = {}
        if payload.drive is not None:
            metadata["drive"] = payload.drive
        if payload.persona is not None:
            metadata["persona"] = payload.persona
        return metadata
