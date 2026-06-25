from __future__ import annotations

from typing import Any, Protocol, cast

from providers.llm.client import ChatMessage


class _ActorMessagesGenomeAgent(Protocol):
    def compute_signals(self, context: dict[str, Any]) -> dict[str, float]:
        ...


class _ActorMessagesMetabolism(Protocol):
    def apply_thermodynamic_noise(
        self,
        base_signals: dict[str, float],
    ) -> dict[str, float]:
        ...


class _ActorMessagesStyleMemory(Protocol):
    def set_clock(self, now: float) -> None:
        ...

    def build_few_shot_prompt(
        self,
        context: dict[str, Any],
        *,
        top_k: int,
        monologue_only: bool,
        lang: str,
    ) -> str:
        ...


class _ActorMessagesPersona(Protocol):
    lang: str


class _ActorMessagesHost(Protocol):
    agent: _ActorMessagesGenomeAgent
    metabolism: _ActorMessagesMetabolism
    style_memory: _ActorMessagesStyleMemory
    persona: _ActorMessagesPersona
    modality_skill_engine: Any
    history: list[ChatMessage]
    max_history: int
    _prev_signals: dict[str, float] | None
    _last_signals: dict[str, float] | None

    def _build_single_prompt(
        self,
        few_shot: str,
        noisy_signals: dict[str, float],
        *,
        modality_skill_engine: Any,
    ) -> str:
        ...

    async def _inject_memory_context(
        self,
        single_prompt: str,
        context: dict[str, Any],
    ) -> str:
        ...


class AgentActorMessagesMixin:
    """Actor prompt and message assembly for chat lifecycle entry points."""

    async def _prepare_actor_messages(
        self,
        user_message: str,
        context: dict[str, Any],
        now: float,
    ) -> list[ChatMessage]:
        host = cast(_ActorMessagesHost, self)

        base_signals = host.agent.compute_signals(context)
        noisy_signals = host.metabolism.apply_thermodynamic_noise(base_signals)
        host._prev_signals = host._last_signals
        host._last_signals = noisy_signals

        host.style_memory.set_clock(now)
        few_shot = host.style_memory.build_few_shot_prompt(
            context,
            top_k=3,
            monologue_only=False,
            lang=host.persona.lang,
        )

        single_prompt = host._build_single_prompt(
            few_shot,
            noisy_signals,
            modality_skill_engine=host.modality_skill_engine,
        )
        single_prompt = await host._inject_memory_context(single_prompt, context)

        single_messages = [ChatMessage(role="system", content=single_prompt)]
        single_messages.extend(host.history[-host.max_history :])
        single_messages.append(ChatMessage(role="user", content=user_message))
        return single_messages
