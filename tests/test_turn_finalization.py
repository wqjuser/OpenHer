from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib
import importlib.util
from typing import Any

from providers.llm.client import ChatMessage


ROOT = Path(__file__).resolve().parents[1]


class FakeMemoryStore:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def add(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class FakeMetabolism:
    def temperature(self) -> float:
        return 0.25


def make_agent(max_history: int = 3):
    spec = importlib.util.find_spec("agent.turn_finalization")
    assert spec is not None
    module = importlib.import_module("agent.turn_finalization")

    class DummyAgent(module.AgentTurnFinalizationMixin):
        def __init__(self):
            self.history: list[ChatMessage] = [
                ChatMessage(role="user", content="old-user"),
                ChatMessage(role="assistant", content="old-assistant"),
            ]
            self.max_history = max_history
            self._fallback_history_added = False
            self._last_action: dict[str, Any] | None = None
            self._last_modality = ""
            self.memory_store = FakeMemoryStore()
            self.user_id = "user-1"
            self.persona = SimpleNamespace(persona_id="luna")
            self.metabolism = FakeMetabolism()
            self.store_calls: list[tuple[str, str]] = []
            self.search_calls: list[str] = []

        def _evermemos_store_bg(self, user_message: str, reply: str) -> None:
            self.store_calls.append((user_message, reply))

        def _evermemos_search_bg(self, user_message: str) -> None:
            self.search_calls.append(user_message)

    return DummyAgent()


def test_turn_finalization_updates_history_action_memory_and_evermemos():
    agent = make_agent(max_history=3)
    context = {"entropy": 0.8, "novelty_level": 0.4}

    agent._finalize_turn_response(
        "hello",
        "hi back",
        "thinking",
        "text",
        context,
        {"connection": 0.7},
        0.42,
    )

    assert [(m.role, m.content) for m in agent.history] == [
        ("assistant", "old-assistant"),
        ("user", "hello"),
        ("assistant", "hi back"),
    ]
    assert agent._fallback_history_added is False
    assert agent._last_action == {
        "context": context,
        "monologue": "thinking",
        "reply": "hi back",
        "modality": "text",
        "user_input": "hello",
    }
    assert agent._last_modality == "text"
    assert agent.memory_store.calls == [
        {
            "user_id": "user-1",
            "persona_id": "luna",
            "content": "hello",
            "category": "user_message",
            "importance": 0.8,
        }
    ]
    assert agent.store_calls == [("hello", "hi back")]
    assert agent.search_calls == ["hello"]


def test_turn_finalization_respects_fallback_history_flag():
    agent = make_agent(max_history=10)
    agent._fallback_history_added = True

    agent._finalize_turn_response(
        "hello",
        "fallback already stored",
        "thinking",
        "text",
        {"entropy": 0.2},
        {},
        0.1,
    )

    assert [(m.role, m.content) for m in agent.history] == [
        ("user", "old-user"),
        ("assistant", "old-assistant"),
        ("user", "hello"),
    ]
    assert agent._fallback_history_added is False


def test_turn_finalization_skips_external_memory_for_proactive_turns():
    agent = make_agent(max_history=10)

    agent._finalize_turn_response(
        "check in",
        "I was thinking of you.",
        "gentle proactive thought",
        "text",
        {"entropy": 0.9},
        {},
        0.3,
        is_proactive=True,
    )

    assert [(m.role, m.content) for m in agent.history] == [
        ("user", "old-user"),
        ("assistant", "old-assistant"),
        ("assistant", "I was thinking of you."),
    ]
    assert agent.memory_store.calls == []
    assert agent.store_calls == []
    assert agent.search_calls == []


def test_chat_agent_delegates_turn_finalization_boundary():
    source = (ROOT / "agent/chat_agent.py").read_text(encoding="utf-8")

    assert "from agent.turn_finalization import AgentTurnFinalizationMixin" in source
    assert "AgentTurnFinalizationMixin" in source
    assert "self.history.append(ChatMessage" not in source
    assert "self.memory_store.add(" not in source
    assert "self._evermemos_store_bg(user_message, reply)" not in source
    assert "self._last_action = {" not in source
