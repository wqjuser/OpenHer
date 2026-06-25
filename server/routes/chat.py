"""Chat REST routes."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query, Request

from server.context import context_from_request
from server.errors import external_error_detail, redact_known_secrets
from server.schemas import ChatRequest


router = APIRouter()


@router.post("/api/chat")
async def chat_api(req: ChatRequest, request: Request):
    ctx = context_from_request(request)
    if not ctx.session_manager:
        raise HTTPException(status_code=503, detail="Session manager is not initialized")
    session_manager = ctx.session_manager
    try:
        session_id, agent = session_manager.get_or_create(
            req.session_id, req.persona_id, req.user_name, req.client_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        result = await agent.chat(req.message)
    except Exception as e:
        print(f"  [chat_api] provider error: {type(e).__name__}: {str(e)[:200]}")
        raise HTTPException(
            status_code=502,
            detail=external_error_detail("Chat provider failed", e),
        )

    status = agent.get_status()
    session_manager.persist_agent(agent)

    if ctx.chat_log_store and req.client_id:
        try:
            ctx.chat_log_store.save_turn(
                client_id=req.client_id,
                persona_id=req.persona_id,
                user_msg=req.message,
                agent_reply=result["reply"],
                modality=result.get("modality", "文字"),
            )
        except Exception as e:
            print(f"  [chat_log] save error: {e}")

    return {
        "session_id": session_id,
        "response": result["reply"],
        "modality": result["modality"],
        "image_url": f"/api/selfie/{os.path.basename(result['image_path'])}" if result.get("image_path") else None,
        **status,
    }


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
