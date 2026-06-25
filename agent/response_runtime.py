from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

from agent.modality_execution import ModalityExecutionResult
from agent.parser import extract_reply


@dataclass
class CompletedActorResponse:
    reply: str
    modality: str
    monologue: str
    outputs: dict[str, Any]


class _ResponseRuntimeGenomeAgent(Protocol):
    def step(
        self,
        context: dict[str, Any],
        *,
        reward: float,
        drive_satisfaction: dict[str, float],
    ) -> None:
        ...


class _ResponseRuntimeHost(Protocol):
    agent: _ResponseRuntimeGenomeAgent
    _last_drive_satisfaction: dict[str, float]

    async def _execute_modality_skills(
        self,
        raw_text: str,
        reply: str,
        modality: str,
    ) -> ModalityExecutionResult:
        ...

    def _finalize_turn_response(
        self,
        user_message: str,
        reply: str,
        monologue: str,
        modality: str,
        context: dict[str, Any],
        drive_satisfaction: dict[str, float],
        reward: float,
        *,
        is_proactive: bool = False,
    ) -> None:
        ...


class AgentResponseRuntimeMixin:
    """Post-Actor response processing shared by chat entry points."""

    async def _complete_actor_response(
        self,
        user_message: str,
        raw_text: str,
        context: dict[str, Any],
        drive_satisfaction: dict[str, float],
        reward: float,
        *,
        is_proactive: bool = False,
    ) -> CompletedActorResponse:
        host = cast(_ResponseRuntimeHost, self)

        monologue, reply, modality = extract_reply(raw_text)

        modality_result = await host._execute_modality_skills(raw_text, reply, modality)
        reply = modality_result.reply
        modality = modality_result.modality

        clamped_reward = max(-1.0, min(1.0, reward))
        host.agent.step(context, reward=clamped_reward, drive_satisfaction=drive_satisfaction)
        host._last_drive_satisfaction = drive_satisfaction
        host._finalize_turn_response(
            user_message,
            reply,
            monologue,
            modality,
            context,
            drive_satisfaction,
            reward,
            is_proactive=is_proactive,
        )

        return CompletedActorResponse(
            reply=reply,
            modality=modality,
            monologue=monologue,
            outputs=modality_result.outputs,
        )
