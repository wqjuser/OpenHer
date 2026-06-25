from __future__ import annotations

from typing import Any, Protocol, cast

from providers.llm.client import ChatMessage


class _TurnFinalizationPersona(Protocol):
    persona_id: str


class _TurnFinalizationMetabolism(Protocol):
    def temperature(self) -> float:
        ...


class _TurnFinalizationMemoryStore(Protocol):
    def add(self, **kwargs: Any) -> None:
        ...


class _TurnFinalizationHost(Protocol):
    history: list[ChatMessage]
    max_history: int
    _fallback_history_added: bool
    _last_action: dict[str, Any] | None
    _last_modality: str
    memory_store: _TurnFinalizationMemoryStore | None
    user_id: str
    persona: _TurnFinalizationPersona
    metabolism: _TurnFinalizationMetabolism

    def _evermemos_store_bg(self, user_message: str, reply: str) -> None:
        ...

    def _evermemos_search_bg(self, user_message: str) -> None:
        ...


class AgentTurnFinalizationMixin:
    """Completed-turn state updates for chat lifecycle entry points."""

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
        host = cast(_TurnFinalizationHost, self)

        if not is_proactive:
            host.history.append(ChatMessage(role="user", content=user_message))
        if not getattr(host, "_fallback_history_added", False):
            host.history.append(ChatMessage(role="assistant", content=reply))
        host._fallback_history_added = False

        if len(host.history) > host.max_history:
            host.history = host.history[-host.max_history :]

        host._last_action = {
            "context": context,
            "monologue": monologue,
            "reply": reply,
            "modality": modality,
            "user_input": user_message,
        }
        host._last_modality = modality

        if host.memory_store and not is_proactive:
            host.memory_store.add(
                user_id=host.user_id,
                persona_id=host.persona.persona_id,
                content=user_message,
                category="user_message",
                importance=context.get("entropy", 0.5),
            )

        sat_str = " ".join(
            f"{drive[:3]}={value:.2f}"
            for drive, value in drive_satisfaction.items()
            if value > 0
        )
        print(
            f"  [genome] reward={reward:.2f} "
            f"temp={host.metabolism.temperature():.3f} modality={modality[:30]}"
        )
        print(f"  [feel] monologue={monologue[:60]}")
        print(f"  [drive_sat] {sat_str or 'none'}")

        if not is_proactive:
            host._evermemos_store_bg(user_message, reply)
            host._evermemos_search_bg(user_message)
