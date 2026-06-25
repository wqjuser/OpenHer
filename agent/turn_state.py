from __future__ import annotations

import time
from typing import Protocol, cast


class _TurnStateHost(Protocol):
    _turn_count: int
    _turn_used_fallback: bool
    _last_active: float
    _interaction_cadence: float


class AgentTurnStateMixin:
    """Per-turn bookkeeping for chat lifecycle entry points."""

    def _begin_turn(self, now: float | None = None) -> float:
        host = cast(_TurnStateHost, self)
        if now is None:
            now = time.time()

        host._turn_count += 1
        host._turn_used_fallback = False

        if host._last_active > 0:
            delta = now - host._last_active
            if host._interaction_cadence > 0:
                host._interaction_cadence = (
                    0.3 * delta + 0.7 * host._interaction_cadence
                )
            else:
                host._interaction_cadence = delta
        host._last_active = now

        return now
