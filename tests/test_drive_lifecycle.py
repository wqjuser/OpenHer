from pathlib import Path
import importlib
import importlib.util
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class FakeGenomeAgent:
    def __init__(self):
        self.drive_baseline = {
            "connection": 0.5,
            "novelty": 0.94,
            "expression": 0.12,
            "safety": 0.5,
            "play": 0.5,
        }


class FakeStyleMemory:
    def __init__(self):
        self.clock = None
        self.crystallized = []

    def set_clock(self, now):
        self.clock = now

    def crystallize(self, context, monologue, reply, user_input):
        self.crystallized.append((context, monologue, reply, user_input))


def make_agent():
    spec = importlib.util.find_spec("agent.drive_lifecycle")
    assert spec is not None
    module = importlib.import_module("agent.drive_lifecycle")

    class DummyAgent(module.AgentDriveLifecycleMixin):
        def __init__(self):
            self.agent = FakeGenomeAgent()
            self._initial_baseline = {
                "connection": 0.4,
                "novelty": 0.5,
                "expression": 0.5,
                "safety": 0.5,
                "play": 0.5,
            }
            self.baseline_lr = 0.1
            self.elasticity = 0.2
            self.style_memory = FakeStyleMemory()
            self._last_action: dict[str, Any] | None = None
            self.should_crystallize: bool = False

        def _should_crystallize(self, reward, context):
            return self.should_crystallize

    return DummyAgent()


def test_drive_lifecycle_mixin_evolves_and_clamps_baseline():
    agent = make_agent()

    agent._evolve_drive_baseline(
        {
            "connection": 0.3,
            "novelty": 1.0,
            "expression": -1.0,
        }
    )

    assert agent.agent.drive_baseline == {
        "connection": 0.51,
        "novelty": 0.95,
        "expression": 0.1,
        "safety": 0.5,
        "play": 0.5,
    }


def test_drive_lifecycle_mixin_crystallizes_last_action_when_gate_allows():
    agent = make_agent()
    context = {"novelty_level": 0.9}
    agent._last_action = {
        "context": {"old": 1},
        "monologue": "thinking",
        "reply": "hello",
        "user_input": "hi",
    }
    agent.should_crystallize = True

    did_crystallize = agent._crystallize_last_action_if_needed(
        reward=0.9,
        context=context,
        now=123.0,
    )

    assert did_crystallize is True
    assert agent.style_memory.clock == 123.0
    assert agent.style_memory.crystallized == [
        ({"old": 1}, "thinking", "hello", "hi")
    ]


def test_drive_lifecycle_mixin_skips_crystallization_without_last_action_or_gate():
    agent = make_agent()

    assert agent._crystallize_last_action_if_needed(0.9, {}, 1.0) is False
    assert agent.style_memory.crystallized == []

    agent._last_action = {
        "context": {},
        "monologue": "thinking",
        "reply": "hello",
        "user_input": "hi",
    }
    agent.should_crystallize = False

    assert agent._crystallize_last_action_if_needed(0.9, {}, 2.0) is False
    assert agent.style_memory.crystallized == []


def test_chat_agent_delegates_drive_lifecycle_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.drive_lifecycle import AgentDriveLifecycleMixin" in source
    assert "AgentDriveLifecycleMixin" in source
    assert "shift = frustration_delta.get" not in source
    assert "self.style_memory.crystallize(" not in source
