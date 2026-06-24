"""Proactive heartbeat and outbox delivery orchestration."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Optional

from agent.chat_agent import ChatAgent
from engine.state_store import StateStore
from providers.memory.evermemos.evermemos_client import EverMemOSClient
from server.session_manager import SessionManager


DEFAULT_PROACTIVE_CONFIG: dict[str, int | float] = {
    "cooldown_hours": 4,
    "max_pending": 3,
    "lock_ttl": 600,
}


def default_proactive_metrics() -> dict[str, int]:
    return {
        "ticks_total": 0,
        "impulse_triggered": 0,
        "silence_chosen": 0,
        "outbox_enqueued": 0,
        "outbox_blocked": 0,
        "ws_push_ok": 0,
        "ws_push_fail": 0,
        "outbox_delivered": 0,
        "outbox_retries": 0,
    }


class ProactiveService:
    """Runs autonomous proactive ticks and delivers pending outbox messages."""

    def __init__(
        self,
        *,
        state_store: StateStore,
        session_manager: SessionManager,
        evermemos: Optional[EverMemOSClient],
        ws_connections: dict[str, set[Any]],
        persist_agent: Callable[[ChatAgent], None],
        instance_id: str,
        config: Optional[dict[str, Any]] = None,
        interval_seconds: int = 300,
        initial_delay_seconds: int = 60,
    ):
        self.state_store = state_store
        self.session_manager = session_manager
        self.evermemos = evermemos
        self.ws_connections = ws_connections
        self.persist_agent = persist_agent
        self.instance_id = instance_id
        self.config = {**DEFAULT_PROACTIVE_CONFIG, **(config or {})}
        self.interval_seconds = interval_seconds
        self.initial_delay_seconds = initial_delay_seconds
        self.metrics = default_proactive_metrics()

    async def heartbeat_loop(self) -> None:
        """Background loop for proactive sweeps."""
        await asyncio.sleep(self.initial_delay_seconds)
        while True:
            try:
                await self.sweep()
            except Exception as e:
                print(f"[proactive] heartbeat error: {e}")
            await asyncio.sleep(self.interval_seconds)

    async def sweep(self) -> None:
        """Generate new proactive messages and retry pending outbox rows."""
        if not self.state_store or not self.session_manager or not self.session_manager.sessions:
            return

        cooldown_h = self.config.get("cooldown_hours", 4)
        max_pending = self.config.get("max_pending", 3)
        lock_ttl = self.config.get("lock_ttl", 600)

        for sid, (agent, _last) in list(self.session_manager.sessions.items()):
            uid = agent.user_id
            pid = agent.persona.persona_id

            if not self.state_store.try_acquire_lock(uid, pid, self.instance_id, ttl=lock_ttl):
                continue

            try:
                self.metrics["ticks_total"] += 1
                result = await agent.proactive_tick()
                if result is not None:
                    self.metrics["impulse_triggered"] += 1
                    drive_id = result.get("drive_id", "unknown")
                    depth = agent._relationship_ema.get("relationship_depth", 0.0)
                    band = "deep" if depth > 0.6 else "mid" if depth > 0.3 else "shallow"
                    bucket = int(time.time() // (float(cooldown_h) * 3600))
                    dedup_key = f"{drive_id}:{band}:{bucket}"

                    if self.state_store.outbox_can_enqueue(
                        uid,
                        pid,
                        dedup_key,
                        cooldown_hours=cooldown_h,
                        max_pending=max_pending,
                    ):
                        self.state_store.outbox_insert(
                            uid,
                            pid,
                            result["tick_id"],
                            result["reply"],
                            result.get("modality", "文字"),
                            result.get("monologue", ""),
                            drive_id,
                            dedup_key,
                        )
                        self.metrics["outbox_enqueued"] += 1
                    else:
                        self.metrics["outbox_blocked"] += 1
                        print(f"  [proactive] outbox guard blocked: {dedup_key}")
                elif result is None and agent._has_impulse():
                    self.metrics["silence_chosen"] += 1

                pending = self.state_store.outbox_get_pending(uid, pid)
                for row in pending:
                    is_retry = row.get("status") == "pending" and row["tick_id"] != (result or {}).get("tick_id")
                    if is_retry:
                        self.metrics["outbox_retries"] += 1
                    await self.deliver_message(agent, sid, row)

                self.persist_agent(agent)
            finally:
                self.state_store.release_lock(uid, pid, self.instance_id)

    async def deliver_message(self, agent: ChatAgent, session_id: str, row: dict[str, Any]) -> None:
        """Deliver one proactive outbox message through the persona engine and WebSocket."""
        uid = row["user_id"]
        pid = row["persona_id"]
        tick_id = row["tick_id"]
        raw_reply = row["reply"]
        drive_id = row.get("drive_id", "")

        msg = self.state_store.outbox_try_send(uid, pid, tick_id)
        if not msg:
            return

        stimulus = f"[系统指令] 你现在想主动对用户说话。以下是你想表达的内容，请用你认为的方式表达出来：\n{raw_reply}"
        try:
            engine_result = await agent.chat(stimulus, is_proactive=True)
            reply = engine_result.get("reply", raw_reply)
            modality = engine_result.get("modality", "文字")
            segments = engine_result.get("segments")
            delays_ms = engine_result.get("delays_ms")
            print(f"  [proactive] engine re-processed: modality={modality}, segments={len(segments) if segments else 0}")
        except Exception as e:
            print(f"  [proactive] engine re-process failed, using raw reply: {e}")
            reply = raw_reply
            modality = row.get("modality", "文字")
            segments = None
            delays_ms = None

        ws_set = self.ws_connections.get(session_id, set())
        if not ws_set:
            self.state_store.outbox_mark_failed(uid, pid, tick_id)
            return

        sent_count = 0
        try:
            for ws in list(ws_set):
                try:
                    if segments and len(segments) > 1:
                        for i, seg in enumerate(segments):
                            if i > 0:
                                await ws.send_json({
                                    "type": "chat_start",
                                    "session_id": session_id,
                                })
                                delay = delays_ms[i] if delays_ms and i < len(delays_ms) else 300
                                await asyncio.sleep(max(delay, 300) / 1000.0)
                            await ws.send_json({
                                "type": "chat_end",
                                "reply": seg,
                                "modality": modality,
                                "proactive": True,
                                "drive": drive_id,
                                "persona": agent.persona.name,
                            })
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
            if sent_count == 0:
                print("  [proactive] WS push failed: no active clients accepted message")
                self.metrics["ws_push_fail"] += 1
                self.state_store.outbox_mark_failed(uid, pid, tick_id)
                return
            print(f"  [proactive] WS pushed to {sent_count} client(s): {reply[:40]}")
            self.metrics["ws_push_ok"] += 1
        except Exception as ws_err:
            print(f"  [proactive] WS push failed: {ws_err}")
            self.metrics["ws_push_fail"] += 1
            self.state_store.outbox_mark_failed(uid, pid, tick_id)
            return

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

        self.state_store.outbox_mark_delivered(uid, pid, tick_id)
        self.metrics["outbox_delivered"] += 1
        print(f"  [proactive] delivered: {reply[:40]}")

    def metrics_snapshot(self) -> dict[str, int | float]:
        """Return counters plus derived rates for the metrics endpoint."""
        m: dict[str, int | float] = dict(self.metrics)
        total = int(m["ticks_total"]) or 1
        m["impulse_rate"] = round(int(m["impulse_triggered"]) / total, 4)
        m["silence_rate"] = round(int(m["silence_chosen"]) / max(int(m["impulse_triggered"]), 1), 4)
        ws_total = int(m["ws_push_ok"]) + int(m["ws_push_fail"]) or 1
        m["ws_success_rate"] = round(int(m["ws_push_ok"]) / ws_total, 4)
        return m
