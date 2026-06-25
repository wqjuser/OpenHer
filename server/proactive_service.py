"""Proactive heartbeat and outbox delivery orchestration."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Optional

from agent.chat_agent import ChatAgent
from engine.state_store import StateStore
from providers.memory.evermemos.evermemos_client import EverMemOSClient
from server.proactive_delivery import (
    ProactiveDeliveryResult,
    ProactiveOutboxDeliveryService,
)
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
        delivery_service: Optional[ProactiveOutboxDeliveryService] = None,
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
        self.delivery_service = delivery_service or ProactiveOutboxDeliveryService(
            state_store=state_store,
            evermemos=evermemos,
            ws_connections=ws_connections,
        )

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
        result = await self.delivery_service.deliver(agent, session_id, row)
        self._apply_delivery_result(result)

    def _apply_delivery_result(self, result: ProactiveDeliveryResult) -> None:
        if result.ws_push_failed:
            self.metrics["ws_push_fail"] += 1
        if result.ws_push_ok:
            self.metrics["ws_push_ok"] += 1
        if result.delivered:
            self.metrics["outbox_delivered"] += 1

    def metrics_snapshot(self) -> dict[str, int | float]:
        """Return counters plus derived rates for the metrics endpoint."""
        m: dict[str, int | float] = dict(self.metrics)
        total = int(m["ticks_total"]) or 1
        m["impulse_rate"] = round(int(m["impulse_triggered"]) / total, 4)
        m["silence_rate"] = round(int(m["silence_chosen"]) / max(int(m["impulse_triggered"]), 1), 4)
        ws_total = int(m["ws_push_ok"]) + int(m["ws_push_fail"]) or 1
        m["ws_success_rate"] = round(int(m["ws_push_ok"]) / ws_total, 4)
        return m
