"""Session agent factory boundary tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast, get_type_hints

import pytest


ROOT = Path(__file__).resolve().parents[1]


class FakePersona:
    persona_id = "luna"
    name = "Luna"


class FakePersonaLoader:
    def __init__(self):
        self.personas = {"luna": FakePersona()}
        self.get_calls: list[str] = []

    def get(self, persona_id: str) -> Any:
        self.get_calls.append(persona_id)
        return self.personas.get(persona_id)


class FakeStateStore:
    def __init__(
        self,
        saved_agent: Any = None,
        saved_metabolism: Any = None,
        proactive_meta: tuple[float, float, int] = (0.0, 0.0, 0),
    ):
        self.saved_agent = saved_agent
        self.saved_metabolism = saved_metabolism
        self.proactive_meta = proactive_meta
        self.load_session_calls: list[tuple[str, str]] = []
        self.load_meta_calls: list[tuple[str, str]] = []

    def load_session(self, user_id: str, persona_id: str) -> tuple[Any, Any]:
        self.load_session_calls.append((user_id, persona_id))
        return self.saved_agent, self.saved_metabolism

    def load_proactive_meta(self, user_id: str, persona_id: str) -> tuple[float, float, int]:
        self.load_meta_calls.append((user_id, persona_id))
        return self.proactive_meta


class FakeAgent:
    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs
        self.persona = kwargs["persona"]
        self.user_id = kwargs["user_id"]
        self.user_name = kwargs["user_name"]
        self.agent = "fresh-agent-state"
        self.metabolism = "fresh-metabolism"
        self._client_id = None
        self._last_active = 0.0
        self._interaction_cadence = 0.0
        self._state_version = 0
        self.pre_warm_count = 0

    def pre_warm(self) -> None:
        self.pre_warm_count += 1


class SavedAgent:
    age = 7
    interaction_count = 11


class SavedMetabolism:
    def total(self) -> float:
        return 2.5


def build_factory(*, state_store: Any = None) -> Any:
    from server.session_agent_factory import SessionAgentFactory

    return SessionAgentFactory(
        persona_loader=cast(Any, FakePersonaLoader()),
        llm_client=cast(Any, "llm-client"),
        task_skill_engine=cast(Any, "task-engine"),
        modality_skill_engine=cast(Any, "modality-engine"),
        memory_store=cast(Any, "memory-store"),
        state_store=state_store,
        evermemos=cast(Any, "evermemos-client"),
        genome_data_dir="/tmp/openher-genome",
        agent_factory=FakeAgent,
    )


def test_factory_creates_new_agent_with_stable_session_identity_and_pre_warm():
    state_store = FakeStateStore()
    factory = build_factory(state_store=state_store)

    agent = factory.create(
        session_id="sid-1",
        persona_id="luna",
        user_name=None,
        client_id="client-1",
    )

    assert isinstance(agent, FakeAgent)
    assert agent.persona.persona_id == "luna"
    assert agent.user_id == "sid-1"
    assert agent.user_name is None
    assert agent._client_id == "client-1"
    assert agent.pre_warm_count == 1
    assert agent.kwargs["llm"] == "llm-client"
    assert agent.kwargs["task_skill_engine"] == "task-engine"
    assert agent.kwargs["modality_skill_engine"] == "modality-engine"
    assert agent.kwargs["memory_store"] == "memory-store"
    assert agent.kwargs["genome_seed"] == hash("luna") % 100000
    assert agent.kwargs["genome_data_dir"] == "/tmp/openher-genome"
    assert agent.kwargs["evermemos"] == "evermemos-client"
    assert state_store.load_session_calls == [("sid-1", "luna")]
    assert state_store.load_meta_calls == [("sid-1", "luna")]


def test_factory_hydrates_saved_agent_state_and_skips_pre_warm():
    saved_agent = SavedAgent()
    saved_metabolism = SavedMetabolism()
    state_store = FakeStateStore(
        saved_agent=saved_agent,
        saved_metabolism=saved_metabolism,
        proactive_meta=(123.0, 45.0, 6),
    )
    factory = build_factory(state_store=state_store)

    agent = factory.create(
        session_id="sid-1",
        persona_id="luna",
        user_name="Codex",
        client_id="client-1",
    )

    assert agent.user_id == "Codex"
    assert agent.agent is saved_agent
    assert agent.metabolism is saved_metabolism
    assert agent._last_active == 123.0
    assert agent._interaction_cadence == 45.0
    assert agent._state_version == 6
    assert agent.pre_warm_count == 0
    assert state_store.load_session_calls == [("Codex", "luna")]
    assert state_store.load_meta_calls == [("Codex", "luna")]


def test_factory_raises_for_missing_persona():
    factory = build_factory(state_store=None)

    with pytest.raises(ValueError, match="角色 'missing' 不存在"):
        factory.create(
            session_id="sid-1",
            persona_id="missing",
            user_name=None,
            client_id=None,
        )


def test_session_manager_delegates_agent_creation_to_factory():
    session_source = (ROOT / "server" / "session_manager.py").read_text(encoding="utf-8")

    assert "from server.session_agent_factory import SessionAgentFactory" in session_source
    assert "from agent.chat_agent import ChatAgent" not in session_source
    assert "ChatAgent(" not in session_source
    assert ".pre_warm(" not in session_source
    assert ".load_session(" not in session_source
    assert "self.agent_factory.create(" in session_source


def test_bootstrap_wires_session_agent_factory_before_session_manager():
    bootstrap_source = (ROOT / "server" / "bootstrap.py").read_text(encoding="utf-8")

    assert "from server.session_agent_factory import SessionAgentFactory" in bootstrap_source
    assert "context.session_agent_factory = SessionAgentFactory(" in bootstrap_source
    assert "agent_factory=context.session_agent_factory" in bootstrap_source
    assert '"session_agent_factory": context.session_agent_factory' in bootstrap_source


def test_app_context_exposes_typed_session_agent_factory():
    from server.context import AppContext

    hints = get_type_hints(AppContext)

    assert hints["session_agent_factory"].__args__[0].__name__ == "SessionAgentFactory"
