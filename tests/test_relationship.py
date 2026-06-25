from pathlib import Path
import importlib
import importlib.util


ROOT = Path(__file__).resolve().parents[1]


def make_agent():
    spec = importlib.util.find_spec("agent.relationship")
    assert spec is not None
    module = importlib.import_module("agent.relationship")

    class DummyAgent(module.AgentRelationshipMixin):
        def __init__(self):
            self._relationship_ema = {}

    return DummyAgent()


def test_relationship_mixin_initializes_prior_and_applies_depth_weighted_delta():
    agent = make_agent()

    status = agent._apply_relationship_ema(
        {
            "relationship_depth": 0.2,
            "emotional_valence": 0.1,
            "trust_level": 0.3,
            "pending_foresight": 0.6,
        },
        {
            "relationship_delta": 0.4,
            "emotional_valence": -0.3,
            "trust_delta": 0.2,
        },
        conversation_depth=0.4,
    )

    assert status == {
        "relationship_depth": 0.34,
        "emotional_valence": -0.005,
        "trust_level": 0.37,
        "pending_foresight": 0.6,
    }
    assert agent._relationship_ema == status


def test_relationship_mixin_clips_and_smooths_existing_state():
    agent = make_agent()
    agent._relationship_ema = {
        "relationship_depth": 0.8,
        "emotional_valence": -0.8,
        "trust_level": 0.1,
        "pending_foresight": 0.2,
    }

    status = agent._apply_relationship_ema(
        {
            "relationship_depth": 0.9,
            "emotional_valence": -0.9,
            "trust_level": 0.9,
            "pending_foresight": 1.0,
        },
        {
            "relationship_delta": 0.5,
            "emotional_valence": -0.5,
            "trust_delta": 0.5,
        },
        conversation_depth=2.0,
    )

    assert status == {
        "relationship_depth": 0.93,
        "emotional_valence": -0.93,
        "trust_level": 0.685,
        "pending_foresight": 0.72,
    }


def test_chat_agent_delegates_relationship_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")
    evermemos_source = (ROOT / "agent/evermemos_mixin.py").read_text(encoding="utf-8")

    assert "from agent.relationship import AgentRelationshipMixin" in source
    assert "AgentRelationshipMixin" in source
    assert "def _apply_relationship_ema(" not in evermemos_source
