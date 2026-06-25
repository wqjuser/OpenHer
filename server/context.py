"""Runtime service container for the FastAPI application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Request, WebSocket

from server.demo_inject import DemoInjectService
from server.websocket_demo import WebSocketDemoCommandService, WebSocketDemoProactiveService
from server.websocket_registry import WebSocketConnectionRegistry


@dataclass
class AppContext:
    """Holds process-wide OpenHer services for route handlers and lifespan."""

    persona_loader: Any = None
    llm_client: Any = None
    tts_engine: Any = None
    task_skill_engine: Any = None
    modality_skill_engine: Any = None
    state_store: Any = None
    chat_log_store: Any = None
    memory_store: Any = None
    evermemos: Any = None
    cron_scheduler: Any = None
    session_manager: Any = None
    proactive_service: Any = None
    ws_registry: WebSocketConnectionRegistry = field(default_factory=WebSocketConnectionRegistry)
    demo_inject_service: DemoInjectService = field(init=False)
    ws_demo_proactive_service: WebSocketDemoProactiveService = field(
        default_factory=WebSocketDemoProactiveService
    )
    ws_demo_command_service: WebSocketDemoCommandService | None = None
    ws_chat_turn_service: Any = None
    persona_switch_service: Any = None
    ws_tts_service: Any = None
    genome_data_dir: str = ""

    def __post_init__(self) -> None:
        self.demo_inject_service = DemoInjectService(self.ws_registry)


def context_from_request(request: Request) -> AppContext:
    return request.app.state.openher


def context_from_websocket(websocket: WebSocket) -> AppContext:
    return websocket.app.state.openher
