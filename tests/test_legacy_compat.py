"""Legacy compatibility boundary tests."""

from __future__ import annotations

from typing import Any, cast

import pytest


def test_initial_legacy_globals_seed_defaults_and_context_bound_aliases():
    from server.context import AppContext
    from server.legacy_compat import initial_legacy_globals

    context = AppContext()

    values = initial_legacy_globals(context)

    for key in (
        "persona_loader",
        "llm_client",
        "tts_engine",
        "task_skill_engine",
        "modality_skill_engine",
        "state_store",
        "chat_log_store",
        "memory_store",
        "evermemos",
        "cron_scheduler",
        "session_agent_factory",
        "session_manager",
        "chat_api_service",
        "media_api_service",
        "persona_api_service",
        "proactive_service",
        "ws_demo_command_service",
        "ws_route_service",
        "ws_chat_turn_service",
        "persona_switch_service",
        "ws_tts_service",
        "_proactive_task",
    ):
        assert values[key] is None

    assert values["ws_registry"] is context.ws_registry
    assert values["demo_inject_service"] is context.demo_inject_service
    assert values["ws_demo_proactive_service"] is context.ws_demo_proactive_service
    assert values["genome_data_dir"] == ""


def test_sync_legacy_globals_exposes_runtime_services():
    from server.context import AppContext
    from server.legacy_compat import sync_legacy_globals

    context = AppContext()
    service_values: dict[str, Any] = {
        "persona_loader": object(),
        "llm_client": object(),
        "tts_engine": object(),
        "task_skill_engine": object(),
        "modality_skill_engine": object(),
        "state_store": object(),
        "chat_log_store": object(),
        "memory_store": object(),
        "evermemos": object(),
        "cron_scheduler": object(),
        "session_agent_factory": object(),
        "session_manager": object(),
        "chat_api_service": object(),
        "media_api_service": object(),
        "persona_api_service": object(),
        "proactive_service": object(),
        "ws_demo_command_service": object(),
        "ws_route_service": object(),
        "ws_chat_turn_service": object(),
        "persona_switch_service": object(),
        "ws_tts_service": object(),
        "proactive_task": object(),
    }
    for name, value in service_values.items():
        setattr(context, name, cast(Any, value))
    context.genome_data_dir = "/tmp/genome"

    module_globals: dict[str, object] = {}
    sync_legacy_globals(context, module_globals)

    for name, value in service_values.items():
        exposed_name = "_proactive_task" if name == "proactive_task" else name
        assert module_globals[exposed_name] is value
    assert module_globals["ws_registry"] is context.ws_registry
    assert module_globals["demo_inject_service"] is context.demo_inject_service
    assert module_globals["ws_demo_proactive_service"] is context.ws_demo_proactive_service
    assert module_globals["genome_data_dir"] == "/tmp/genome"


async def test_legacy_compat_helpers_delegate_to_context_services():
    from server.context import AppContext, SessionManagerService
    from server.legacy_compat import LegacyCompatibility

    events: list[tuple[Any, ...]] = []

    class FakeProactiveService:
        async def heartbeat_loop(self) -> None:
            events.append(("heartbeat",))

        async def sweep(self) -> None:
            events.append(("sweep",))

        async def deliver_message(self, agent: Any, session_id: str, row: dict[str, Any]) -> None:
            events.append(("deliver", agent, session_id, row))

    class FakeSessionManager:
        def persist_agent(self, agent: Any) -> None:
            events.append(("persist", agent))

        def cleanup_expired_sessions(self) -> int:
            events.append(("cleanup",))
            return 3

        def get_or_create(
            self,
            session_id: str | None,
            persona_id: str,
            user_name: str | None = None,
            client_id: str | None = None,
        ) -> tuple[str, Any]:
            events.append(("get_or_create", session_id, persona_id, user_name, client_id))
            return "session-1", "agent-1"

        def remove(self, session_id: str) -> None:
            events.append(("remove", session_id))

    context = AppContext()
    context.proactive_service = cast(Any, FakeProactiveService())
    context.session_manager = cast(SessionManagerService, FakeSessionManager())
    helper = LegacyCompatibility(context)

    await helper.proactive_heartbeat_loop()
    await helper.proactive_sweep()
    await helper.deliver_proactive_msg("agent-0", "session-0", {"tick_id": "tick-1"})
    helper.persist_agent("agent-2")
    assert helper.cleanup_expired_sessions() == 3
    assert helper.get_or_create_session(None, "iris", "Ada", "client-1") == ("session-1", "agent-1")
    helper.remove_session("session-1")

    assert events == [
        ("heartbeat",),
        ("sweep",),
        ("deliver", "agent-0", "session-0", {"tick_id": "tick-1"}),
        ("persist", "agent-2"),
        ("cleanup",),
        ("get_or_create", None, "iris", "Ada", "client-1"),
        ("remove", "session-1"),
    ]


async def test_legacy_compat_helpers_raise_when_required_services_are_missing():
    from server.context import AppContext
    from server.legacy_compat import LegacyCompatibility

    helper = LegacyCompatibility(AppContext())

    with pytest.raises(RuntimeError, match="Session manager is not initialized"):
        helper.get_or_create_session(None, "iris")

    with pytest.raises(RuntimeError, match="Proactive service is not initialized"):
        await helper.deliver_proactive_msg(object(), "session-1", {})
