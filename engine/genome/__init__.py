"""Genome package exports with lazy imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.genome.critic import critic_sense
    from engine.genome.drive_metabolism import DriveMetabolism, apply_thermodynamic_noise
    from engine.genome.genome_engine import DRIVE_LABELS, DRIVES, SIGNAL_LABELS, SIGNALS, Agent
    from engine.genome.style_memory import ContinuousStyleMemory, clean_action_markers

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
    "clean_action_markers",
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
    "clean_action_markers": ("engine.genome.style_memory", "clean_action_markers"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'engine.genome' has no attribute {name!r}") from exc
    return getattr(import_module(module_name), attr_name)
