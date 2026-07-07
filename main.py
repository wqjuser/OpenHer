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

from server import bootstrap
from server.context import AppContext
from server.legacy_compat import LegacyCompatibility, initial_legacy_globals, sync_legacy_globals
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
    sync_legacy_globals(context, globals())
    try:
        yield
    finally:
        await bootstrap.shutdown(context)
        sync_legacy_globals(context, globals())


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
chat_api_service: object | None = None
media_api_service: object | None = None
persona_api_service: object | None = None
proactive_service: object | None = None
ws_registry: object = openher_context.ws_registry
demo_inject_service: object = openher_context.demo_inject_service
ws_demo_proactive_service: object = openher_context.ws_demo_proactive_service
ws_demo_command_service: object | None = None
ws_route_service: object | None = None
ws_chat_turn_service: object | None = None
persona_switch_service: object | None = None
ws_tts_service: object | None = None
genome_data_dir: str = ""

globals().update(initial_legacy_globals(openher_context))
legacy_helpers = LegacyCompatibility(openher_context)

# ──────────────────────────────────────────────────────────────
# Proactive Heartbeat — Drive-driven autonomous messaging
# ──────────────────────────────────────────────────────────────

_proactive_heartbeat_loop = legacy_helpers.proactive_heartbeat_loop
_proactive_sweep = legacy_helpers.proactive_sweep
_deliver_proactive_msg = legacy_helpers.deliver_proactive_msg


# ──────────────────────────────────────────────────────────────
# Message Protocol
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# Session Management (with TTL + persistence)
# ──────────────────────────────────────────────────────────────

_persist_agent = legacy_helpers.persist_agent
_cleanup_expired_sessions = legacy_helpers.cleanup_expired_sessions
get_or_create_session = legacy_helpers.get_or_create_session
remove_session = legacy_helpers.remove_session
