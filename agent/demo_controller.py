"""
DemoController — Engine control console for demo/recording sessions.

Provides "god mode" tools for presentations:
  1. Time jump: fast-forward metabolism engine by N hours
  2. State injection: directly set frustration/drive values
  3. Preset messages: pre-loaded demo messages for quick-fire sending

All LLM responses remain real — this only manipulates engine state.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import yaml

from engine.genome.genome_engine import DRIVES


class DemoController:
    """Demo mode control console — manipulate time and engine state."""

    def __init__(self, agent):
        """
        Args:
            agent: ChatAgent instance to control.
        """
        self.agent = agent
        self.presets: list[dict] = []
        self.scenarios: dict[str, dict] = {}
        self._preset_index: int = 0

    # ── Time Jump ──

    def time_jump(self, hours: float) -> dict:
        """Fast-forward metabolism engine by N hours.

        Drives and frustration evolve according to physics equations:
          - frustration *= e^(-λΔt)  (cooling)
          - connection += k * Δt     (loneliness)
          - novelty += k * Δt        (boredom)

        Returns: engine state snapshot after the jump.
        """
        future = time.time() + hours * 3600
        self.agent.metabolism.time_metabolism(future)
        self.agent.metabolism.sync_to_agent(self.agent.agent)
        # Update _last_active so proactive system sees the gap
        if hasattr(self.agent, '_last_active'):
            self.agent._last_active = time.time()
        return self.snapshot()

    # ── State Injection ──

    def inject_state(self, overrides: dict) -> dict:
        """Directly inject engine state values.

        overrides: {
            "frustration": {"connection": 1.8, ...},
            "drive_state": {"connection": 0.95, ...},
            "drive_baseline": {"connection": 0.85, ...},
        }

        Returns: engine state snapshot after injection.
        """
        if "frustration" in overrides:
            for d, v in overrides["frustration"].items():
                if d in self.agent.metabolism.frustration:
                    self.agent.metabolism.frustration[d] = max(0.0, min(5.0, float(v)))
            self.agent.metabolism.sync_to_agent(self.agent.agent)

        if "drive_state" in overrides:
            for d, v in overrides["drive_state"].items():
                if d in self.agent.agent.drive_state:
                    self.agent.agent.drive_state[d] = max(0.0, min(1.0, float(v)))

        if "drive_baseline" in overrides:
            for d, v in overrides["drive_baseline"].items():
                if d in self.agent.agent.drive_baseline:
                    self.agent.agent.drive_baseline[d] = max(0.0, min(1.0, float(v)))

        return self.snapshot()

    # ── Presets ──

    def load_presets_file(self, filepath: str) -> None:
        """Load presets from a YAML file."""
        path = Path(filepath)
        if not path.exists():
            print(f"  [demo] preset file not found: {filepath}")
            return

        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        self.presets = data.get('presets', [])
        self.scenarios = data.get('scenarios', {})
        self._preset_index = 0
        print(f"  [demo] loaded {len(self.presets)} presets, "
              f"{len(self.scenarios)} scenarios from {path.name}")

    def get_presets(self) -> list[dict]:
        """Return all preset messages."""
        return self.presets

    def get_scenarios(self) -> dict:
        """Return all scenario definitions."""
        return self.scenarios

    def apply_scenario(self, scenario_id: str) -> dict:
        """Apply a named scenario: time jump + state injection.

        Returns: engine state snapshot after applying.
        """
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            return {"error": f"scenario '{scenario_id}' not found"}

        # Time jump first (if specified)
        if 'time_jump_hours' in scenario:
            self.time_jump(scenario['time_jump_hours'])

        # Then inject state
        if 'inject' in scenario:
            self.inject_state(scenario['inject'])

        result = self.snapshot()
        result['applied_scenario'] = scenario_id
        result['scenario_label'] = scenario.get('label', scenario_id)
        return result

    # ── Snapshot ──

    def snapshot(self) -> dict:
        """Return current engine state snapshot."""
        return {
            "drive_state": {
                d: round(self.agent.agent.drive_state[d], 3)
                for d in DRIVES
            },
            "drive_baseline": {
                d: round(self.agent.agent.drive_baseline[d], 3)
                for d in DRIVES
            },
            "frustration": {
                d: round(self.agent.metabolism.frustration[d], 3)
                for d in DRIVES
            },
            "temperature": round(self.agent.metabolism.temperature(), 4),
            "total_frustration": round(self.agent.metabolism.total(), 3),
            "agent_age": self.agent.agent.age,
        }
