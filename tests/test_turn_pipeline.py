from __future__ import annotations

from pathlib import Path
import importlib
import importlib.util
from typing import Any

from providers.llm.client import ChatMessage


ROOT = Path(__file__).resolve().parents[1]


class FakeMetabolism:
    def __init__(self, calls: list[str]):
        self.calls = calls

    def time_metabolism(self, now: float) -> float:
        self.calls.append(f"time_metabolism:{now}")
        return 0.25

    def apply_llm_delta(self, frustration_delta: dict[str, float]) -> float:
        self.calls.append(f"apply_llm_delta:{frustration_delta}")
        return 0.37

    def sync_to_agent(self, agent: object) -> None:
        self.calls.append(f"sync_to_agent:{agent!r}")


def make_agent():
    spec = importlib.util.find_spec("agent.turn_pipeline")
    assert spec is not None
    module = importlib.import_module("agent.turn_pipeline")

    class DummyAgent(module.AgentTurnPipelineMixin):
        def __init__(self):
            self.calls: list[str] = []
            self.metabolism = FakeMetabolism(self.calls)
            self.agent = object()
            self._last_reward = 0.0
            self.relationship_prior = {"relationship_depth": 0.2}
            self.context = {"conversation_depth": 0.6}
            self.frustration_delta = {"connection": 0.2}
            self.drive_satisfaction = {"connection": 0.8}
            self.actor_messages = [
                ChatMessage(role="system", content="prompt"),
                ChatMessage(role="user", content="skilled hello"),
            ]

        async def _run_task_skills(self, user_message: str) -> str:
            self.calls.append(f"task_skills:{user_message}")
            return f"skilled {user_message}"

        def _begin_turn(self) -> float:
            self.calls.append("begin_turn")
            return 123.0

        async def _evermemos_gather(self) -> dict[str, float]:
            self.calls.append("evermemos_gather")
            return self.relationship_prior

        async def _sense_critic_context(
            self,
            user_message: str,
            relationship_prior: dict[str, float],
        ) -> tuple[dict[str, Any], dict[str, float], dict[str, float]]:
            self.calls.append(f"critic:{user_message}:{relationship_prior}")
            return self.context, self.frustration_delta, self.drive_satisfaction

        def _evolve_drive_baseline(self, frustration_delta: dict[str, float]) -> None:
            self.calls.append(f"drive_baseline:{frustration_delta}")

        def _crystallize_last_action_if_needed(
            self,
            reward: float,
            context: dict[str, Any],
            now: float,
        ) -> bool:
            self.calls.append(f"crystallize:{reward}:{context}:{now}")
            return True

        async def _prepare_actor_messages(
            self,
            user_message: str,
            context: dict[str, Any],
            now: float,
        ) -> list[ChatMessage]:
            self.calls.append(f"actor_messages:{user_message}:{context}:{now}")
            return self.actor_messages

    return DummyAgent(), module


async def test_turn_pipeline_prepares_shared_lifecycle_in_order():
    agent, _module = make_agent()

    prepared = await agent._prepare_turn_for_actor("hello")

    assert agent.calls == [
        "task_skills:hello",
        "begin_turn",
        "evermemos_gather",
        "time_metabolism:123.0",
        "critic:skilled hello:{'relationship_depth': 0.2}",
        "apply_llm_delta:{'connection': 0.2}",
        f"sync_to_agent:{agent.agent!r}",
        "drive_baseline:{'connection': 0.2}",
        "crystallize:0.37:{'conversation_depth': 0.6}:123.0",
        "actor_messages:skilled hello:{'conversation_depth': 0.6}:123.0",
    ]
    assert prepared.user_message == "skilled hello"
    assert prepared.now == 123.0
    assert prepared.context is agent.context
    assert prepared.frustration_delta is agent.frustration_delta
    assert prepared.drive_satisfaction is agent.drive_satisfaction
    assert prepared.reward == 0.37
    assert prepared.actor_messages is agent.actor_messages
    assert agent._last_reward == 0.37


def test_prepared_turn_dataclass_exports_expected_fields():
    _agent, module = make_agent()

    prepared = module.PreparedTurn(
        user_message="hello",
        now=1.0,
        context={"entropy": 0.5},
        frustration_delta={"play": 0.1},
        drive_satisfaction={"play": 0.9},
        reward=0.4,
        actor_messages=[ChatMessage(role="user", content="hello")],
    )

    assert prepared.user_message == "hello"
    assert prepared.now == 1.0
    assert prepared.context == {"entropy": 0.5}
    assert prepared.frustration_delta == {"play": 0.1}
    assert prepared.drive_satisfaction == {"play": 0.9}
    assert prepared.reward == 0.4
    assert [(msg.role, msg.content) for msg in prepared.actor_messages] == [
        ("user", "hello")
    ]


def test_chat_agent_delegates_turn_pipeline_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.turn_pipeline import AgentTurnPipelineMixin" in source
    assert "AgentTurnPipelineMixin" in source
    assert source.count("_prepare_turn_for_actor(") == 2
    assert "self._run_task_skills(" not in source
    assert "self._begin_turn()" not in source
    assert "self._evermemos_gather()" not in source
    assert "self._sense_critic_context(" not in source
    assert "self.metabolism.apply_llm_delta(" not in source
    assert "self.metabolism.sync_to_agent(" not in source
    assert "self._evolve_drive_baseline(" not in source
    assert "self._crystallize_last_action_if_needed(" not in source
    assert "self._prepare_actor_messages(" not in source
