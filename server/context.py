"""Runtime service container for the FastAPI application."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from fastapi import Request, WebSocket

from agent.cron_scheduler import CronScheduler
from agent.skills import ModalitySkillEngine, TaskSkillEngine
from engine.chat_log_store import ChatLogStore
from engine.state_store import StateStore
from memory.memory_store import MemoryStore
from providers.llm import LLMClient
from providers.media.tts_engine import TTSResult
from providers.memory.evermemos.evermemos_client import EverMemOSClient
from server.chat_api_service import ChatApiService
from server.demo_inject import DemoInjectService
from server.media_api_service import MediaApiService
from server.persona_api_service import PersonaApiService
from server.proactive_service import ProactiveService
from server.session_manager import SessionManager
from server.websocket_chat import WebSocketChatTurnService
from server.websocket_demo import WebSocketDemoCommandService, WebSocketDemoProactiveService
from server.websocket_persona_switch import WebSocketPersonaSwitchService
from server.websocket_registry import WebSocketConnectionRegistry
from server.websocket_route_service import WebSocketRouteService
from server.ws_tts import WebSocketTTSService


class PersonaLoaderService(Protocol):
    def load_all(self) -> dict[str, Any]: ...
    def get(self, persona_id: str) -> Any: ...
    def list_ids(self) -> list[str]: ...


class TTSEngineService(Protocol):
    async def synthesize(
        self,
        *,
        text: str,
        voice_preset: str = "sweet_female",
        emotion_instruction: Optional[str] = None,
    ) -> TTSResult: ...


class SessionManagerService(Protocol):
    def get_or_create(
        self,
        session_id: Optional[str],
        persona_id: str,
        user_name: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> tuple[str, Any]: ...
    def get_entry(self, session_id: str) -> tuple[Any, float] | None: ...
    def persist_agent(self, agent: Any) -> None: ...
    def persist_all(self) -> None: ...
    def remove(self, session_id: str) -> None: ...
    def cleanup_expired_sessions(self) -> int: ...
    def active_agents(self) -> list[Any]: ...
    @property
    def active_count(self) -> int: ...


@dataclass
class AppContext:
    """Holds process-wide OpenHer services for route handlers and lifespan."""

    persona_loader: PersonaLoaderService | None = None
    llm_client: LLMClient | None = None
    tts_engine: TTSEngineService | None = None
    task_skill_engine: TaskSkillEngine | None = None
    modality_skill_engine: ModalitySkillEngine | None = None
    state_store: StateStore | None = None
    chat_log_store: ChatLogStore | None = None
    memory_store: MemoryStore | None = None
    evermemos: EverMemOSClient | None = None
    cron_scheduler: CronScheduler | None = None
    session_manager: SessionManagerService | None = None
    chat_api_service: ChatApiService | None = None
    media_api_service: MediaApiService | None = None
    persona_api_service: PersonaApiService | None = None
    proactive_service: ProactiveService | None = None
    proactive_task: asyncio.Task[None] | None = None
    ws_registry: WebSocketConnectionRegistry = field(default_factory=WebSocketConnectionRegistry)
    demo_inject_service: DemoInjectService = field(init=False)
    ws_demo_proactive_service: WebSocketDemoProactiveService = field(
        default_factory=WebSocketDemoProactiveService
    )
    ws_demo_command_service: WebSocketDemoCommandService | None = None
    ws_route_service: WebSocketRouteService | None = None
    ws_chat_turn_service: WebSocketChatTurnService | None = None
    persona_switch_service: WebSocketPersonaSwitchService | None = None
    ws_tts_service: WebSocketTTSService | None = None
    genome_data_dir: str = ""

    def __post_init__(self) -> None:
        self.demo_inject_service = DemoInjectService(self.ws_registry)


def context_from_request(request: Request) -> AppContext:
    return request.app.state.openher


def context_from_websocket(websocket: WebSocket) -> AppContext:
    return websocket.app.state.openher
