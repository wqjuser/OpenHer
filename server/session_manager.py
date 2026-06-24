"""In-memory chat session lifecycle management for the FastAPI server."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Optional

from agent.chat_agent import ChatAgent
from agent.skills import ModalitySkillEngine, TaskSkillEngine
from engine.state_store import StateStore
from memory.memory_store import MemoryStore
from persona import PersonaLoader
from providers.llm import LLMClient
from providers.memory.evermemos.evermemos_client import EverMemOSClient


class SessionManager:
    """Owns active ChatAgent sessions and their persisted runtime state."""

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
        ttl_seconds: int = 30 * 60,
    ):
        self.persona_loader = persona_loader
        self.llm_client = llm_client
        self.task_skill_engine = task_skill_engine
        self.modality_skill_engine = modality_skill_engine
        self.memory_store = memory_store
        self.state_store = state_store
        self.evermemos = evermemos
        self.genome_data_dir = genome_data_dir
        self.ttl_seconds = ttl_seconds
        self.sessions: dict[str, tuple[ChatAgent, float]] = {}

    @property
    def active_count(self) -> int:
        return len(self.sessions)

    def get_entry(self, session_id: str) -> Optional[tuple[ChatAgent, float]]:
        return self.sessions.get(session_id)

    def active_agents(self) -> list[ChatAgent]:
        return [agent for agent, _ in self.sessions.values()]

    def persist_agent(self, agent: ChatAgent) -> None:
        """Save agent state via CAS with bootstrap fallback."""
        if not self.state_store:
            return

        agent_data = json.dumps(agent.agent.to_dict(), ensure_ascii=False)
        metabolism_data = json.dumps(agent.metabolism.to_dict(), ensure_ascii=False)

        ok = self.state_store.save_state(
            user_id=agent.user_id,
            persona_id=agent.persona.persona_id,
            agent_data=agent_data,
            metabolism_data=metabolism_data,
            last_active_at=agent._last_active,
            interaction_cadence=agent._interaction_cadence,
            expected_version=agent._state_version,
        )
        if ok:
            agent._state_version += 1
            return

        _, _, db_ver = self.state_store.load_proactive_meta(agent.user_id, agent.persona.persona_id)
        if db_ver == 0 and agent._state_version == 0:
            self.state_store.save_state(
                user_id=agent.user_id,
                persona_id=agent.persona.persona_id,
                agent_data=agent_data,
                metabolism_data=metabolism_data,
                last_active_at=agent._last_active,
                interaction_cadence=agent._interaction_cadence,
                expected_version=None,
            )
            _, _, actual_v = self.state_store.load_proactive_meta(agent.user_id, agent.persona.persona_id)
            agent._state_version = actual_v
        else:
            agent._state_version = db_ver
            print(f"  [persist] CAS conflict {agent.user_id}/{agent.persona.persona_id}, synced v={db_ver}")

    def persist_all(self) -> None:
        for agent in self.active_agents():
            self.persist_agent(agent)

    def cleanup_expired_sessions(self) -> int:
        """Remove sessions that have been inactive past the TTL."""
        now = time.time()
        expired = []
        for sid, (agent, last_active) in self.sessions.items():
            if now - last_active > self.ttl_seconds:
                self.persist_agent(agent)
                if self.evermemos and self.evermemos.available:
                    asyncio.create_task(
                        self.evermemos.close_session(
                            user_id=agent.evermemos_uid,
                            persona_id=agent.persona.persona_id,
                            group_id=agent._group_id,
                        )
                    )
                expired.append(sid)
        for sid in expired:
            del self.sessions[sid]
        return len(expired)

    def get_or_create(
        self,
        session_id: Optional[str],
        persona_id: str,
        user_name: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> tuple[str, ChatAgent]:
        """Get an existing session or create a new hydrated ChatAgent."""
        now = time.time()

        if session_id and session_id in self.sessions:
            agent, _ = self.sessions[session_id]
            self.sessions[session_id] = (agent, now)
            return session_id, agent

        if not session_id and client_id:
            for sid_candidate, (agent_candidate, _ts) in self.sessions.items():
                if (
                    hasattr(agent_candidate, "persona")
                    and agent_candidate.persona
                    and getattr(agent_candidate.persona, "persona_id", None) == persona_id
                    and getattr(agent_candidate, "_client_id", None) == client_id
                ):
                    print(f"  [session] ♻️ reusing session {sid_candidate} for {persona_id}/{client_id[:8]}")
                    self.sessions[sid_candidate] = (agent_candidate, now)
                    return sid_candidate, agent_candidate

        self.cleanup_expired_sessions()

        sid = session_id or str(uuid.uuid4())[:8]
        persona = self.persona_loader.get(persona_id)
        if not persona:
            raise ValueError(f"角色 '{persona_id}' 不存在")

        genome_seed = hash(persona_id) % 100000
        stable_user_id = user_name if user_name else sid

        agent = ChatAgent(
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

        self.sessions[sid] = (agent, now)
        return sid, agent

    def remove(self, session_id: str) -> None:
        """Persist and remove a session."""
        if session_id and session_id in self.sessions:
            agent, _ = self.sessions.pop(session_id)
            self.persist_agent(agent)
            print(f"  ↳ 会话 {session_id} 已保存并清理")
