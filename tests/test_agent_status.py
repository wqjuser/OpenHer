from pathlib import Path
from types import SimpleNamespace
import importlib
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
DRIVES = ["connection", "novelty", "expression", "safety", "play"]


class FakeGenomeAgent:
    def __init__(self):
        self.drive_baseline = {drive: 0.1234 for drive in DRIVES}
        self.drive_state = {drive: 0.5678 for drive in DRIVES}
        self.age = 12
        self._last_input = [0.11111] * 25
        self._last_hidden = [0.22222] * 24
        self._last_phase_transition = True

    def get_dominant_drive(self):
        return "connection"


class FakeMetabolism:
    def __init__(self):
        self.frustration = {drive: 0.33333 for drive in DRIVES}

    def status_summary(self):
        return {"temperature": 0.456, "total": 1.234}

    def total(self):
        return 1.23456

    def temperature(self):
        return 0.45678


class FakeStyleMemory:
    def stats(self):
        return {"total": 7, "personal_count": 2}

    def last_recall_info(self):
        return [{"memory": "recent"}]


def make_agent():
    spec = importlib.util.find_spec("agent.status")
    assert spec is not None
    module = importlib.import_module("agent.status")

    class DummyAgent(module.AgentStatusMixin):
        def __init__(self):
            self.persona = SimpleNamespace(name="Luna")
            self.agent = FakeGenomeAgent()
            self.metabolism = FakeMetabolism()
            self.style_memory = FakeStyleMemory()
            self.history = [object(), object(), object()]
            self._last_signals = {
                "warmth": 0.9,
                "defiance": 0.1,
                "depth": 0.51,
                "playfulness": 0.5,
            }
            self._last_drive_satisfaction = {"connection": 0.1234}
            self._turn_count = 4
            self._last_reward = -0.456
            self._last_modality = "文字"
            self._relationship_ema = {
                "relationship_depth": 0.2345,
                "trust_level": 0.3456,
                "emotional_valence": -0.4567,
            }
            self.evermemos = SimpleNamespace(available=True)
            self._search_hit = 2
            self._search_timeout = 1
            self._search_fallback = 1
            self._search_relevant_used = 3
            self._skill_outputs = {"image_path": "/tmp/a.png"}
            self._last_critic = {
                "conversation_depth": 0.33333,
                "topic_intimacy": 0.44444,
            }
            self._last_action = {"monologue": "thinking deeply about this turn"}

    return DummyAgent()


def test_agent_status_mixin_reports_runtime_status():
    status = make_agent().get_status()

    assert status["persona"] == "Luna"
    assert status["dominant_drive"] == "🔗 联结"
    assert status["drive_baseline"]["connection"] == 0.123
    assert status["drive_state"]["connection"] == 0.568
    assert status["drive_satisfaction"] == {"connection": 0.123}
    assert status["signals"] == {"warmth": 0.9, "defiance": 0.1, "depth": 0.51}
    assert status["temperature"] == 0.456
    assert status["frustration"] == 1.234
    assert status["history_length"] == 3
    assert status["memory_count"] == 7
    assert status["personal_memories"] == 2
    assert status["last_reward"] == -0.46
    assert status["relationship"] == {
        "depth": 0.234,
        "trust": 0.346,
        "valence": -0.457,
    }
    assert status["evermemos"] == "ON"
    assert status["search_hit_rate"] == 0.667
    assert status["search_timeout_rate"] == 0.333
    assert status["fallback_rate"] == 0.25
    assert status["relevant_injection_ratio"] == 0.75
    assert status["image_path"] == "/tmp/a.png"


def test_agent_status_mixin_reports_debug_status():
    debug = make_agent().get_debug_status()

    assert debug["context_vector"] == {
        "conversation_depth": 0.3333,
        "topic_intimacy": 0.4444,
    }
    assert debug["signals"] == {
        "warmth": 0.9,
        "defiance": 0.1,
        "depth": 0.51,
        "playfulness": 0.5,
    }
    assert len(debug["hidden_activations"]) == 24
    assert debug["hidden_activations"][0] == 0.2222
    assert len(debug["input_vector"]) == 25
    assert debug["drive_state"]["connection"] == 0.5678
    assert debug["drive_baseline"]["connection"] == 0.1234
    assert debug["frustration"]["connection"] == 0.3333
    assert debug["total_frustration"] == 1.2346
    assert debug["temperature"] == 0.4568
    assert debug["monologue"] == "thinking deeply about this turn"
    assert debug["style_recall"] == [{"memory": "recent"}]
    assert debug["relationship"] == {
        "depth": 0.2345,
        "trust": 0.3456,
        "valence": -0.4567,
    }
    assert debug["reward"] == -0.456
    assert debug["age"] == 12
    assert debug["turn_count"] == 4
    assert debug["phase_transition"] is True


def test_chat_agent_delegates_status_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.status import AgentStatusMixin" in source
    assert "AgentStatusMixin" in source
    assert "def get_status(" not in source
    assert "def get_debug_status(" not in source
    assert "DRIVE_LABELS" not in source
