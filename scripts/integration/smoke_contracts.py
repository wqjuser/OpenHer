"""Shared helpers for OpenHer integration smoke contracts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


PROVIDER_KEYS = ("llm", "tts", "image", "memory")
CAPABILITY_KEYS = ("chat", "voice", "image", "memory")


@dataclass(frozen=True)
class StatusDiagnostics:
    providers: dict[str, Any]
    capabilities: dict[str, Any]
    chat: dict[str, Any]
    voice: dict[str, Any]
    image: dict[str, Any]
    memory: dict[str, Any]
    memory_provider: dict[str, Any]


def auth_headers(token: str) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def decode_json(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object, got {safe_value(value)}")
    return value


def require_status(status_code: int, expected: int, label: str, detail: Any = "") -> None:
    if status_code == expected:
        return
    suffix = f": {safe_value(detail)}" if detail else ""
    raise AssertionError(f"{label}: expected HTTP {expected}, got {status_code}{suffix}")


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError(f"{label}: expected object, got {safe_value(value)}")
    return value


def bool_text(value: Any, label: str) -> str:
    if not isinstance(value, bool):
        raise AssertionError(f"{label} must be a boolean")
    return str(value).lower()


def safe_value(value: Any) -> str:
    return str(value).replace("\n", " ")[:500]


def format_result(name: str, result: dict[str, str]) -> str:
    fields = " ".join(f"{key}={value}" for key, value in sorted(result.items()))
    return f"{name}: {fields}"


def validate_status_diagnostics(
    body: dict[str, Any],
    *,
    require_setup_hints: bool = False,
) -> StatusDiagnostics:
    if body.get("status") != "running":
        raise AssertionError(f"status: expected running, got {body.get('status')!r}")

    providers = require_dict(body.get("providers"), "status.providers")
    capabilities = require_dict(body.get("capabilities"), "status.capabilities")

    for key in PROVIDER_KEYS:
        if key not in providers:
            raise AssertionError(f"status.providers: missing {key}")
    for key in CAPABILITY_KEYS:
        if key not in capabilities:
            raise AssertionError(f"status.capabilities: missing {key}")

    provider_sections = {
        key: require_dict(providers.get(key), f"status.providers.{key}")
        for key in PROVIDER_KEYS
    }
    capability_sections = {
        key: require_dict(capabilities.get(key), f"status.capabilities.{key}")
        for key in CAPABILITY_KEYS
    }

    for key, section in provider_sections.items():
        if require_setup_hints and not isinstance(section.get("setup_hint"), str):
            raise AssertionError(f"status.providers.{key}.setup_hint must be a string")

    for key, section in capability_sections.items():
        if not isinstance(section.get("available"), bool):
            raise AssertionError(f"status.capabilities.{key}.available must be a boolean")
        if "reason" not in section:
            raise AssertionError(f"status.capabilities.{key}.reason is required")
        if require_setup_hints and not isinstance(section.get("setup_hint"), str):
            raise AssertionError(f"status.capabilities.{key}.setup_hint must be a string")

    memory_provider = provider_sections["memory"]
    for key in ("enabled", "configured", "available"):
        if not isinstance(memory_provider.get(key), bool):
            raise AssertionError(f"status.providers.memory.{key} must be a boolean")

    return StatusDiagnostics(
        providers=providers,
        capabilities=capabilities,
        chat=capability_sections["chat"],
        voice=capability_sections["voice"],
        image=capability_sections["image"],
        memory=capability_sections["memory"],
        memory_provider=memory_provider,
    )
