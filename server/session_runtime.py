"""Session and WebSocket runtime service assembly for OpenHer startup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from server.chat_api_service import ChatApiService
from server.session_agent_factory import SessionAgentFactory
from server.session_manager import SessionManager
from server.websocket_chat import WebSocketChatTurnService
from server.websocket_demo import WebSocketDemoCommandService
from server.websocket_persona_switch import WebSocketPersonaSwitchService
from server.websocket_route_service import WebSocketRouteService


GetOrCreateSession = Callable[[Optional[str], str, Optional[str], Optional[str]], tuple[str, Any]]
RemoveSession = Callable[[str], None]
ServiceFactory = Callable[..., Any]


@dataclass(frozen=True)
class SessionRuntimeServices:
    session_agent_factory: SessionAgentFactory | None
    session_manager: SessionManager | None
    chat_api_service: ChatApiService
    persona_switch_service: WebSocketPersonaSwitchService | None
    ws_chat_turn_service: WebSocketChatTurnService | None
    ws_demo_command_service: WebSocketDemoCommandService | None
    ws_route_service: WebSocketRouteService


def build_session_runtime_services(
    *,
    base_dir: Path,
    llm_client: Any | None,
    persona_loader: Any,
    task_skill_engine: Any,
    modality_skill_engine: Any,
    memory_store: Any,
    state_store: Any,
    evermemos: Any | None,
    genome_data_dir: str,
    chat_log_store: Any,
    ws_registry: Any,
    ws_tts_service: Any | None,
    ws_demo_proactive_service: Any,
    get_or_create_session: GetOrCreateSession,
    remove_session: RemoveSession,
    session_ttl_seconds: int,
    session_agent_factory_factory: ServiceFactory = SessionAgentFactory,
    session_manager_factory: ServiceFactory = SessionManager,
    chat_api_service_factory: ServiceFactory = ChatApiService,
    persona_switch_service_factory: ServiceFactory = WebSocketPersonaSwitchService,
    ws_chat_turn_service_factory: ServiceFactory = WebSocketChatTurnService,
    ws_demo_command_service_factory: ServiceFactory = WebSocketDemoCommandService,
    ws_route_service_factory: ServiceFactory = WebSocketRouteService,
) -> SessionRuntimeServices:
    session_agent_factory = None
    session_manager = None
    persona_switch_service = None
    ws_chat_turn_service = None
    ws_demo_command_service = None

    if llm_client:
        session_agent_factory = session_agent_factory_factory(
            persona_loader=persona_loader,
            llm_client=llm_client,
            task_skill_engine=task_skill_engine,
            modality_skill_engine=modality_skill_engine,
            memory_store=memory_store,
            state_store=state_store,
            evermemos=evermemos,
            genome_data_dir=genome_data_dir,
        )
        session_manager = session_manager_factory(
            agent_factory=session_agent_factory,
            state_store=state_store,
            evermemos=evermemos,
            ttl_seconds=session_ttl_seconds,
        )
        chat_api_service = chat_api_service_factory(
            session_manager=session_manager,
            chat_log_store=chat_log_store,
        )
        persona_switch_service = persona_switch_service_factory(
            registry=ws_registry,
            get_or_create_session=get_or_create_session,
            remove_session=remove_session,
        )
        ws_chat_turn_service = ws_chat_turn_service_factory(
            registry=ws_registry,
            get_or_create_session=get_or_create_session,
            chat_log_store=chat_log_store,
        )
        ws_demo_command_service = ws_demo_command_service_factory(
            get_or_create_session=get_or_create_session,
            presets_file=str(Path(base_dir) / "demo" / "presets" / "showcase.yaml"),
            proactive_delivery=ws_demo_proactive_service,
        )
    else:
        chat_api_service = chat_api_service_factory(
            session_manager=None,
            chat_log_store=chat_log_store,
        )

    ws_route_service = ws_route_service_factory(
        registry=ws_registry,
        session_manager=session_manager,
        chat_turn_service=ws_chat_turn_service,
        tts_service=ws_tts_service,
        persona_switch_service=persona_switch_service,
        demo_command_service=ws_demo_command_service,
    )

    return SessionRuntimeServices(
        session_agent_factory=session_agent_factory,
        session_manager=session_manager,
        chat_api_service=chat_api_service,
        persona_switch_service=persona_switch_service,
        ws_chat_turn_service=ws_chat_turn_service,
        ws_demo_command_service=ws_demo_command_service,
        ws_route_service=ws_route_service,
    )
