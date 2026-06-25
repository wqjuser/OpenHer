"""Proactive outbox delivery through the persona engine and WebSocket."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


SleepFunc = Callable[[float], Awaitable[Any]]


@dataclass(frozen=True)
class ProactiveDeliveryResult:
    attempted: bool
    delivered: bool
    ws_push_ok: bool
    ws_push_failed: bool
    reply: str = ""
    sent_count: int = 0


class ProactiveOutboxDeliveryService:
    """Delivers one proactive outbox row and updates outbox state."""

    def __init__(
        self,
        *,
        state_store: Any,
        evermemos: Any,
        ws_connections: dict[str, set[Any]],
        sleep: SleepFunc = asyncio.sleep,
    ) -> None:
        self.state_store = state_store
        self.evermemos = evermemos
        self.ws_connections = ws_connections
        self.sleep = sleep

    async def deliver(
        self,
        agent: Any,
        session_id: str,
        row: dict[str, Any],
    ) -> ProactiveDeliveryResult:
        uid = row["user_id"]
        pid = row["persona_id"]
        tick_id = row["tick_id"]
        raw_reply = row["reply"]
        drive_id = row.get("drive_id", "")

        msg = self.state_store.outbox_try_send(uid, pid, tick_id)
        if not msg:
            return ProactiveDeliveryResult(
                attempted=False,
                delivered=False,
                ws_push_ok=False,
                ws_push_failed=False,
            )

        reply, modality, segments, delays_ms = await self._reprocess_with_engine(
            agent,
            raw_reply,
            row,
        )

        ws_set = self.ws_connections.get(session_id, set())
        if not ws_set:
            self.state_store.outbox_mark_failed(uid, pid, tick_id)
            return ProactiveDeliveryResult(
                attempted=True,
                delivered=False,
                ws_push_ok=False,
                ws_push_failed=False,
                reply=reply,
            )

        sent_count = await self._push_to_websockets(
            ws_set=ws_set,
            session_id=session_id,
            agent=agent,
            reply=reply,
            modality=modality,
            segments=segments,
            delays_ms=delays_ms,
            drive_id=drive_id,
        )
        if sent_count == 0:
            print("  [proactive] WS push failed: no active clients accepted message")
            self.state_store.outbox_mark_failed(uid, pid, tick_id)
            return ProactiveDeliveryResult(
                attempted=True,
                delivered=False,
                ws_push_ok=False,
                ws_push_failed=True,
                reply=reply,
            )

        print(f"  [proactive] WS pushed to {sent_count} client(s): {reply[:40]}")
        await self._store_proactive_turn(agent, uid, pid, reply, tick_id)
        self.state_store.outbox_mark_delivered(uid, pid, tick_id)
        print(f"  [proactive] delivered: {reply[:40]}")
        return ProactiveDeliveryResult(
            attempted=True,
            delivered=True,
            ws_push_ok=True,
            ws_push_failed=False,
            reply=reply,
            sent_count=sent_count,
        )

    async def _reprocess_with_engine(
        self,
        agent: Any,
        raw_reply: str,
        row: dict[str, Any],
    ) -> tuple[str, str, Any, Any]:
        stimulus = (
            "[系统指令] 你现在想主动对用户说话。以下是你想表达的内容，请用你认为的方式表达出来：\n"
            f"{raw_reply}"
        )
        try:
            engine_result = await agent.chat(stimulus, is_proactive=True)
            reply = engine_result.get("reply", raw_reply)
            modality = engine_result.get("modality", "文字")
            segments = engine_result.get("segments")
            delays_ms = engine_result.get("delays_ms")
            print(
                "  [proactive] engine re-processed: "
                f"modality={modality}, segments={len(segments) if segments else 0}"
            )
            return reply, modality, segments, delays_ms
        except Exception as e:
            print(f"  [proactive] engine re-process failed, using raw reply: {e}")
            return raw_reply, row.get("modality", "文字"), None, None

    async def _push_to_websockets(
        self,
        *,
        ws_set: set[Any],
        session_id: str,
        agent: Any,
        reply: str,
        modality: str,
        segments: Any,
        delays_ms: Any,
        drive_id: str,
    ) -> int:
        sent_count = 0
        try:
            for ws in list(ws_set):
                try:
                    if segments and len(segments) > 1:
                        await self._send_segments(
                            ws=ws,
                            session_id=session_id,
                            agent=agent,
                            segments=segments,
                            delays_ms=delays_ms,
                            modality=modality,
                            drive_id=drive_id,
                        )
                    else:
                        await ws.send_json({
                            "type": "proactive",
                            "content": reply,
                            "modality": modality,
                            "drive": drive_id,
                            "persona": agent.persona.name,
                        })
                    sent_count += 1
                except Exception:
                    ws_set.discard(ws)
            return sent_count
        except Exception as ws_err:
            print(f"  [proactive] WS push failed: {ws_err}")
            return 0

    async def _send_segments(
        self,
        *,
        ws: Any,
        session_id: str,
        agent: Any,
        segments: Any,
        delays_ms: Any,
        modality: str,
        drive_id: str,
    ) -> None:
        for i, seg in enumerate(segments):
            if i > 0:
                await ws.send_json({
                    "type": "chat_start",
                    "session_id": session_id,
                })
                delay = delays_ms[i] if delays_ms and i < len(delays_ms) else 300
                await self.sleep(max(delay, 300) / 1000.0)
            await ws.send_json({
                "type": "chat_end",
                "reply": seg,
                "modality": modality,
                "proactive": True,
                "drive": drive_id,
                "persona": agent.persona.name,
            })

    async def _store_proactive_turn(
        self,
        agent: Any,
        uid: str,
        pid: str,
        reply: str,
        tick_id: str,
    ) -> None:
        try:
            if self.evermemos and self.evermemos.available:
                await self.evermemos.store_proactive_turn(
                    user_id=uid,
                    persona_id=pid,
                    persona_name=agent.persona.name,
                    group_id=agent._group_id,
                    reply=reply,
                    tick_id=tick_id,
                )
        except Exception as e:
            print(f"  [proactive] EverMemOS store failed (non-fatal): {e}")
