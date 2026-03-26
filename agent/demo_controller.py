"""
DemoController — Engine control console for demo/recording sessions.

Provides "god mode" tools for presentations:
  1. Time jump:        fast-forward metabolism engine by N hours
  2. State injection:  directly set frustration/drive values
  3. Force proactive:  trigger proactive tick immediately
  4. Inject memory:    plant a memory for later recall
  5. Preset messages:  pre-loaded demo messages for quick-fire sending

All LLM responses remain real — this only manipulates engine state.
Zero modification to core engine files.
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
          - connection += k * Δt     (loneliness accumulates)
          - novelty += k * Δt        (boredom accumulates)

        Crucially sets _last_active to simulate "N hours of silence"
        so proactive_tick sees the gap.

        Returns: engine state snapshot after the jump.
        """
        future = time.time() + hours * 3600
        self.agent.metabolism.time_metabolism(future)
        self.agent.metabolism.sync_to_agent(self.agent.agent)
        # KEY: Set _last_active to N hours AGO so proactive sees the gap
        if hasattr(self.agent, '_last_active'):
            self.agent._last_active = time.time() - hours * 3600
        return self.snapshot()

    # ── Force Proactive ──

    async def force_proactive(self, simulated_hours: float = 0) -> dict:
        """Force an immediate proactive tick (bypasses heartbeat timer).

        KEY TRICK: proactive_tick() calls time_metabolism(now) internally,
        which uses metabolism._last_tick to compute delta_hours.
        We set _last_tick backwards so the tick sees the simulated time gap.
        
        If simulated_hours=0, uses the gap from the most recent time_jump.

        Returns the proactive result or silence indicator.
        """
        # Determine how far back to set _last_tick
        hours_back = simulated_hours
        if hours_back <= 0 and hasattr(self.agent, '_last_active'):
            hours_back = (time.time() - self.agent._last_active) / 3600
        if hours_back <= 0:
            hours_back = 4  # Fallback: simulate 4h gap

        # Set metabolism._last_tick to simulate N hours of silence
        self.agent.metabolism._last_tick = time.time() - hours_back * 3600

        result = await self.agent.proactive_tick()
        snap = self.snapshot()
        if result is not None:
            return {
                **snap,
                "proactive_fired": True,
                "proactive_reply": result.get('reply', ''),
                "proactive_modality": result.get('modality', '文字'),
                "proactive_monologue": result.get('monologue', ''),
                "proactive_drive": result.get('drive_id', ''),
            }
        else:
            return {
                **snap,
                "proactive_fired": False,
                "proactive_reason": "no impulse or chose silence",
            }

    # ── Memory Injection ──

    async def inject_memory(self, content: str, category: str = "preference") -> dict:
        """Plant a memory for later recall — dual-path for demo reliability.

        Path 1: POST to EverMemOS for long-term storage (async processing)
        Path 2: Immediately inject into agent._user_profile so it appears
                 in the very next prompt without waiting for EverMemOS indexing.

        Does NOT modify core engine — just sets existing public fields.
        """
        import uuid as _uuid
        import time as _time

        result = {"injected": False, "content": content, "category": category}

        # ── Path 2: Immediate prompt injection (always works) ──
        label = {"preference": "偏好", "fact": "事实", "episode": "经历"}.get(category, category)
        inject_text = f"{label}: {content}"
        current = getattr(self.agent, '_user_profile', '') or ''
        if inject_text not in current:
            self.agent._user_profile = (current + f"\n{inject_text}").strip()
            result["injected"] = True
            print(f"  [demo] 💾 memory → _user_profile: {inject_text}", flush=True)

        # ── Path 1: EverMemOS long-term storage (best effort) ──
        evermemos = self.agent.evermemos
        if evermemos and evermemos.available and evermemos._client:
            try:
                now_iso = _time.strftime("%Y-%m-%dT%H:%M:%S+08:00", _time.localtime())
                group_id = getattr(self.agent, '_group_id', 'demo')
                resp = await evermemos._client.post("/memories", json={
                    "content": f"[demo注入-{category}] {content}",
                    "create_time": now_iso,
                    "message_id": str(_uuid.uuid4()),
                    "sender": getattr(self.agent, 'user_id', 'demo_user'),
                    "sender_name": getattr(self.agent, 'user_name', '演示者'),
                    "role": "user",
                    "group_id": group_id,
                    "flush": True,
                })
                if resp.status_code in (200, 202):
                    print(f"  [demo] 💾 EverMemOS stored: HTTP {resp.status_code}", flush=True)
                else:
                    print(f"  [demo] ⚠️ EverMemOS store HTTP {resp.status_code}", flush=True)
            except Exception as e:
                print(f"  [demo] ⚠️ EverMemOS store failed: {e}", flush=True)

        return result

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
        hours_since = 0
        if hasattr(self.agent, '_last_active') and self.agent._last_active > 0:
            hours_since = (time.time() - self.agent._last_active) / 3600

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
            "hours_since_active": round(hours_since, 1),
        }
