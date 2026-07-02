"""Health and observability routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from providers.api_config import get_image_config, get_llm_config, get_memory_config, get_tts_config
from server.context import context_from_request
from server.proactive_service import default_proactive_metrics


router = APIRouter()


def _capability_status(cfg: dict) -> dict:
    available = bool(cfg.get("available", False))
    missing_key_env = str(cfg.get("missing_key_env") or "")
    return {
        "provider": str(cfg.get("provider") or ""),
        "available": available,
        "missing_key_env": missing_key_env,
        "setup_hint": "" if available else _provider_setup_hint(missing_key_env),
    }


def _memory_status(ctx) -> dict:
    cfg = get_memory_config()
    status = {
        "provider": "evermemos",
        "enabled": bool(cfg.get("enabled", False)),
        "configured": bool(cfg.get("base_url") or cfg.get("api_key")),
        "available": bool(ctx.evermemos and ctx.evermemos.available),
    }
    status["setup_hint"] = _memory_setup_hint(status)
    return status


def _provider_setup_hint(missing_key_env: str) -> str:
    if missing_key_env:
        return f"Set {missing_key_env} in .env, then restart the backend."
    return "Configure this provider in providers/api.yaml or .env, then restart the backend."


def _memory_setup_hint(memory: dict) -> str:
    if memory.get("available", False):
        return ""
    if not memory.get("enabled", False) or not memory.get("configured", False):
        return (
            "Set EVERMEMOS_API_KEY or MEMORY_API_KEY in .env to enable EverMemOS; "
            "omit EVERMEMOS_BASE_URL to use the cloud default."
        )
    return "Check EverMemOS credentials or network connectivity, then restart the backend."


def _providers_status(ctx) -> dict:
    return {
        "llm": _capability_status(get_llm_config()),
        "tts": _capability_status(get_tts_config()),
        "image": _capability_status(get_image_config()),
        "memory": _memory_status(ctx),
    }


def _missing_key_reason(label: str, missing_key_env: str) -> str:
    if missing_key_env:
        return f"{label} provider is not configured (missing {missing_key_env})"
    return f"{label} provider is not configured"


def _feature_status(
    available: bool,
    reason: str,
    requires: list[str],
    setup_hint: str = "",
) -> dict:
    return {
        "available": available,
        "reason": "" if available else reason,
        "requires": requires,
        "setup_hint": "" if available else setup_hint,
    }


def _provider_feature_status(provider: dict, label: str, requires: list[str]) -> dict:
    available = bool(provider.get("available", False))
    return _feature_status(
        available=available,
        reason=_missing_key_reason(label, str(provider.get("missing_key_env") or "")),
        requires=requires,
        setup_hint=str(provider.get("setup_hint") or ""),
    )


def _memory_unavailable_reason(memory: dict) -> str:
    if not memory.get("enabled", False):
        return "EverMemOS is disabled"
    if not memory.get("configured", False):
        return "EverMemOS is not configured"
    return "EverMemOS is not available"


def _capabilities_status(providers: dict) -> dict:
    memory = providers["memory"]
    memory_available = bool(memory.get("available", False))
    return {
        "chat": _provider_feature_status(providers["llm"], "LLM", ["llm"]),
        "voice": _provider_feature_status(providers["tts"], "TTS", ["tts"]),
        "image": _provider_feature_status(providers["image"], "Image", ["image"]),
        "memory": _feature_status(
            available=memory_available,
            reason=_memory_unavailable_reason(memory),
            requires=["memory"],
            setup_hint=str(memory.get("setup_hint") or ""),
        ),
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
    providers = _providers_status(ctx)
    return {
        "name": "OpenHer",
        "version": "0.5.0",
        "engine": "Genome v10",
        "status": "running",
        "personas": ctx.persona_loader.list_ids() if ctx.persona_loader else [],
        "active_sessions": ctx.session_manager.active_count if ctx.session_manager else 0,
        "providers": providers,
        "capabilities": _capabilities_status(providers),
    }
