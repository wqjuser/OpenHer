"""Public engine package exports with lazy imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.genome.critic import critic_sense
    from engine.genome.drive_metabolism import DriveMetabolism, apply_thermodynamic_noise
    from engine.genome.genome_engine import DRIVE_LABELS, DRIVES, SIGNAL_LABELS, SIGNALS, Agent
    from engine.genome.style_memory import ContinuousStyleMemory
    from engine.prompt_registry import load_signal_config, render_prompt
    from engine.state_store import StateStore

__all__ = [
    "Agent",
    "DRIVES",
    "SIGNALS",
    "SIGNAL_LABELS",
    "DRIVE_LABELS",
    "DriveMetabolism",
    "apply_thermodynamic_noise",
    "critic_sense",
    "ContinuousStyleMemory",
    "StateStore",
    "render_prompt",
    "load_signal_config",
]

_EXPORTS = {
    "Agent": ("engine.genome.genome_engine", "Agent"),
    "DRIVES": ("engine.genome.genome_engine", "DRIVES"),
    "SIGNALS": ("engine.genome.genome_engine", "SIGNALS"),
    "SIGNAL_LABELS": ("engine.genome.genome_engine", "SIGNAL_LABELS"),
    "DRIVE_LABELS": ("engine.genome.genome_engine", "DRIVE_LABELS"),
    "DriveMetabolism": ("engine.genome.drive_metabolism", "DriveMetabolism"),
    "apply_thermodynamic_noise": ("engine.genome.drive_metabolism", "apply_thermodynamic_noise"),
    "critic_sense": ("engine.genome.critic", "critic_sense"),
    "ContinuousStyleMemory": ("engine.genome.style_memory", "ContinuousStyleMemory"),
    "StateStore": ("engine.state_store", "StateStore"),
    "render_prompt": ("engine.prompt_registry", "render_prompt"),
    "load_signal_config": ("engine.prompt_registry", "load_signal_config"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'engine' has no attribute {name!r}") from exc
    return getattr(import_module(module_name), attr_name)
