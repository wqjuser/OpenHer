from __future__ import annotations

from typing import Any, Protocol, cast

from engine.genome.genome_engine import DRIVES


class _DriveLifecycleGenomeAgent(Protocol):
    drive_baseline: dict[str, float]


class _DriveLifecycleStyleMemory(Protocol):
    def set_clock(self, now: float) -> None:
        ...

    def crystallize(
        self,
        context: dict[str, Any],
        monologue: str,
        reply: str,
        user_input: str,
    ) -> None:
        ...


class _DriveLifecycleHost(Protocol):
    agent: _DriveLifecycleGenomeAgent
    _initial_baseline: dict[str, float]
    baseline_lr: float
    elasticity: float
    style_memory: _DriveLifecycleStyleMemory
    _last_action: dict[str, Any] | None

    def _should_crystallize(self, reward: float, context: dict[str, Any]) -> bool:
        ...


class AgentDriveLifecycleMixin:
    """Drive baseline and crystallization lifecycle helpers for ChatAgent."""

    def _evolve_drive_baseline(self, frustration_delta: dict[str, float]) -> None:
        host = cast(_DriveLifecycleHost, self)

        for drive in DRIVES:
            shift = frustration_delta.get(drive, 0.0) * host.baseline_lr
            baseline = host.agent.drive_baseline[drive]
            drift = baseline - host._initial_baseline.get(drive, 0.5)
            pull_back = -drift * host.elasticity
            host.agent.drive_baseline[drive] = max(
                0.1,
                min(0.95, baseline + shift + pull_back),
            )

    def _crystallize_last_action_if_needed(
        self,
        reward: float,
        context: dict[str, Any],
        now: float,
    ) -> bool:
        host = cast(_DriveLifecycleHost, self)
        last_action = host._last_action
        if not last_action:
            return False
        if not host._should_crystallize(reward, context):
            return False

        host.style_memory.set_clock(now)
        host.style_memory.crystallize(
            last_action["context"],
            last_action["monologue"],
            last_action["reply"],
            last_action["user_input"],
        )
        return True
