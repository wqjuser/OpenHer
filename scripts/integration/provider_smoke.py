"""Optional live smoke checks for configured OpenHer providers."""

from __future__ import annotations

import os
import sys
import asyncio
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INTEGRATION_ENV = "RUN_OPENHER_INTEGRATION"
TRUE_VALUES = {"1", "true", "yes", "on"}


def integration_enabled() -> bool:
    """Return True when live external provider checks are explicitly enabled."""
    value = os.getenv(INTEGRATION_ENV, "")
    return value.strip().lower() in TRUE_VALUES


def skip_message() -> str:
    return (
        "Integration smoke skipped. "
        f"Set {INTEGRATION_ENV}=1 or run `make integration-smoke` to call live providers."
    )


async def smoke_llm_chat() -> dict[str, str]:
    """Send a tiny chat through the configured LLM provider."""
    from providers.config import get_llm_config
    from providers.llm.client import ChatMessage, LLMClient

    llm_cfg = get_llm_config()
    provider = str(llm_cfg["provider"])
    model = str(llm_cfg["model"])
    if not bool(llm_cfg.get("available", True)):
        reason = str(llm_cfg.get("missing_key_env") or "not_configured")
        return {"status": "skipped", "provider": provider, "reason": reason}

    client = LLMClient(
        provider=provider,
        model=model,
        api_key=str(llm_cfg.get("api_key") or "") or None,
        base_url=str(llm_cfg.get("base_url") or "") or None,
        temperature=0.2,
        max_tokens=64,
    )
    messages = [
        ChatMessage(role="system", content="Reply with exactly: OK"),
        ChatMessage(role="user", content="Say OK"),
    ]
    response = None
    for _attempt in range(2):
        response = await client.chat(messages, temperature=0.0, max_tokens=32)
        if response.content.strip():
            break
    if response is None or not response.content.strip():
        raise RuntimeError("LLM provider returned an empty response")
    return {
        "status": "ok",
        "provider": provider,
        "model": response.model or model,
        "reply_chars": str(len(response.content.strip())),
    }


async def smoke_evermemos() -> dict[str, str]:
    """Verify optional EverMemOS memory provider configuration."""
    from providers.config import get_memory_config
    from providers.memory.evermemos.evermemos_client import EverMemOSClient

    memory_cfg = get_memory_config()
    has_memory_config = bool(
        memory_cfg.get("enabled")
        or memory_cfg.get("base_url")
        or memory_cfg.get("api_key")
    )
    if not has_memory_config:
        return {"status": "skipped", "reason": "not_configured"}

    client = EverMemOSClient(
        base_url=str(memory_cfg.get("base_url") or "") or None,
        api_key=str(memory_cfg.get("api_key") or "") or None,
    )
    if not client.available:
        raise RuntimeError("EverMemOS is configured but the client is unavailable")

    ok = await client.verify_connection()
    if ok is False:
        raise RuntimeError("EverMemOS connection verification failed")

    status_code = await _strict_evermemos_search_status(client)
    return {"status": "ok", "http_status": str(status_code)}


async def _strict_evermemos_search_status(client: Any) -> int:
    """Make a direct search request so integration smoke catches live endpoint failures."""
    http_client = getattr(client, "_client", None)
    if http_client is None:
        raise RuntimeError("EverMemOS HTTP client is unavailable")

    body = {
        "filters": {"user_id": "__openher_smoke__"},
        "query": "__openher_smoke__",
        "method": "keyword",
        "top_k": 1,
    }
    try:
        response = await http_client.request(
            "POST",
            "/memories/search",
            json=body,
            timeout=8.0,
        )
        if response.status_code in (404, 405):
            response = await http_client.request(
                "POST",
                "/memory/search",
                json={
                    "query": "__openher_smoke__",
                    "method": "keyword",
                    "user_id": "__openher_smoke__",
                    "app_id": "openher",
                    "project_id": "openher",
                    "top_k": 1,
                },
                timeout=8.0,
            )

        if response.status_code >= 400:
            raise RuntimeError(f"EverMemOS search failed with HTTP {response.status_code}")
        return int(response.status_code)
    finally:
        await http_client.aclose()


async def smoke_tts_provider() -> dict[str, str]:
    """Instantiate the configured TTS provider without generating audio."""
    from providers.config import get_tts_config
    from providers.registry import get_tts

    tts_cfg = get_tts_config()
    provider = str(tts_cfg["provider"])
    if not bool(tts_cfg.get("available")):
        reason = str(tts_cfg.get("missing_key_env") or "not_configured")
        return {"status": "skipped", "provider": provider, "reason": reason}

    cache_dir = ROOT / ".cache" / "integration" / "tts"
    instance = get_tts(provider=provider, cache_dir=str(cache_dir))
    return {
        "status": "ok",
        "provider": provider,
        "class": type(instance).__name__,
        "cache_dir": ".cache/integration/tts",
    }


async def smoke_image_provider() -> dict[str, str]:
    """Instantiate the configured image provider without generating an image."""
    from providers.config import get_image_config
    from providers.registry import get_image_gen

    image_cfg = get_image_config()
    provider = str(image_cfg["provider"])
    if not bool(image_cfg.get("available")):
        reason = str(image_cfg.get("missing_key_env") or "not_configured")
        return {"status": "skipped", "provider": provider, "reason": reason}

    cache_dir = ROOT / ".cache" / "integration" / "image"
    instance = get_image_gen(provider=provider, cache_dir=str(cache_dir))
    return {
        "status": "ok",
        "provider": provider,
        "model": str(image_cfg.get("model") or ""),
        "class": type(instance).__name__,
        "cache_dir": ".cache/integration/image",
    }


async def run_smoke() -> list[tuple[str, dict[str, str]]]:
    """Run all configured live provider checks."""
    results = [
        ("llm", await smoke_llm_chat()),
        ("evermemos", await smoke_evermemos()),
        ("tts", await smoke_tts_provider()),
        ("image", await smoke_image_provider()),
    ]
    return results


def _format_result(name: str, result: dict[str, str]) -> str:
    fields = " ".join(f"{key}={value}" for key, value in sorted(result.items()))
    return f"{name}: {fields}"


async def _async_main() -> int:
    load_dotenv(ROOT / ".env")

    if not integration_enabled():
        print(skip_message())
        return 0

    try:
        results = await run_smoke()
    except Exception as exc:
        from server.errors import redact_known_secrets

        message = redact_known_secrets(str(exc))
        print(f"integration smoke failed: {type(exc).__name__}: {message}", file=sys.stderr)
        return 1

    for name, result in results:
        print(_format_result(name, result))
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
