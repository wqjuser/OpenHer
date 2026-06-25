"""
ChatAgent — Genome v10 Hybrid lifecycle-powered conversational agent.

Per-turn lifecycle (with EverMemOS async memory):
  0.  EverMemOS session context (first turn only: async load profile)
  1.  Time metabolism (DriveMetabolism)
  2.  Critic perception (LLM → 8D context + frustration delta + relationship delta)
  2.5 Semi-emergent relationship update:
       posterior = clip(prior + LLM_delta)
       alpha = clip(0.15 + 0.5*depth, 0.15, 0.65)
       ema_state = alpha*posterior + (1-alpha)*prev
  3.  LLM metabolism (apply frustration delta → reward)
  3.5 Critic-driven Drive baseline evolution (BASELINE_LR=0.01, every turn)
       frustration_delta > 0 → drive not satisfied → baseline rises
       frustration_delta < 0 → drive satisfied → baseline eases
       No math formula. Purely LLM-judged, same structure as Hebbian learning.
  4.  Crystallization gate (composite score: reward + novelty×engagement + conflict penalty)
  5.  Compute signals (Agent neural network, 12D context)
  6.  Thermodynamic noise injection
  7.  KNN retrieval (ContinuousStyleMemory)
  8.  Build Actor prompt (persona + signals + few-shot)
  8.5 Profile/Episode memory injection (user facts + narrative)
  9.  LLM Actor (generate response with monologue + reply)
  10. Hebbian learning (Agent.step)
  11. EverMemOS store_turn → asyncio.create_task (non-blocking)
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from typing import AsyncIterator, Optional

from providers.llm.client import LLMClient, ChatMessage, ChatResponse
from persona.loader import Persona
from engine.genome.genome_engine import Agent
from engine.genome.drive_metabolism import DriveMetabolism
from engine.genome.style_memory import ContinuousStyleMemory
from memory.memory_store import MemoryStore

# Mixin modules (extracted from this file)
from agent.prompt_builder import PromptBuilderMixin
from agent.task_skills import AgentTaskSkillMixin
from agent.turn_state import AgentTurnStateMixin
from agent.critic_context import AgentCriticContextMixin
from agent.actor_messages import AgentActorMessagesMixin
from agent.turn_pipeline import AgentTurnPipelineMixin
from agent.drive_lifecycle import AgentDriveLifecycleMixin
from agent.turn_finalization import AgentTurnFinalizationMixin
from agent.evermemos_mixin import EverMemosMixin
from agent.relationship import AgentRelationshipMixin
from agent.memory_injection import MemoryInjectionMixin
from agent.status import AgentStatusMixin
from agent.modality_execution import ModalityExecutionMixin
from agent.response_runtime import AgentResponseRuntimeMixin
from agent.modality_retry import ModalityRetryMixin
from agent.proactive import ProactiveMixin




class ChatAgent(
    PromptBuilderMixin,
    AgentTaskSkillMixin,
    AgentTurnStateMixin,
    AgentCriticContextMixin,
    AgentActorMessagesMixin,
    AgentTurnPipelineMixin,
    AgentDriveLifecycleMixin,
    AgentTurnFinalizationMixin,
    EverMemosMixin,
    AgentRelationshipMixin,
    MemoryInjectionMixin,
    AgentStatusMixin,
    ModalityExecutionMixin,
    AgentResponseRuntimeMixin,
    ModalityRetryMixin,
    ProactiveMixin,
):
    """
    Genome v8 lifecycle-powered persona chat agent.

    Each instance represents one user ↔ persona conversation session,
    backed by a living personality engine (Agent + DriveMetabolism +
    ContinuousStyleMemory).
    """

    def __init__(
        self,
        persona: Persona,
        llm: LLMClient,
        user_id: str = "default_user",
        user_name: Optional[str] = None,
        task_skill_engine=None,
        modality_skill_engine=None,
        skills_prompt: Optional[str] = None,
        skill_engine=None,
        memory_store: Optional[MemoryStore] = None,
        genome_seed: int = 42,
        genome_data_dir: Optional[str] = None,
        max_history: int = 40,
        evermemos=None,
        task_log_store=None,
    ):
        self.persona = persona
        self.llm = llm
        self.user_id = user_id
        self.user_name = user_name
        self._client_id: Optional[str] = None
        # Dual skill engines (isolated)
        self.task_skill_engine = task_skill_engine or skill_engine  # backward compat
        self.modality_skill_engine = modality_skill_engine
        self.skills_prompt = skills_prompt or ""
        self.task_log_store = task_log_store

        self.memory_store = memory_store
        self.max_history = max_history

        # ── Genome v8 Engine (with per-persona params) ──
        engine_params = persona.engine_params
        self.agent = Agent(seed=genome_seed, engine_params=engine_params)
        self.metabolism = DriveMetabolism(engine_params=engine_params)

        # Per-persona tunable parameters (with defaults)
        self.baseline_lr = engine_params.get('baseline_lr', 0.01)
        self.elasticity = engine_params.get('elasticity', 0.05)
        self.crystal_threshold = engine_params.get('crystal_threshold', 0.50)
        self.trend_delta = engine_params.get('trend_delta', 0.15)

        # Apply persona-specific genome seed (initial conditions only)
        if persona.drive_baseline:
            for d, v in persona.drive_baseline.items():
                if d in self.agent.drive_baseline:
                    self.agent.drive_baseline[d] = float(v)
                    self.agent.drive_state[d] = float(v)

        # Snapshot initial baseline for elastic pullback (persona gravity)
        self._initial_baseline = dict(self.agent.drive_baseline)

        self.style_memory = ContinuousStyleMemory(
            agent_id=f"{persona.persona_id}_{user_id}",
            db_dir=genome_data_dir,
            persona_id=persona.persona_id,
            hawking_gamma=engine_params.get('hawking_gamma'),
        )

        # ── Conversation state ──
        self.history: list[ChatMessage] = []
        self._turn_count: int = 0
        self._last_action: Optional[dict] = None
        self._last_critic: Optional[dict] = None
        self._last_signals: Optional[dict] = None
        self._prev_signals: Optional[dict] = None  # Previous turn signals for trend injection
        self._last_reward: float = 0.0
        self._last_modality: str = ""
        self._skill_outputs: dict = {}  # all modality skill results, reset per turn
        self._last_drive_satisfaction: dict = {}
        # ── Concurrency lock (R2: serialize chat/stream/proactive_tick) ──
        self._turn_lock = asyncio.Lock()

        # ── Proactive tick state ──
        self._last_active: float = time.time()
        self._state_version: int = 0
        self._interaction_cadence: float = 0.0  # EMA of interaction interval (seconds)

        # ── EverMemOS Async Memory ──
        self.evermemos = evermemos
        self.evermemos_uid = f"{user_id}__{persona.persona_id}"  # sender for user messages in store
        self._group_id = f"{persona.persona_id}__{user_id}"  # group_id scopes per user-persona pair
        self._user_profile: str = ""
        self._episode_summary: str = ""   # Narrative history for Critic + Actor
        self._session_ctx = None   # SessionContext loaded on first turn

        # ── Phase 1 Emergence: Relationship EMA state ──
        self._relationship_ema: dict = {}  # Populated on first turn from prior

        # ── Phase 3: Query-based relevance retrieval ──
        self._relevant_facts: str = ""      # Populated by async search from previous turn
        self._relevant_episodes: str = ""   # Populated by async search from previous turn
        self._relevant_profile: str = ""    # P1: Profile attrs from search
        self._foresight_text: str = ""      # P1: Foresight content from session context
        self._search_task: Optional[asyncio.Task] = None  # Tracks background search
        self._search_turn_id: int = 0       # Turn that fired the search (concurrency guard)
        self._search_hit: int = 0           # Observability: successful search collections
        self._search_timeout: int = 0       # Observability: timeout fallbacks
        self._search_fallback: int = 0      # Observability: turns that used static (per-turn)
        self._search_relevant_used: int = 0 # Observability: turns that injected relevant
        self._turn_used_fallback: bool = False  # Per-turn flag, reset each turn

        evermemos_status = "ON" if (evermemos and evermemos.available) else "OFF"
        m = self.metabolism
        print(f"✓ ChatAgent(Genome v10+EverMemOS) 初始化: {persona.name} ↔ {user_name or user_id} "
              f"(seed={genome_seed}, memories={self.style_memory.total_memories}, evermemos={evermemos_status})")
        print(f"  [metabolism] conn_k={m.connection_hunger_k}, nov_k={m.novelty_hunger_k}, "
              f"decay={m.decay_lambda}, temp_coeff={m.temp_coeff}, temp_floor={m.temp_floor}")


    def pre_warm(self, scenarios: list | None = None, steps_per_scenario: int = 20) -> None:
        """
        Pre-warm the Agent's neural network via simulated scenario steps.

        Call this ONCE on brand-new agents (before any real conversation).
        Restored agents already have shaped weights — calling this again
        would corrupt their evolved personality; always guard with age check:

            if agent.agent.age == 0:
                agent.pre_warm()

        Args:
            scenarios:           Scenario sequence; defaults to V10 standard 3-phase.
            steps_per_scenario:  Steps per scenario (default 20 → 60 total).
        """
        from engine.genome.genome_engine import simulate_conversation, DRIVES
        if scenarios is None:
            scenarios = ['分享喜悦', '吵架冲突', '深夜心事']
        simulate_conversation(self.agent, scenarios, steps_per_scenario=steps_per_scenario)

        # Reset drive_state to baseline after pre_warm.
        # Pre_warm shaped the NN weights (W1/W2) — that's its real job.
        # The saturated drive_state (all → ~1.0) is a side effect of 60 steps
        # of positive-biased rewards and must not leak into real conversation.
        for d in DRIVES:
            self.agent.drive_state[d] = self.agent.drive_baseline[d]
        self.agent._frustration = 0.0



    # ── Prompt building, memory blending, crystallization ──
    # See agent/prompt_builder.py (PromptBuilderMixin)

    async def chat(self, user_message: str, on_feel_done=None, is_proactive: bool = False) -> dict:
        """
        Process a user message through the full Genome v10 lifecycle.
        Returns only the reply (monologue is stored internally).
        on_feel_done: optional async callback invoked when prompt is ready (before LLM call).
        is_proactive: if True, this is a self-driven message — skip user memory/history storage.
        """
        async with self._turn_lock:
            return await self._chat_inner(user_message, on_feel_done=on_feel_done, is_proactive=is_proactive)

    async def _chat_inner(self, user_message: str, on_feel_done=None, is_proactive: bool = False) -> dict:
        """Inner chat implementation (called under lock)."""
        # ── Step -1-8.5: Shared pre-Actor turn lifecycle ──
        prepared_turn = await self._prepare_turn_for_actor(user_message)
        user_message = prepared_turn.user_message
        context = prepared_turn.context
        drive_satisfaction = prepared_turn.drive_satisfaction
        reward = prepared_turn.reward
        single_messages = prepared_turn.actor_messages

        # Notify caller that prompt is built (typing indicator can start)
        if on_feel_done:
            await on_feel_done()

        single_response = await self.llm.chat(single_messages)
        completed_response = await self._complete_actor_response(
            user_message,
            single_response.content,
            context,
            drive_satisfaction,
            reward,
            is_proactive=is_proactive,
        )

        result = {
            "reply": completed_response.reply,
            "modality": completed_response.modality,
        }
        for key in ('image_path', 'audio_path', 'segments', 'delays_ms'):
            if completed_response.outputs.get(key):
                result[key] = completed_response.outputs[key]
        return result

    # _express_wrap removed — SKILL results now injected into user_message
    # and processed through the full persona engine (Single-Pass Actor).

    async def chat_stream(self, user_message: str) -> AsyncIterator[str]:
        """
        Stream a response through the Genome v10 lifecycle.
        Steps 1-8 run first (Critic, metabolism, KNN), then Actor streams.
        """
        await self._turn_lock.acquire()
        try:
            # ── Step -1-8.5: Shared pre-Actor turn lifecycle ──
            prepared_turn = await self._prepare_turn_for_actor(user_message)
            user_message = prepared_turn.user_message
            context = prepared_turn.context
            drive_satisfaction = prepared_turn.drive_satisfaction
            reward = prepared_turn.reward
            single_messages = prepared_turn.actor_messages

            # Signal to stream consumer that prompt is ready → "typing" can start
            yield "__FEEL_DONE__"

            full_response = []
            async for chunk in self.llm.chat_stream(single_messages):
                full_response.append(chunk)
                yield chunk

            # ── Post-stream processing ──
            raw_text = "".join(full_response)
            await self._complete_actor_response(
                user_message,
                raw_text,
                context,
                drive_satisfaction,
                reward,
            )
        finally:
            self._turn_lock.release()


    # ── EverMemOS integration ──
    # See agent/evermemos_mixin.py (EverMemosMixin)

    # ── Modality failure with retry ──
    # See agent/modality_retry.py (ModalityRetryMixin)



    # ── Proactive Tick ──
    # See agent/proactive.py (ProactiveMixin)
