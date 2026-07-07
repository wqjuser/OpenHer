"""Compatibility bridge for legacy `main.py` globals and helper functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from server.context import AppContext


LEGACY_SERVICE_NAMES: tuple[str, ...] = (
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
)


def initial_legacy_globals(context: AppContext) -> dict[str, object]:
    values: dict[str, object] = {name: None for name in LEGACY_SERVICE_NAMES}
    values.update(
        {
            "ws_registry": context.ws_registry,
            "demo_inject_service": context.demo_inject_service,
            "ws_demo_proactive_service": context.ws_demo_proactive_service,
            "genome_data_dir": "",
            "_proactive_task": None,
        }
    )
    return values


def sync_legacy_globals(context: AppContext, module_globals: dict[str, object]) -> None:
    """Expose context services through legacy `main.py` global names."""
    module_globals.update(
        {
            "persona_loader": context.persona_loader,
            "llm_client": context.llm_client,
            "tts_engine": context.tts_engine,
            "task_skill_engine": context.task_skill_engine,
            "modality_skill_engine": context.modality_skill_engine,
            "state_store": context.state_store,
            "chat_log_store": context.chat_log_store,
            "memory_store": context.memory_store,
            "evermemos": context.evermemos,
            "cron_scheduler": context.cron_scheduler,
            "session_agent_factory": context.session_agent_factory,
            "session_manager": context.session_manager,
            "chat_api_service": context.chat_api_service,
            "media_api_service": context.media_api_service,
            "persona_api_service": context.persona_api_service,
            "proactive_service": context.proactive_service,
            "ws_registry": context.ws_registry,
            "demo_inject_service": context.demo_inject_service,
            "ws_demo_proactive_service": context.ws_demo_proactive_service,
            "ws_demo_command_service": context.ws_demo_command_service,
            "ws_route_service": context.ws_route_service,
            "ws_chat_turn_service": context.ws_chat_turn_service,
            "persona_switch_service": context.persona_switch_service,
            "ws_tts_service": context.ws_tts_service,
            "genome_data_dir": context.genome_data_dir,
            "_proactive_task": context.proactive_task,
        }
    )


@dataclass(frozen=True)
class LegacyCompatibility:
    context: AppContext

    async def proactive_heartbeat_loop(self) -> None:
        """Compatibility wrapper for the proactive service loop."""
        if not self.context.proactive_service:
            return
        await self.context.proactive_service.heartbeat_loop()

    async def proactive_sweep(self) -> None:
        """Compatibility wrapper for one proactive service sweep."""
        if self.context.proactive_service:
            await self.context.proactive_service.sweep()

    async def deliver_proactive_msg(self, agent: Any, session_id: str, row: dict[str, Any]) -> None:
        """Compatibility wrapper for proactive service delivery."""
        if not self.context.proactive_service:
            raise RuntimeError("Proactive service is not initialized")
        await self.context.proactive_service.deliver_message(agent, session_id, row)

    def persist_agent(self, agent: Any) -> None:
        """Compatibility wrapper for session-manager persistence."""
        if self.context.session_manager:
            self.context.session_manager.persist_agent(agent)

    def cleanup_expired_sessions(self) -> int:
        """Compatibility wrapper for session-manager TTL cleanup."""
        return self.context.session_manager.cleanup_expired_sessions() if self.context.session_manager else 0

    def get_or_create_session(
        self,
        session_id: Optional[str],
        persona_id: str,
        user_name: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> tuple[str, Any]:
        """Compatibility wrapper for session-manager get-or-create."""
        if not self.context.session_manager:
            raise RuntimeError("Session manager is not initialized")
        return self.context.session_manager.get_or_create(session_id, persona_id, user_name, client_id)

    def remove_session(self, session_id: str) -> None:
        """Compatibility wrapper for session-manager removal."""
        if self.context.session_manager:
            self.context.session_manager.remove(session_id)
