"""Backward-compatible wrapper around :mod:`providers.config`."""

from __future__ import annotations

from providers.config import EVERMEMOS_CLOUD_BASE_URL
from providers.config import _load
from providers.config import get_llm_config
from providers.config import get_memory_config
from providers.config import get_tts_config
from providers.config import reload


__all__ = [
    "EVERMEMOS_CLOUD_BASE_URL",
    "_load",
    "get_llm_config",
    "get_memory_config",
    "get_tts_config",
    "reload",
]
