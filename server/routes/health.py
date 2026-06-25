"""Health and observability routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from server.context import context_from_request
from server.proactive_service import default_proactive_metrics


router = APIRouter()


@router.get("/api/proactive/metrics")
async def proactive_metrics(request: Request):
    """Proactive messaging observability: rates and counters."""
    ctx = context_from_request(request)
    if ctx.proactive_service:
        return ctx.proactive_service.metrics_snapshot()
    return default_proactive_metrics()


@router.get("/api/status")
async def api_status(request: Request):
    ctx = context_from_request(request)
    return {
        "name": "OpenHer",
        "version": "0.5.0",
        "engine": "Genome v10",
        "status": "running",
        "personas": ctx.persona_loader.list_ids() if ctx.persona_loader else [],
        "active_sessions": ctx.session_manager.active_count if ctx.session_manager else 0,
    }
