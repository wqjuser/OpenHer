"""Public agent package exports with lazy imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.chat_agent import ChatAgent
    from agent.parser import _SECTION_RE, _TAG_MAP, _parse_modality, extract_reply

__all__ = [
    "ChatAgent",
    "extract_reply",
    "_parse_modality",
    "_SECTION_RE",
    "_TAG_MAP",
]

_EXPORTS = {
    "ChatAgent": ("agent.chat_agent", "ChatAgent"),
    "extract_reply": ("agent.parser", "extract_reply"),
    "_parse_modality": ("agent.parser", "_parse_modality"),
    "_SECTION_RE": ("agent.parser", "_SECTION_RE"),
    "_TAG_MAP": ("agent.parser", "_TAG_MAP"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'agent' has no attribute {name!r}") from exc
    return getattr(import_module(module_name), attr_name)
