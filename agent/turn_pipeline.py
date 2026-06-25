from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

from providers.llm.client import ChatMessage


@dataclass
class PreparedTurn:
    user_message: str
    now: float
    context: dict[str, Any]
    frustration_delta: dict[str, float]
    drive_satisfaction: dict[str, float]
    reward: float
    actor_messages: list[ChatMessage]


class _TurnPipelineMetabolism(Protocol):
    def time_metabolism(self, now: float) -> float:
        ...

    def apply_llm_delta(self, frustration_delta: dict[str, float]) -> float:
        ...

    def sync_to_agent(self, agent: Any) -> None:
        ...


class _TurnPipelineHost(Protocol):
    metabolism: _TurnPipelineMetabolism
    agent: Any
    _last_reward: float

    async def _run_task_skills(self, user_message: str) -> str:
        ...

    def _begin_turn(self) -> float:
        ...

    async def _evermemos_gather(self) -> dict[str, float]:
        ...

    async def _sense_critic_context(
        self,
        user_message: str,
        relationship_prior: dict[str, float],
    ) -> tuple[dict[str, Any], dict[str, float], dict[str, float]]:
        ...

    def _evolve_drive_baseline(self, frustration_delta: dict[str, float]) -> None:
        ...

    def _crystallize_last_action_if_needed(
        self,
        reward: float,
        context: dict[str, Any],
        now: float,
    ) -> bool:
        ...

    async def _prepare_actor_messages(
        self,
        user_message: str,
        context: dict[str, Any],
        now: float,
    ) -> list[ChatMessage]:
        ...


class AgentTurnPipelineMixin:
    """Shared pre-Actor turn lifecycle for chat entry points."""

    async def _prepare_turn_for_actor(self, user_message: str) -> PreparedTurn:
        host = cast(_TurnPipelineHost, self)

        user_message = await host._run_task_skills(user_message)
        now = host._begin_turn()
        relationship_prior = await host._evermemos_gather()
        host.metabolism.time_metabolism(now)

        context, frustration_delta, drive_satisfaction = await host._sense_critic_context(
            user_message,
            relationship_prior,
        )

        reward = host.metabolism.apply_llm_delta(frustration_delta)
        host.metabolism.sync_to_agent(host.agent)
        host._last_reward = reward

        host._evolve_drive_baseline(frustration_delta)
        host._crystallize_last_action_if_needed(reward, context, now)

        actor_messages = await host._prepare_actor_messages(user_message, context, now)

        return PreparedTurn(
            user_message=user_message,
            now=now,
            context=context,
            frustration_delta=frustration_delta,
            drive_satisfaction=drive_satisfaction,
            reward=reward,
            actor_messages=actor_messages,
        )
