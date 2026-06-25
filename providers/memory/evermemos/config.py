from __future__ import annotations

import os
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def _load_memory_config() -> dict:
    """Load config/memory_config.yaml; fall back to safe defaults.
    ENV override: OPENHER_MEMORY__<KEY>=value overrides any key.
    Example: OPENHER_MEMORY__RETRIEVE_METHOD=agentic
    """
    defaults = {
        "enabled": True,
        "base_url": "http://localhost:1995/api/v1",
        "retrieve_method": "rrf",
        "agentic_rollout_pct": 0,
        "search_timeout_sec": 3.0,
        "load_timeout_sec": 5.0,
        "foresight_max_items": 3,
        "foresight_max_chars": 200,
        "profile_max_items": 5,
        "facts_max_items": 5,
        "episodes_max_items": 3,
        "circuit_breaker_enabled": True,
        "failure_threshold": 5,
        "recovery_timeout_sec": 60,
        "log_hit_rates": True,
        "log_latency": True,
    }
    config_path = Path(__file__).parent / "memory_config.yaml"
    if yaml is not None and config_path.exists():
        try:
            data = yaml.safe_load(config_path.read_text()) or {}
            cfg = data.get("evermemos", data)
            merged = {**defaults, **cfg}
        except Exception as e:
            print(f"  [evermemos] config load error: {e} — using defaults")
            merged = dict(defaults)
    else:
        merged = dict(defaults)

    prefix = "OPENHER_MEMORY__"
    for env_key, env_val in os.environ.items():
        if env_key.upper().startswith(prefix):
            cfg_key = env_key[len(prefix) :].lower()
            if cfg_key in merged:
                orig = merged[cfg_key]
                try:
                    if isinstance(orig, bool):
                        merged[cfg_key] = env_val.lower() in ("1", "true", "yes")
                    elif isinstance(orig, int):
                        merged[cfg_key] = int(env_val)
                    elif isinstance(orig, float):
                        merged[cfg_key] = float(env_val)
                    else:
                        merged[cfg_key] = env_val
                except ValueError:
                    pass

    return merged


_CFG = _load_memory_config()


def _fmt_latency(elapsed_ms: float) -> str:
    """Format latency string, respecting log_latency config flag."""
    if _CFG.get("log_latency", True):
        return f" ({elapsed_ms:.0f}ms)"
    return ""
