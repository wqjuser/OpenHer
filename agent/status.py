from __future__ import annotations

from typing import Any, Protocol, cast

from engine.genome.genome_engine import DRIVE_LABELS, DRIVES


class _StatusPersona(Protocol):
    name: str


class _StatusStyleMemory(Protocol):
    def stats(self) -> dict[str, Any]:
        ...

    def last_recall_info(self) -> Any:
        ...


class _StatusMetabolism(Protocol):
    frustration: dict[str, float]

    def status_summary(self) -> dict[str, Any]:
        ...

    def total(self) -> float:
        ...

    def temperature(self) -> float:
        ...


class _StatusGenomeAgent(Protocol):
    drive_baseline: dict[str, float]
    drive_state: dict[str, float]
    age: int
    _last_input: list[float] | None
    _last_hidden: list[float] | None

    def get_dominant_drive(self) -> str:
        ...


class _StatusHost(Protocol):
    persona: _StatusPersona
    agent: _StatusGenomeAgent
    metabolism: _StatusMetabolism
    style_memory: _StatusStyleMemory
    history: list[Any]
    _last_signals: dict[str, float] | None
    _last_drive_satisfaction: dict[str, float]
    _turn_count: int
    _last_reward: float
    _last_modality: str
    _relationship_ema: dict[str, float]
    evermemos: Any
    _search_hit: int
    _search_timeout: int
    _search_fallback: int
    _search_relevant_used: int
    _skill_outputs: dict[str, Any]
    _last_critic: dict[str, Any] | None
    _last_action: dict[str, Any] | None


class AgentStatusMixin:
    def get_status(self) -> dict:
        """Get comprehensive agent status including genome state."""
        host = cast(_StatusHost, self)
        mem_stats = host.style_memory.stats()
        metabolism_status = host.metabolism.status_summary()

        signals_summary = {}
        if host._last_signals:
            sorted_sigs = sorted(
                host._last_signals.items(),
                key=lambda x: abs(x[1] - 0.5),
                reverse=True,
            )[:3]
            signals_summary = {k: round(v, 2) for k, v in sorted_sigs}

        dominant_drive = host.agent.get_dominant_drive()

        total_searches = host._search_hit + host._search_timeout
        search_hit_rate = host._search_hit / total_searches if total_searches else 0.0
        search_timeout_rate = (
            host._search_timeout / total_searches if total_searches else 0.0
        )
        turns = max(host._turn_count, 1)
        fallback_rate = host._search_fallback / turns
        relevant_injection_ratio = host._search_relevant_used / turns

        return {
            "persona": host.persona.name,
            "dominant_drive": DRIVE_LABELS.get(dominant_drive, dominant_drive),
            "drive_baseline": {
                d: round(host.agent.drive_baseline[d], 3) for d in DRIVES
            },
            "drive_state": {d: round(host.agent.drive_state[d], 3) for d in DRIVES},
            "drive_satisfaction": (
                {d: round(v, 3) for d, v in host._last_drive_satisfaction.items()}
                if host._last_drive_satisfaction
                else {}
            ),
            "signals": signals_summary,
            "temperature": metabolism_status["temperature"],
            "frustration": metabolism_status["total"],
            "history_length": len(host.history),
            "turn_count": host._turn_count,
            "memory_count": mem_stats.get("total", 0),
            "personal_memories": mem_stats.get("personal_count", 0),
            "age": host.agent.age,
            "last_reward": round(host._last_reward, 2),
            "modality": host._last_modality,
            "relationship": {
                "depth": round(host._relationship_ema.get("relationship_depth", 0.0), 3),
                "trust": round(host._relationship_ema.get("trust_level", 0.0), 3),
                "valence": round(host._relationship_ema.get("emotional_valence", 0.0), 3),
            },
            "evermemos": (
                "ON" if (host.evermemos and host.evermemos.available) else "OFF"
            ),
            "search_hit": host._search_hit,
            "search_timeout": host._search_timeout,
            "search_fallback": host._search_fallback,
            "search_hit_rate": round(search_hit_rate, 3),
            "search_timeout_rate": round(search_timeout_rate, 3),
            "fallback_rate": round(fallback_rate, 3),
            "relevant_injection_ratio": round(relevant_injection_ratio, 3),
            **host._skill_outputs,
        }

    def get_debug_status(self) -> dict:
        """Get full engine state for developer visualization."""
        host = cast(_StatusHost, self)
        input_vec = host.agent._last_input or [0.0] * 25
        hidden_vec = host.agent._last_hidden or [0.0] * 24

        sig = {}
        if host._last_signals:
            sig = {s: round(v, 4) for s, v in host._last_signals.items()}

        ctx = {}
        if host._last_critic:
            ctx = {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in host._last_critic.items()
            }

        drive_st = {d: round(host.agent.drive_state[d], 4) for d in DRIVES}
        sig_str = " ".join(f"{k[:3]}={v:.2f}" for k, v in sig.items())
        drv_str = " ".join(f"{k[:3]}={v:.2f}" for k, v in drive_st.items())
        mono_preview = (
            host._last_action.get("monologue", "") if host._last_action else ""
        )[:40]
        print(f"  [debug-viz] signals: {sig_str}")
        print(f"  [debug-viz] drives:  {drv_str}")
        print(f"  [debug-viz] mono:    {mono_preview}")

        return {
            "context_vector": ctx,
            "signals": sig,
            "hidden_activations": [round(h, 4) for h in hidden_vec],
            "input_vector": [round(v, 4) for v in input_vec],
            "drive_state": drive_st,
            "drive_baseline": {
                d: round(host.agent.drive_baseline[d], 4) for d in DRIVES
            },
            "frustration": {
                d: round(host.metabolism.frustration[d], 4) for d in DRIVES
            },
            "total_frustration": round(host.metabolism.total(), 4),
            "temperature": round(host.metabolism.temperature(), 4),
            "monologue": (
                host._last_action.get("monologue", "") if host._last_action else ""
            ),
            "style_recall": host.style_memory.last_recall_info(),
            "relationship": {
                "depth": round(host._relationship_ema.get("relationship_depth", 0.0), 4),
                "trust": round(host._relationship_ema.get("trust_level", 0.0), 4),
                "valence": round(
                    host._relationship_ema.get("emotional_valence", 0.0), 4
                ),
            },
            "reward": round(host._last_reward, 4),
            "age": host.agent.age,
            "turn_count": host._turn_count,
            "phase_transition": getattr(host.agent, "_last_phase_transition", False),
        }
