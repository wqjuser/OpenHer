"""ChatAgent construction and hydration for server sessions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from agent.chat_agent import ChatAgent
from agent.skills import ModalitySkillEngine, TaskSkillEngine
from engine.state_store import StateStore
from memory.memory_store import MemoryStore
from persona import PersonaLoader
from providers.llm import LLMClient
from providers.memory.evermemos.evermemos_client import EverMemOSClient


class SessionAgentFactory:
    """Creates hydrated ChatAgent instances for new server sessions."""

    def __init__(
        self,
        *,
        persona_loader: PersonaLoader,
        llm_client: LLMClient,
        task_skill_engine: TaskSkillEngine,
        modality_skill_engine: ModalitySkillEngine,
        memory_store: MemoryStore,
        state_store: Optional[StateStore],
        evermemos: Optional[EverMemOSClient],
        genome_data_dir: str,
        agent_factory: Callable[..., Any] = ChatAgent,
    ):
        self.persona_loader = persona_loader
        self.llm_client = llm_client
        self.task_skill_engine = task_skill_engine
        self.modality_skill_engine = modality_skill_engine
        self.memory_store = memory_store
        self.state_store = state_store
        self.evermemos = evermemos
        self.genome_data_dir = genome_data_dir
        self.agent_factory = agent_factory

    def create(
        self,
        *,
        session_id: str,
        persona_id: str,
        user_name: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> Any:
        """Create a ChatAgent and hydrate persisted runtime state when available."""
        persona = self.persona_loader.get(persona_id)
        if not persona:
            raise ValueError(f"角色 '{persona_id}' 不存在")

        genome_seed = hash(persona_id) % 100000
        stable_user_id = user_name if user_name else session_id

        agent = self.agent_factory(
            persona=persona,
            llm=self.llm_client,
            user_id=stable_user_id,
            user_name=user_name,
            skills_prompt=None,
            task_skill_engine=self.task_skill_engine,
            modality_skill_engine=self.modality_skill_engine,
            memory_store=self.memory_store,
            genome_seed=genome_seed,
            genome_data_dir=self.genome_data_dir,
            evermemos=self.evermemos,
        )
        agent._client_id = client_id

        is_new_agent = True
        if self.state_store:
            saved_agent, saved_metabolism = self.state_store.load_session(stable_user_id, persona_id)
            if saved_agent:
                agent.agent = saved_agent
                is_new_agent = False
                print(f"  ↳ 恢复 Agent: age={saved_agent.age}, interactions={saved_agent.interaction_count}")
            if saved_metabolism:
                agent.metabolism = saved_metabolism
                print(f"  ↳ 恢复代谢: total_frustration={saved_metabolism.total():.2f}")
            last_active, cadence, state_version = self.state_store.load_proactive_meta(stable_user_id, persona_id)
            if last_active > 0:
                agent._last_active = last_active
                agent._interaction_cadence = cadence
                agent._state_version = state_version
                print(f"  ↳ 恢复 proactive: last_active={last_active:.0f}, cadence={cadence:.0f}s, v={state_version}")

        if is_new_agent:
            agent.pre_warm()
            print(f"  ↳ 新 Agent 预热: 60步完成 (seed={genome_seed})")

        return agent
