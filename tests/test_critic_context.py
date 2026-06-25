from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib
import importlib.util
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class FakeMetabolism:
    def __init__(self):
        self.frustration = {
            "connection": 0.124,
            "novelty": 0.235,
            "expression": 0.346,
            "safety": 0.457,
            "play": 0.568,
        }


def make_agent(persona: Any | None = None):
    spec = importlib.util.find_spec("agent.critic_context")
    assert spec is not None
    module = importlib.import_module("agent.critic_context")

    class DummyAgent(module.AgentCriticContextMixin):
        def __init__(self):
            self.metabolism = FakeMetabolism()
            self.llm = object()
            self.persona = persona or SimpleNamespace(
                name="Luna",
                mbti="ENFP",
                tags=["warm", "curious", "playful", "extra"],
            )
            self._user_profile = "likes tea"
            self._episode_summary = "met yesterday"
            self._last_critic: dict[str, Any] | None = None
            self.relationship_calls: list[tuple[dict[str, float], dict[str, float], float]] = []

        def _apply_relationship_ema(
            self,
            prior: dict[str, float],
            rel_delta: dict[str, float],
            conversation_depth: float,
        ) -> dict[str, float]:
            self.relationship_calls.append((prior, rel_delta, conversation_depth))
            return {
                "relationship_depth": 0.42,
                "trust_level": 0.51,
                "emotional_valence": 0.12,
                "pending_foresight": 0.05,
            }

    return DummyAgent(), module


async def test_critic_context_mixin_senses_and_merges_relationship(monkeypatch):
    agent, module = make_agent()
    calls: list[dict[str, Any]] = []

    async def fake_critic_sense(
        user_message,
        llm,
        frust_dict,
        *,
        user_profile,
        episode_summary,
        persona_hint,
    ):
        calls.append(
            {
                "user_message": user_message,
                "llm": llm,
                "frust_dict": frust_dict,
                "user_profile": user_profile,
                "episode_summary": episode_summary,
                "persona_hint": persona_hint,
            }
        )
        return (
            {"conversation_depth": 0.6, "entropy": 0.8},
            {"connection": 0.1, "play": -0.2},
            {"relationship_delta": 0.3, "trust_delta": 0.2},
            {"connection": 0.9, "play": 0.1},
        )

    monkeypatch.setattr(module, "critic_sense", fake_critic_sense)
    relationship_prior = {
        "relationship_depth": 0.2,
        "trust_level": 0.3,
        "emotional_valence": 0.0,
        "pending_foresight": 0.0,
    }

    context, frustration_delta, drive_satisfaction = await agent._sense_critic_context(
        "hello",
        relationship_prior,
    )

    assert calls == [
        {
            "user_message": "hello",
            "llm": agent.llm,
            "frust_dict": {
                "connection": 0.12,
                "novelty": 0.23,
                "expression": 0.35,
                "safety": 0.46,
                "play": 0.57,
            },
            "user_profile": "likes tea",
            "episode_summary": "met yesterday",
            "persona_hint": "Luna (ENFP) — warm、curious、playful",
        }
    ]
    assert agent.relationship_calls == [
        (
            relationship_prior,
            {"relationship_delta": 0.3, "trust_delta": 0.2},
            0.6,
        )
    ]
    assert context == {
        "conversation_depth": 0.6,
        "entropy": 0.8,
        "relationship_depth": 0.42,
        "trust_level": 0.51,
        "emotional_valence": 0.12,
        "pending_foresight": 0.05,
    }
    assert agent._last_critic is context
    assert frustration_delta == {"connection": 0.1, "play": -0.2}
    assert drive_satisfaction == {"connection": 0.9, "play": 0.1}


async def test_critic_context_mixin_uses_unknown_mbti_and_omits_empty_tags(
    monkeypatch,
):
    persona = SimpleNamespace(name="Kai", mbti="", tags=[])
    agent, module = make_agent(persona=persona)
    hints: list[str] = []

    async def fake_critic_sense(
        user_message,
        llm,
        frust_dict,
        *,
        user_profile,
        episode_summary,
        persona_hint,
    ):
        hints.append(persona_hint)
        return ({}, {}, {}, {})

    monkeypatch.setattr(module, "critic_sense", fake_critic_sense)

    await agent._sense_critic_context("hello", {})

    assert hints == ["Kai (未知)"]


def test_chat_agent_delegates_critic_context_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.critic_context import AgentCriticContextMixin" in source
    assert "AgentCriticContextMixin" in source
    assert "from engine.genome.critic import critic_sense" not in source
    assert "critic_sense(" not in source
    assert "_persona_hint" not in source
    assert "frust_dict = {d: round(self.metabolism.frustration[d], 2)" not in source
