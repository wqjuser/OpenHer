"""Secret-safe provider diagnostics shared by CLI and backend status."""

from __future__ import annotations

from typing import Any


def provider_secret_configured(cfg: dict[str, Any], active: bool = False) -> bool:
    """Return whether provider config contains a secret without exposing it."""
    secret_key = "api_" + "key"
    key = f"active_{secret_key}" if active else secret_key
    return bool(cfg.get(key))


def required_provider_doctor_check(label: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Convert a required provider config into the local doctor check shape."""
    configured = provider_secret_configured(cfg)
    available = bool(cfg.get("available", False))
    missing = str(cfg.get("missing_key_env") or "")
    status = "ok" if available else "error"
    message = f"{label} provider is configured" if available else f"Missing required {label} key: {missing}"
    hint = (
        "No action needed."
        if available
        else f"Set {missing} in .env, or switch DEFAULT_PROVIDER to a provider that is configured."
    )
    return _diagnostic_check(
        status,
        message,
        hint,
        {
            "provider": str(cfg.get("provider") or ""),
            "model": str(cfg.get("model") or ""),
            "api_key_configured": configured,
            "base_url_configured": bool(cfg.get("base_url")),
            "missing_key_env": missing,
        },
    )


def optional_provider_doctor_check(label: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Convert an optional provider config into the local doctor check shape."""
    configured = provider_secret_configured(cfg, active=True)
    available = bool(cfg.get("available", False))
    missing = str(cfg.get("missing_key_env") or "")
    status = "ok" if available else "warn"
    message = (
        f"{label} provider is configured"
        if available
        else f"{label} provider is optional but not configured: {missing}"
    )
    hint = (
        "No action needed."
        if available
        else f"optional: set {missing} in .env if you need {label.lower()} features."
    )
    details = {
        "provider": str(cfg.get("provider") or ""),
        "api_key_configured": configured,
        "missing_key_env": missing,
    }
    model = str(cfg.get("model") or cfg.get("minimax_model") or "")
    if model:
        details["model"] = model
    return _diagnostic_check(status, message, hint, details)


def provider_setup_hint(missing_key_env: str) -> str:
    """Return a backend-facing setup hint for an unavailable provider."""
    if missing_key_env:
        return f"Set {missing_key_env} in .env, then restart the backend."
    return "Configure this provider in providers/api.yaml or .env, then restart the backend."


def provider_capability_status(cfg: dict[str, Any]) -> dict[str, Any]:
    """Convert raw provider config into the /api/status provider shape."""
    available = bool(cfg.get("available", False))
    missing_key_env = str(cfg.get("missing_key_env") or "")
    return {
        "provider": str(cfg.get("provider") or ""),
        "available": available,
        "missing_key_env": missing_key_env,
        "setup_hint": "" if available else provider_setup_hint(missing_key_env),
    }


def memory_runtime_status(cfg: dict[str, Any], runtime_available: bool) -> dict[str, Any]:
    """Convert memory config plus runtime state into the /api/status memory shape."""
    status = {
        "provider": "evermemos",
        "enabled": bool(cfg.get("enabled", False)),
        "configured": bool(cfg.get("base_url") or cfg.get("api_key")),
        "available": runtime_available,
    }
    status["setup_hint"] = memory_setup_hint(status)
    return status


def memory_setup_hint(memory: dict[str, Any]) -> str:
    """Return a backend-facing setup hint for memory readiness."""
    if memory.get("available", False):
        return ""
    if not memory.get("enabled", False) or not memory.get("configured", False):
        return (
            "Set EVERMEMOS_API_KEY or MEMORY_API_KEY in .env to enable EverMemOS; "
            "omit EVERMEMOS_BASE_URL to use the cloud default."
        )
    return "Check EverMemOS credentials or network connectivity, then restart the backend."


def capabilities_status(providers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Derive feature capability status from provider status."""
    memory = providers["memory"]
    memory_available = bool(memory.get("available", False))
    return {
        "chat": provider_feature_status(providers["llm"], "LLM", ["llm"]),
        "voice": provider_feature_status(providers["tts"], "TTS", ["tts"]),
        "image": provider_feature_status(providers["image"], "Image", ["image"]),
        "memory": feature_status(
            available=memory_available,
            reason=memory_unavailable_reason(memory),
            requires=["memory"],
            setup_hint=str(memory.get("setup_hint") or ""),
        ),
    }


def provider_feature_status(
    provider: dict[str, Any],
    label: str,
    requires: list[str],
) -> dict[str, Any]:
    """Return feature readiness driven by a provider status object."""
    available = bool(provider.get("available", False))
    return feature_status(
        available=available,
        reason=missing_key_reason(label, str(provider.get("missing_key_env") or "")),
        requires=requires,
        setup_hint=str(provider.get("setup_hint") or ""),
    )


def feature_status(
    available: bool,
    reason: str,
    requires: list[str],
    setup_hint: str = "",
) -> dict[str, Any]:
    """Return the /api/status capability summary shape."""
    return {
        "available": available,
        "reason": "" if available else reason,
        "requires": requires,
        "setup_hint": "" if available else setup_hint,
    }


def missing_key_reason(label: str, missing_key_env: str) -> str:
    """Return a user-facing reason for an unavailable provider feature."""
    if missing_key_env:
        return f"{label} provider is not configured (missing {missing_key_env})"
    return f"{label} provider is not configured"


def memory_unavailable_reason(memory: dict[str, Any]) -> str:
    """Return a user-facing reason for memory feature unavailability."""
    if not memory.get("enabled", False):
        return "EverMemOS is disabled"
    if not memory.get("configured", False):
        return "EverMemOS is not configured"
    return "EverMemOS is not available"


def _diagnostic_check(status: str, message: str, setup_hint: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "setup_hint": setup_hint,
        "details": details,
    }
