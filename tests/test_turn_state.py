from pathlib import Path
import importlib
import importlib.util


ROOT = Path(__file__).resolve().parents[1]


def make_agent(last_active=100.0, cadence=0.0, turn_count=2):
    spec = importlib.util.find_spec("agent.turn_state")
    assert spec is not None
    module = importlib.import_module("agent.turn_state")

    class DummyAgent(module.AgentTurnStateMixin):
        def __init__(self):
            self._turn_count = turn_count
            self._turn_used_fallback = True
            self._last_active = last_active
            self._interaction_cadence = cadence

    return DummyAgent()


def test_turn_state_mixin_starts_turn_and_initializes_cadence():
    agent = make_agent(last_active=100.0, cadence=0.0, turn_count=2)

    now = agent._begin_turn(now=112.0)

    assert now == 112.0
    assert agent._turn_count == 3
    assert agent._turn_used_fallback is False
    assert agent._interaction_cadence == 12.0
    assert agent._last_active == 112.0


def test_turn_state_mixin_smooths_existing_cadence():
    agent = make_agent(last_active=100.0, cadence=10.0, turn_count=4)

    now = agent._begin_turn(now=130.0)

    assert now == 130.0
    assert agent._turn_count == 5
    assert agent._interaction_cadence == 16.0
    assert agent._last_active == 130.0


def test_turn_state_mixin_handles_missing_last_active_without_touching_cadence():
    agent = make_agent(last_active=0.0, cadence=9.0, turn_count=0)

    now = agent._begin_turn(now=50.0)

    assert now == 50.0
    assert agent._turn_count == 1
    assert agent._turn_used_fallback is False
    assert agent._interaction_cadence == 9.0
    assert agent._last_active == 50.0


def test_chat_agent_delegates_turn_state_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.turn_state import AgentTurnStateMixin" in source
    assert "AgentTurnStateMixin" in source
    assert "self._turn_count += 1" not in source
    assert "self._interaction_cadence = 0.3" not in source
