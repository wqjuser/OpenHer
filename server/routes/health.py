"""Health and observability routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from providers.api_config import get_image_config, get_llm_config, get_memory_config, get_tts_config
from server.context import context_from_request
from server.proactive_service import default_proactive_metrics


router = APIRouter()


def _capability_status(cfg: dict) -> dict:
    return {
        "provider": str(cfg.get("provider") or ""),
        "available": bool(cfg.get("available", False)),
        "missing_key_env": str(cfg.get("missing_key_env") or ""),
    }


def _memory_status(ctx) -> dict:
    cfg = get_memory_config()
    return {
        "provider": "evermemos",
        "enabled": bool(cfg.get("enabled", False)),
        "configured": bool(cfg.get("base_url") or cfg.get("api_key")),
        "available": bool(ctx.evermemos and ctx.evermemos.available),
    }


def _providers_status(ctx) -> dict:
    return {
        "llm": _capability_status(get_llm_config()),
        "tts": _capability_status(get_tts_config()),
        "image": _capability_status(get_image_config()),
        "memory": _memory_status(ctx),
    }


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
        "providers": _providers_status(ctx),
    }
