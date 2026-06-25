from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib
import importlib.util
from typing import Any

from providers.llm.client import ChatMessage


ROOT = Path(__file__).resolve().parents[1]


class FakeGenomeAgent:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def compute_signals(self, context: dict[str, Any]) -> dict[str, float]:
        self.calls.append(context)
        return {"warmth": 0.7, "curiosity": 0.4}


class FakeMetabolism:
    def __init__(self):
        self.calls: list[dict[str, float]] = []

    def apply_thermodynamic_noise(
        self,
        base_signals: dict[str, float],
    ) -> dict[str, float]:
        self.calls.append(base_signals)
        return {"warmth": 0.72, "curiosity": 0.41}


class FakeStyleMemory:
    def __init__(self):
        self.clock = None
        self.calls: list[dict[str, Any]] = []

    def set_clock(self, now: float) -> None:
        self.clock = now

    def build_few_shot_prompt(
        self,
        context: dict[str, Any],
        *,
        top_k: int,
        monologue_only: bool,
        lang: str,
    ) -> str:
        self.calls.append(
            {
                "context": context,
                "top_k": top_k,
                "monologue_only": monologue_only,
                "lang": lang,
            }
        )
        return "few-shot"


def make_agent(max_history: int = 2):
    spec = importlib.util.find_spec("agent.actor_messages")
    assert spec is not None
    module = importlib.import_module("agent.actor_messages")

    class DummyAgent(module.AgentActorMessagesMixin):
        def __init__(self):
            self.agent = FakeGenomeAgent()
            self.metabolism = FakeMetabolism()
            self.style_memory = FakeStyleMemory()
            self.persona = SimpleNamespace(lang="zh")
            self.modality_skill_engine = object()
            self.history = [
                ChatMessage(role="user", content="old-1"),
                ChatMessage(role="assistant", content="old-2"),
                ChatMessage(role="user", content="old-3"),
            ]
            self.max_history = max_history
            self._prev_signals: dict[str, float] | None = {"old": 0.1}
            self._last_signals: dict[str, float] | None = {"previous": 0.2}
            self.build_calls: list[dict[str, Any]] = []
            self.inject_calls: list[dict[str, Any]] = []

        def _build_single_prompt(
            self,
            few_shot: str,
            noisy_signals: dict[str, float],
            *,
            modality_skill_engine: Any,
        ) -> str:
            self.build_calls.append(
                {
                    "few_shot": few_shot,
                    "noisy_signals": noisy_signals,
                    "modality_skill_engine": modality_skill_engine,
                }
            )
            return "actor prompt"

        async def _inject_memory_context(
            self,
            single_prompt: str,
            context: dict[str, Any],
        ) -> str:
            self.inject_calls.append(
                {
                    "single_prompt": single_prompt,
                    "context": context,
                }
            )
            return single_prompt + " + memory"

    return DummyAgent()


async def test_actor_messages_mixin_prepares_prompt_and_updates_signal_state():
    agent = make_agent(max_history=2)
    context = {"entropy": 0.6}

    messages = await agent._prepare_actor_messages(
        "hello",
        context,
        now=123.0,
    )

    assert agent.agent.calls == [context]
    assert agent.metabolism.calls == [{"warmth": 0.7, "curiosity": 0.4}]
    assert agent._prev_signals == {"previous": 0.2}
    assert agent._last_signals == {"warmth": 0.72, "curiosity": 0.41}
    assert agent.style_memory.clock == 123.0
    assert agent.style_memory.calls == [
        {
            "context": context,
            "top_k": 3,
            "monologue_only": False,
            "lang": "zh",
        }
    ]
    assert agent.build_calls == [
        {
            "few_shot": "few-shot",
            "noisy_signals": {"warmth": 0.72, "curiosity": 0.41},
            "modality_skill_engine": agent.modality_skill_engine,
        }
    ]
    assert agent.inject_calls == [
        {
            "single_prompt": "actor prompt",
            "context": context,
        }
    ]
    assert [(msg.role, msg.content) for msg in messages] == [
        ("system", "actor prompt + memory"),
        ("assistant", "old-2"),
        ("user", "old-3"),
        ("user", "hello"),
    ]


async def test_actor_messages_mixin_uses_all_history_when_under_limit():
    agent = make_agent(max_history=10)

    messages = await agent._prepare_actor_messages(
        "now",
        {"conversation_depth": 0.2},
        now=50.0,
    )

    assert [(msg.role, msg.content) for msg in messages] == [
        ("system", "actor prompt + memory"),
        ("user", "old-1"),
        ("assistant", "old-2"),
        ("user", "old-3"),
        ("user", "now"),
    ]


def test_chat_agent_delegates_actor_messages_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.actor_messages import AgentActorMessagesMixin" in source
    assert "AgentActorMessagesMixin" in source
    assert "build_few_shot_prompt(" not in source
    assert "self._build_single_prompt(" not in source
    assert "self._inject_memory_context(single_prompt, context)" not in source
    assert "single_messages = [ChatMessage(role=\"system\"" not in source
