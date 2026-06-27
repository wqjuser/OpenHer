"""WebSocket chat route."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from server.context import context_from_websocket
from server.security import request_has_api_token
from server.websocket_route_service import WebSocketRouteService


router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """WebSocket endpoint for real-time persona chat with Genome v10."""
    ctx = context_from_websocket(ws)
    if not request_has_api_token(
        ws.headers.get("Authorization"),
        ws.query_params.get("token"),
    ):
        await ws.close(code=1008)
        return
    await ws.accept()
    service = ctx.ws_route_service or WebSocketRouteService(
        registry=ctx.ws_registry,
        session_manager=ctx.session_manager,
        chat_turn_service=ctx.ws_chat_turn_service,
        tts_service=ctx.ws_tts_service,
        persona_switch_service=ctx.persona_switch_service,
        demo_command_service=ctx.ws_demo_command_service,
    )
    await service.handle_connection(ws)
