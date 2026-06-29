"""Single source of truth for provider configuration."""

from __future__ import annotations

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
    provider_prefix = _provider_env_prefix(provider_name)

    api_key_env = preset.get("api_key_env", "")
    api_key = _first_env(api_key_env, f"{provider_prefix}_API_KEY", "LLM_API_KEY")

    base_url_env = preset.get("base_url_env", "")
    base_url = (
        _first_env(f"{provider_prefix}_BASE_URL", "LLM_BASE_URL", base_url_env)
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
        "api_key": api_key,
        "base_url": base_url,
        "temperature": llm.get("temperature", 0.92),
        "max_tokens": llm.get("max_tokens", 1024),
        "providers": providers,
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
    api_keys = {}
    for name, provider_cfg in providers.items():
        env_var = provider_cfg.get("api_key_env", "")
        api_keys[name] = os.getenv(env_var, "") if env_var else ""

    active_preset = providers.get(provider_name, {})
    active_api_key = api_keys.get(provider_name, "")
    no_key_required = bool(active_preset.get("no_key_required", False))
    available = no_key_required or bool(active_api_key)
    missing_key_env = "" if available else active_preset.get("api_key_env", "")

    return {
        "provider": provider_name,
        "cache_dir": tts.get("cache_dir", ".cache/tts"),
        "api_keys": api_keys,
        "active_api_key": active_api_key,
        "available": available,
        "missing_key_env": missing_key_env,
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

    env_base_url = os.getenv("EVERMEMOS_BASE_URL", "")
    base_url = env_base_url or ever_cfg.get("base_url", "") or mem.get("base_url", "")
    api_key_env = ever_cfg.get("api_key_env", "") or mem.get("api_key_env", "EVERMEMOS_API_KEY")
    api_key = os.getenv(api_key_env, "") if api_key_env else ""

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
    api_keys = {}
    for name, provider_cfg in providers.items():
        env_var = provider_cfg.get("api_key_env", "")
        api_keys[name] = os.getenv(env_var, "") if env_var else ""

    active_preset = providers.get(provider_name, {})
    active_api_key = api_keys.get(provider_name, "")
    no_key_required = bool(active_preset.get("no_key_required", False))
    available = no_key_required or bool(active_api_key)
    missing_key_env = "" if available else active_preset.get("api_key_env", "")

    return {
        "provider": provider_name,
        "cache_dir": image.get("cache_dir", ".cache/image"),
        "api_keys": api_keys,
        "active_api_key": active_api_key,
        "available": available,
        "missing_key_env": missing_key_env,
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
