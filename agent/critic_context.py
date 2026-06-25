from __future__ import annotations

from typing import Any, Protocol, cast

from engine.genome.critic import critic_sense
from engine.genome.genome_engine import DRIVES


class _CriticContextPersona(Protocol):
    name: str
    mbti: str
    tags: list[str]


class _CriticContextMetabolism(Protocol):
    frustration: dict[str, float]


class _CriticContextHost(Protocol):
    metabolism: _CriticContextMetabolism
    persona: _CriticContextPersona
    llm: Any
    _user_profile: str
    _episode_summary: str
    _last_critic: dict[str, Any] | None

    def _apply_relationship_ema(
        self,
        prior: dict[str, float],
        rel_delta: dict[str, float],
        conversation_depth: float,
    ) -> dict[str, float]:
        ...


class AgentCriticContextMixin:
    """Critic perception and relationship context merge for chat turns."""

    async def _sense_critic_context(
        self,
        user_message: str,
        relationship_prior: dict[str, float],
    ) -> tuple[dict[str, Any], dict[str, float], dict[str, float]]:
        host = cast(_CriticContextHost, self)

        frust_dict = {
            drive: round(host.metabolism.frustration[drive], 2) for drive in DRIVES
        }
        context, frustration_delta, rel_delta, drive_satisfaction = await critic_sense(
            user_message,
            host.llm,
            frust_dict,
            user_profile=host._user_profile,
            episode_summary=host._episode_summary,
            persona_hint=self._build_critic_persona_hint(),
        )

        relationship_4d = host._apply_relationship_ema(
            relationship_prior,
            rel_delta,
            context.get("conversation_depth", 0.0),
        )
        context.update(relationship_4d)
        host._last_critic = context

        return context, frustration_delta, drive_satisfaction

    def _build_critic_persona_hint(self) -> str:
        host = cast(_CriticContextHost, self)
        mbti = getattr(host.persona, "mbti", "") or "未知"
        tags = "、".join(getattr(host.persona, "tags", [])[:3])
        if tags:
            return f"{host.persona.name} ({mbti}) — {tags}"
        return f"{host.persona.name} ({mbti})"
