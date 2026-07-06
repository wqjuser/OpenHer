"""Session runtime assembly boundary tests."""

from __future__ import annotations

from typing import Any


class FakeService:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_session_runtime_builds_available_session_and_websocket_services(tmp_path):
    from server.session_runtime import build_session_runtime_services

    calls: dict[str, list[dict[str, Any]]] = {
        "agent_factory": [],
        "session_manager": [],
        "chat_api": [],
        "persona_switch": [],
        "ws_chat": [],
        "demo": [],
        "route": [],
    }

    def factory(name: str):
        def _factory(**kwargs: Any) -> FakeService:
            calls[name].append(kwargs)
            return FakeService(**kwargs)

        return _factory

    llm_client = object()
    persona_loader = object()
    task_skill_engine = object()
    modality_skill_engine = object()
    memory_store = object()
    state_store = object()
    evermemos = object()
    chat_log_store = object()
    ws_registry = object()
    ws_tts_service = object()
    ws_demo_proactive_service = object()

    def get_or_create_session(*_args: Any) -> tuple[str, object]:
        return ("sid", object())

    def remove_session(_session_id: str) -> None:
        return None

    runtime = build_session_runtime_services(
        base_dir=tmp_path,
        llm_client=llm_client,
        persona_loader=persona_loader,
        task_skill_engine=task_skill_engine,
        modality_skill_engine=modality_skill_engine,
        memory_store=memory_store,
        state_store=state_store,
        evermemos=evermemos,
        genome_data_dir="/tmp/genome",
        chat_log_store=chat_log_store,
        ws_registry=ws_registry,
        ws_tts_service=ws_tts_service,
        ws_demo_proactive_service=ws_demo_proactive_service,
        get_or_create_session=get_or_create_session,
        remove_session=remove_session,
        session_ttl_seconds=123,
        session_agent_factory_factory=factory("agent_factory"),
        session_manager_factory=factory("session_manager"),
        chat_api_service_factory=factory("chat_api"),
        persona_switch_service_factory=factory("persona_switch"),
        ws_chat_turn_service_factory=factory("ws_chat"),
        ws_demo_command_service_factory=factory("demo"),
        ws_route_service_factory=factory("route"),
    )

    assert calls["agent_factory"][0] == {
        "persona_loader": persona_loader,
        "llm_client": llm_client,
        "task_skill_engine": task_skill_engine,
        "modality_skill_engine": modality_skill_engine,
        "memory_store": memory_store,
        "state_store": state_store,
        "evermemos": evermemos,
        "genome_data_dir": "/tmp/genome",
    }
    assert calls["session_manager"][0]["agent_factory"] is runtime.session_agent_factory
    assert calls["session_manager"][0]["state_store"] is state_store
    assert calls["session_manager"][0]["evermemos"] is evermemos
    assert calls["session_manager"][0]["ttl_seconds"] == 123
    assert calls["chat_api"][0] == {
        "session_manager": runtime.session_manager,
        "chat_log_store": chat_log_store,
    }
    assert calls["persona_switch"][0] == {
        "registry": ws_registry,
        "get_or_create_session": get_or_create_session,
        "remove_session": remove_session,
    }
    assert calls["ws_chat"][0] == {
        "registry": ws_registry,
        "get_or_create_session": get_or_create_session,
        "chat_log_store": chat_log_store,
    }
    assert calls["demo"][0] == {
        "get_or_create_session": get_or_create_session,
        "presets_file": str(tmp_path / "demo" / "presets" / "showcase.yaml"),
        "proactive_delivery": ws_demo_proactive_service,
    }
    assert calls["route"][0] == {
        "registry": ws_registry,
        "session_manager": runtime.session_manager,
        "chat_turn_service": runtime.ws_chat_turn_service,
        "tts_service": ws_tts_service,
        "persona_switch_service": runtime.persona_switch_service,
        "demo_command_service": runtime.ws_demo_command_service,
    }


def test_session_runtime_degrades_when_llm_is_unavailable(tmp_path):
    from server.session_runtime import build_session_runtime_services

    chat_api_calls: list[dict[str, Any]] = []
    route_calls: list[dict[str, Any]] = []

    def forbidden_factory(**_kwargs: Any) -> FakeService:
        raise AssertionError("factory should not be called when llm is unavailable")

    def chat_api_factory(**kwargs: Any) -> FakeService:
        chat_api_calls.append(kwargs)
        return FakeService(**kwargs)

    def route_factory(**kwargs: Any) -> FakeService:
        route_calls.append(kwargs)
        return FakeService(**kwargs)

    ws_registry = object()
    ws_tts_service = object()
    chat_log_store = object()

    runtime = build_session_runtime_services(
        base_dir=tmp_path,
        llm_client=None,
        persona_loader=object(),
        task_skill_engine=object(),
        modality_skill_engine=object(),
        memory_store=object(),
        state_store=object(),
        evermemos=None,
        genome_data_dir="/tmp/genome",
        chat_log_store=chat_log_store,
        ws_registry=ws_registry,
        ws_tts_service=ws_tts_service,
        ws_demo_proactive_service=object(),
        get_or_create_session=lambda *_args: ("sid", object()),
        remove_session=lambda _session_id: None,
        session_ttl_seconds=123,
        session_agent_factory_factory=forbidden_factory,
        session_manager_factory=forbidden_factory,
        chat_api_service_factory=chat_api_factory,
        persona_switch_service_factory=forbidden_factory,
        ws_chat_turn_service_factory=forbidden_factory,
        ws_demo_command_service_factory=forbidden_factory,
        ws_route_service_factory=route_factory,
    )

    assert runtime.session_agent_factory is None
    assert runtime.session_manager is None
    assert runtime.persona_switch_service is None
    assert runtime.ws_chat_turn_service is None
    assert runtime.ws_demo_command_service is None
    assert chat_api_calls == [{"session_manager": None, "chat_log_store": chat_log_store}]
    assert route_calls == [
        {
            "registry": ws_registry,
            "session_manager": None,
            "chat_turn_service": None,
            "tts_service": ws_tts_service,
            "persona_switch_service": None,
            "demo_command_service": None,
        }
    ]
