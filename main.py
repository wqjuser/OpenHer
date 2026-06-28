"""
Gateway — FastAPI WebSocket server for OpenHer (Genome v10 Hybrid).

Provides:
  - WebSocket endpoint for real-time chat with Genome v10 lifecycle
  - REST APIs for persona management, status
  - Agent state persistence (neural network weights + drive metabolism)
  - Session auto-cleanup with TTL
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent.chat_agent import ChatAgent
from server import bootstrap
from server.context import AppContext
from server.media import audio_format_for_path as _audio_format_for_path
from server.media import media_type_for_file as _media_type_for_file
from server.observability import add_request_observability
from server.security import cors_origins_from_env as _cors_origins_from_env
from server.security import request_has_api_token as _request_has_api_token
from server.routes import register_routes

# ──────────────────────────────────────────────────────────────
# Load env
# ──────────────────────────────────────────────────────────────

load_dotenv(override=True)  # override=True: .env values take precedence over shell exports


# ──────────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    context: AppContext = _app.state.openher
    await bootstrap.startup(context)
    bootstrap.sync_legacy_globals(context, globals())
    try:
        yield
    finally:
        await bootstrap.shutdown(context)
        bootstrap.sync_legacy_globals(context, globals())


async def require_api_token(request: Request, call_next):
    """Require a bearer token when OPENHER_API_TOKEN is configured."""
    if request.method == "OPTIONS":
        return await call_next(request)
    if not _request_has_api_token(
        request.headers.get("Authorization"),
        request.query_params.get("token"),
    ):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


def create_app(context: Optional[AppContext] = None) -> FastAPI:
    """Create the FastAPI application and attach its runtime context."""
    server_app = FastAPI(
        title="OpenHer",
        description="AI Companion Server — Genome v10 Hybrid Engine",
        version="0.5.0",
        lifespan=lifespan,
    )
    server_app.state.openher = context or AppContext()
    server_app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins_from_env(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    server_app.middleware("http")(require_api_token)
    server_app.middleware("http")(add_request_observability)
    register_routes(server_app)
    return server_app


openher_context = AppContext()
app = create_app(openher_context)


# ──────────────────────────────────────────────────────────────
# Legacy global service aliases (initialized at startup)
# ──────────────────────────────────────────────────────────────

persona_loader: object | None = None
llm_client: object | None = None
tts_engine: object | None = None
task_skill_engine: object | None = None
modality_skill_engine: object | None = None
state_store: object | None = None
chat_log_store: object | None = None
memory_store: object | None = None
evermemos: object | None = None
cron_scheduler: object | None = None
session_agent_factory: object | None = None
session_manager: object | None = None
proactive_service: object | None = None
ws_registry = openher_context.ws_registry
demo_inject_service = openher_context.demo_inject_service
ws_demo_proactive_service = openher_context.ws_demo_proactive_service
ws_demo_command_service: object | None = None
ws_chat_turn_service: object | None = None
persona_switch_service: object | None = None
ws_tts_service: object | None = None
genome_data_dir: str = ""

# ──────────────────────────────────────────────────────────────
# Proactive Heartbeat — Drive-driven autonomous messaging
# ──────────────────────────────────────────────────────────────

async def _proactive_heartbeat_loop():
    """Compatibility wrapper for the proactive service loop."""
    if not openher_context.proactive_service:
        return
    await openher_context.proactive_service.heartbeat_loop()


async def _proactive_sweep():
    """Compatibility wrapper for one proactive service sweep."""
    if openher_context.proactive_service:
        await openher_context.proactive_service.sweep()


async def _deliver_proactive_msg(agent: ChatAgent, session_id: str, row: dict):
    """Compatibility wrapper for proactive service delivery."""
    if not openher_context.proactive_service:
        raise RuntimeError("Proactive service is not initialized")
    await openher_context.proactive_service.deliver_message(agent, session_id, row)


# ──────────────────────────────────────────────────────────────
# Message Protocol
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# Session Management (with TTL + persistence)
# ──────────────────────────────────────────────────────────────

def _persist_agent(agent: ChatAgent) -> None:
    """Compatibility wrapper for session-manager persistence."""
    if openher_context.session_manager:
        openher_context.session_manager.persist_agent(agent)


def _cleanup_expired_sessions() -> int:
    """Compatibility wrapper for session-manager TTL cleanup."""
    return openher_context.session_manager.cleanup_expired_sessions() if openher_context.session_manager else 0


def get_or_create_session(
    session_id: Optional[str],
    persona_id: str,
    user_name: Optional[str] = None,
    client_id: Optional[str] = None,
) -> tuple[str, ChatAgent]:
    """Compatibility wrapper for session-manager get-or-create."""
    if not openher_context.session_manager:
        raise RuntimeError("Session manager is not initialized")
    return openher_context.session_manager.get_or_create(session_id, persona_id, user_name, client_id)


def remove_session(session_id: str) -> None:
    """Compatibility wrapper for session-manager removal."""
    if openher_context.session_manager:
        openher_context.session_manager.remove(session_id)
