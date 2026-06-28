"""In-memory chat session lifecycle management for the FastAPI server."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Optional

from engine.state_store import StateStore
from providers.memory.evermemos.evermemos_client import EverMemOSClient
from server.session_agent_factory import SessionAgentFactory


class SessionManager:
    """Owns active ChatAgent sessions and their persisted runtime state."""

    def __init__(
        self,
        *,
        agent_factory: SessionAgentFactory,
        state_store: Optional[StateStore],
        evermemos: Optional[EverMemOSClient],
        ttl_seconds: int = 30 * 60,
    ):
        self.agent_factory = agent_factory
        self.state_store = state_store
        self.evermemos = evermemos
        self.ttl_seconds = ttl_seconds
        self.sessions: dict[str, tuple[Any, float]] = {}

    @property
    def active_count(self) -> int:
        return len(self.sessions)

    def get_entry(self, session_id: str) -> Optional[tuple[Any, float]]:
        return self.sessions.get(session_id)

    def active_agents(self) -> list[Any]:
        return [agent for agent, _ in self.sessions.values()]

    def persist_agent(self, agent: Any) -> None:
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
    ) -> tuple[str, Any]:
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
        agent = self.agent_factory.create(
            session_id=sid,
            persona_id=persona_id,
            user_name=user_name,
            client_id=client_id,
        )

        self.sessions[sid] = (agent, now)
        return sid, agent

    def remove(self, session_id: str) -> None:
        """Persist and remove a session."""
        if session_id and session_id in self.sessions:
            agent, _ = self.sessions.pop(session_id)
            self.persist_agent(agent)
            print(f"  ↳ 会话 {session_id} 已保存并清理")
