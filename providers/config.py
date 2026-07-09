"""Single source of truth for provider configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None


_config: Optional[dict] = None
_CONFIG_PATH = Path(__file__).parent / "api.yaml"
EVERMEMOS_CLOUD_BASE_URL = "https://api.evermind.ai/api/v1"
_EVERMEMOS_CLOUD_V0_BASE_URL = "https://api.evermind.ai/api/v0"

_PROVIDER_DEFAULT_MODELS = {
    "dashscope": "qwen-max",
    "openai": "gpt-4o",
    "moonshot": "moonshot-v1-auto",
    "ollama": "qwen3.5:9b",
    "gemini": "gemini-3.1-flash-lite-preview",
    "stepfun": "step-3.5-flash",
    "claude": "claude-haiku-4-5-20251001",
    "minimax": "MiniMax-M2.7",
    "deepseek": "deepseek-v4-pro",
}


@dataclass(frozen=True)
class ResolvedProviderSecret:
    api_key: str
    available: bool
    missing_key_env: str
    env_options: list[str]


def _provider_env_prefix(provider: str) -> str:
    """Convert provider id to an env-safe prefix."""
    return "".join(ch if ch.isalnum() else "_" for ch in provider.upper())


def _first_env(*names: str) -> str:
    """Return the first non-empty environment value from the provided names."""
    for name in names:
        if not name:
            continue
        value = os.getenv(name, "")
        if value:
            return value
    return ""


def _api_key_env_options(provider: str, preset_env: str, generic_env: str = "") -> list[str]:
    """Return API-key env candidates in priority order without duplicates."""
    provider_env = f"{_provider_env_prefix(provider)}_API_KEY"
    return [name for name in dict.fromkeys((preset_env, provider_env, generic_env)) if name]


def _missing_key_env(options: list[str]) -> str:
    """Render a readable missing-key hint for accepted API-key env vars."""
    return " or ".join(options)


def normalize_evermemos_base_url(base_url: str) -> str:
    """Normalize EverMemOS base URLs to the active API path."""
    url = base_url.rstrip("/")
    if url == _EVERMEMOS_CLOUD_V0_BASE_URL:
        return EVERMEMOS_CLOUD_BASE_URL
    if url and not url.endswith("/api/v1") and "/api/" not in url:
        return f"{url}/api/v1"
    return url


def _resolve_provider_secret(
    provider_name: str,
    preset: dict,
    generic_env: str = "",
) -> ResolvedProviderSecret:
    """Resolve one active provider secret and availability metadata."""
    env_options = _api_key_env_options(
        provider_name,
        str(preset.get("api_key_env") or ""),
        generic_env,
    )
    api_key = _first_env(*env_options)
    available = bool(preset.get("no_key_required", False)) or bool(api_key)
    missing_key_env = "" if available else _missing_key_env(env_options)
    return ResolvedProviderSecret(
        api_key=api_key,
        available=available,
        missing_key_env=missing_key_env,
        env_options=env_options,
    )


def _resolve_provider_secret_map(
    providers: dict,
    active_provider: str,
    generic_env: str,
) -> tuple[dict[str, str], ResolvedProviderSecret]:
    """Resolve all provider secrets while applying generic env only to active provider."""
    api_keys = {}
    active_secret: ResolvedProviderSecret | None = None
    for name, provider_cfg in providers.items():
        preset = provider_cfg if isinstance(provider_cfg, dict) else {}
        secret = _resolve_provider_secret(
            name,
            preset,
            generic_env if name == active_provider else "",
        )
        api_keys[name] = secret.api_key
        if name == active_provider:
            active_secret = secret
    if active_secret is None:
        active_secret = _resolve_provider_secret(active_provider, {}, generic_env)
    return api_keys, active_secret


def _load() -> dict:
    """Load providers/api.yaml once. Returns an empty dict on error."""
    global _config
    if _config is not None:
        return _config

    if yaml is None:
        print("  [providers/config] ⚠ pyyaml not installed, using defaults")
        _config = {}
        return _config

    if not _CONFIG_PATH.exists():
        print(f"  [providers/config] ⚠ {_CONFIG_PATH} not found, using env vars only")
        _config = {}
        return _config

    try:
        loaded = yaml.safe_load(_CONFIG_PATH.read_text())
        _config = loaded if isinstance(loaded, dict) else {}
    except Exception as e:
        print(f"  [providers/config] ⚠ parse error: {e}")
        _config = {}

    return _config


def reload():
    """Force reload of provider config, useful for tests."""
    global _config
    _config = None
    return _load()


def get_llm_config(provider: Optional[str] = None) -> dict:
    """Resolve LLM configuration including provider-specific env overrides."""
    cfg = _load()
    llm = cfg.get("llm", {})
    provider_name = (
        provider
        or os.getenv("DEFAULT_PROVIDER")
        or llm.get("provider")
        or llm.get("active_provider")
        or "claude"
    )
    providers = llm.get("providers", {})
    preset = providers.get(provider_name, {})

    secret = _resolve_provider_secret(provider_name, preset, "LLM_API_KEY")

    base_url_env = preset.get("base_url_env", "")
    base_url = (
        _first_env(f"{_provider_env_prefix(provider_name)}_BASE_URL", "LLM_BASE_URL", base_url_env)
        or preset.get("base_url", "")
    )

    model = (
        os.getenv("DEFAULT_MODEL")
        or llm.get("model")
        or preset.get("default_model")
        or _PROVIDER_DEFAULT_MODELS.get(provider_name, "qwen-max")
    )

    return {
        "provider": provider_name,
        "model": model,
        "api_key": secret.api_key,
        "base_url": base_url,
        "available": secret.available,
        "missing_key_env": secret.missing_key_env,
        "temperature": llm.get("temperature", 0.92),
        "max_tokens": llm.get("max_tokens", 1024),
        "providers": providers,
        "active_provider_config": preset,
    }


def get_llm_provider_config() -> dict:
    """Compatibility shape used by providers.registry."""
    llm = get_llm_config()
    return {
        "active_provider": llm["provider"],
        "model": llm["model"],
        "temperature": llm["temperature"],
        "max_tokens": llm["max_tokens"],
        "providers": llm["providers"],
    }


def _tts_section() -> dict:
    cfg = _load()
    speech = cfg.get("speech")
    if isinstance(speech, dict) and (
        "provider" in speech or "active_provider" in speech or "providers" in speech
    ):
        return speech
    return cfg.get("tts", {})


def get_tts_config(provider: Optional[str] = None) -> dict:
    """Resolve TTS configuration including all configured API keys."""
    tts = _tts_section()
    providers = tts.get("providers", {})
    provider_name = provider or tts.get("provider", tts.get("active_provider", "dashscope"))
    api_keys, active_secret = _resolve_provider_secret_map(providers, provider_name, "TTS_API_KEY")

    active_preset = providers.get(provider_name, {})

    return {
        "provider": provider_name,
        "cache_dir": tts.get("cache_dir", ".cache/tts"),
        "api_keys": api_keys,
        "active_api_key": active_secret.api_key,
        "available": active_secret.available,
        "missing_key_env": active_secret.missing_key_env,
        "minimax_model": providers.get("minimax", {}).get("model", "speech-2.8-turbo"),
        "active_provider_config": active_preset,
    }


def get_tts_provider_config() -> dict:
    """Compatibility shape used by providers.registry."""
    resolved = get_tts_config()
    tts = _tts_section()
    return {
        "active_provider": resolved["provider"],
        "cache_dir": resolved["cache_dir"],
        "providers": tts.get("providers", {}),
    }


def get_memory_config() -> dict:
    """Resolve EverMemOS configuration."""
    cfg = _load()
    mem = cfg.get("memory", {})
    ever_cfg = mem.get("evermemos", {})

    env_base_url = _first_env("EVERMEMOS_BASE_URL", "MEMORY_BASE_URL")
    base_url = normalize_evermemos_base_url(
        env_base_url or ever_cfg.get("base_url", "") or mem.get("base_url", "")
    )
    api_key_env = ever_cfg.get("api_key_env", "") or mem.get("api_key_env", "EVERMEMOS_API_KEY")
    api_key = _first_env(api_key_env, "EVERMEMOS_API_KEY", "MEMORY_API_KEY")

    enabled = ever_cfg.get("enabled", mem.get("enabled", False))
    if env_base_url or api_key:
        enabled = True
    if api_key and not base_url:
        base_url = EVERMEMOS_CLOUD_BASE_URL

    return {
        "enabled": enabled,
        "base_url": base_url,
        "api_key": api_key,
    }


def get_memory_provider_config() -> dict:
    """Resolve all memory provider configuration."""
    cfg = _load()
    mem = cfg.get("memory", {})
    soulmem_cfg = mem.get("soulmem", {})

    return {
        "soulmem": {
            "db_path": soulmem_cfg.get("db_path", ".data/memory.db"),
        },
        "evermemos": get_memory_config(),
    }


def get_image_config(provider: Optional[str] = None) -> dict:
    """Resolve image generation provider configuration including API keys."""
    cfg = _load()
    image = cfg.get("image", {})
    providers = image.get("providers", {})
    provider_name = (
        provider
        or image.get("provider")
        or image.get("active_provider")
        or "gemini"
    )
    api_keys, active_secret = _resolve_provider_secret_map(providers, provider_name, "IMAGE_API_KEY")

    active_preset = providers.get(provider_name, {})

    return {
        "provider": provider_name,
        "cache_dir": image.get("cache_dir", ".cache/image"),
        "api_keys": api_keys,
        "active_api_key": active_secret.api_key,
        "available": active_secret.available,
        "missing_key_env": active_secret.missing_key_env,
        "model": active_preset.get("model", ""),
        "providers": providers,
        "active_provider_config": active_preset,
    }


def get_image_provider_config() -> dict:
    """Compatibility shape for image generation provider configuration."""
    resolved = get_image_config()
    return {
        "active_provider": resolved["provider"],
        "cache_dir": resolved["cache_dir"],
        "providers": resolved["providers"],
    }
