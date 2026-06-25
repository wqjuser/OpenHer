from __future__ import annotations

from typing import Protocol, cast


class _RelationshipHost(Protocol):
    _relationship_ema: dict[str, float]


class AgentRelationshipMixin:
    """Relationship state evolution methods for ChatAgent."""

    def _apply_relationship_ema(
        self,
        prior: dict[str, float],
        rel_delta: dict[str, float],
        conversation_depth: float,
    ) -> dict[str, float]:
        """
        Step 2.5: Semi-emergent relationship update.

        Pattern: posterior = clip(prior + LLM_delta) -> EMA smooth
          alpha = clip(0.15 + 0.5 * depth, 0.15, 0.65)
          state_t = alpha * posterior + (1 - alpha) * state_{t-1}

        First turn initializes EMA state from prior, then applies delta normally.
        """
        host = cast(_RelationshipHost, self)

        # Map Critic output keys to context feature keys.
        delta_map = {
            "relationship_depth": rel_delta.get("relationship_delta", 0.0),
            "emotional_valence": rel_delta.get("emotional_valence", 0.0),
            "trust_level": rel_delta.get("trust_delta", 0.0),
            "pending_foresight": 0.0,
        }

        if not host._relationship_ema:
            host._relationship_ema = dict(prior)

        posterior: dict[str, float] = {}
        for key in prior:
            lower_bound = -1.0 if key == "emotional_valence" else 0.0
            posterior[key] = max(
                lower_bound,
                min(1.0, prior[key] + delta_map.get(key, 0.0)),
            )

        alpha = max(0.15, min(0.65, 0.15 + 0.5 * conversation_depth))

        ema: dict[str, float] = {}
        for key in prior:
            previous = host._relationship_ema.get(key, prior[key])
            ema[key] = round(alpha * posterior[key] + (1 - alpha) * previous, 4)
        host._relationship_ema = ema

        print(
            f"  [emergence] α={alpha:.2f} | "
            f"depth: prior={prior['relationship_depth']:.2f} "
            f"δ={delta_map['relationship_depth']:+.2f} → ema={ema['relationship_depth']:.3f} | "
            f"trust: prior={prior['trust_level']:.2f} "
            f"δ={delta_map['trust_level']:+.2f} → ema={ema['trust_level']:.3f} | "
            f"valence: δ={delta_map['emotional_valence']:+.2f} → ema={ema['emotional_valence']:.3f} | "
            f"foresight={ema['pending_foresight']:.2f}"
        )

        return ema
