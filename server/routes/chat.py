"""Chat REST routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from server.chat_api_service import (
    ChatApiPersonaNotFound,
    ChatApiProviderError,
    ChatApiService,
    ChatApiServiceUnavailable,
)
from server.context import context_from_request
from server.errors import external_error_detail
from server.schemas import ChatRequest


router = APIRouter()


@router.post("/api/chat")
async def chat_api(req: ChatRequest, request: Request):
    ctx = context_from_request(request)
    service = ctx.chat_api_service or ChatApiService(
        session_manager=ctx.session_manager,
        chat_log_store=ctx.chat_log_store,
    )
    try:
        result = await service.chat(req)
    except ChatApiServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ChatApiPersonaNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ChatApiProviderError as e:
        raise HTTPException(
            status_code=502,
            detail=external_error_detail("Chat provider failed", e.original),
        ) from e
    return result.to_response()


@router.get("/api/session/{session_id}/status")
async def session_status(session_id: str, request: Request):
    ctx = context_from_request(request)
    entry = ctx.session_manager.get_entry(session_id) if ctx.session_manager else None
    if not entry:
        raise HTTPException(status_code=404, detail="Session not found")
    agent, _ = entry
    return agent.get_status()


@router.get("/api/chat/history/{persona_id}")
async def get_chat_history(
    persona_id: str,
    request: Request,
    client_id: str = Query(..., description="Frontend client identity (localStorage UUID)"),
    limit: int = Query(50, ge=1, le=500),
    before_id: int = Query(None, description="Pagination cursor — return messages before this id"),
):
    """Load chat history for display. Does not affect engine state."""
    ctx = context_from_request(request)
    if not ctx.chat_log_store:
        return {"messages": [], "total": 0}
    messages = ctx.chat_log_store.load_messages(client_id, persona_id, limit, before_id)
    total = ctx.chat_log_store.count_messages(client_id, persona_id)
    return {"messages": messages, "total": total}
