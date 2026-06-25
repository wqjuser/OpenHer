# pyright: reportAttributeAccessIssue=false
"""
EverMemosMixin — EverMemOS integration for ChatAgent.

Handles session context loading, background store/search, and search result
collection.
"""

from __future__ import annotations

import asyncio


class EverMemosMixin:
    """EverMemOS async memory integration methods."""

    async def _evermemos_gather(self) -> dict:
        """
        Step 0: Load EverMemOS session context (first turn only).
        Subsequent turns reuse cached _session_ctx.
        Returns relationship_4d dict for GenomeEngine context.
        """
        empty_4d = {
            'relationship_depth': 0.0,
            'emotional_valence': 0.0,
            'trust_level': 0.0,
            'pending_foresight': 0.0,
        }

        if not (self.evermemos and self.evermemos.available):
            return empty_4d

        # Load once per session
        if self._turn_count == 1:
            self._session_ctx = await self.evermemos.load_session_context(
                user_id=self.evermemos_uid,
                persona_id=self.persona.persona_id,
                group_id=self._group_id,
            )
            if self._session_ctx.user_profile:
                self._user_profile = self._session_ctx.user_profile
            if self._session_ctx.episode_summary:
                self._episode_summary = self._session_ctx.episode_summary
            # P1: Cache foresight text for Actor injection
            if self._session_ctx.foresight_text:
                self._foresight_text = self._session_ctx.foresight_text

        if not self._session_ctx:
            return empty_4d

        return self.evermemos.relationship_vector(self._session_ctx)

    def _evermemos_store_bg(self, user_message: str, reply: str) -> None:
        """Step 11: Fire-and-forget EverMemOS storage (asyncio.create_task)."""
        if not (self.evermemos and self.evermemos.available):
            return
        async def _do_store():
            try:
                stored = await self.evermemos.store_turn(
                    user_id=self.evermemos_uid,
                    persona_id=self.persona.persona_id,
                    persona_name=self.persona.name,
                    user_name=self.user_name or "用户",
                    group_id=self._group_id,
                    user_message=user_message,
                    agent_reply=reply,
                )
                if stored:
                    print(f"  [evermemos] ✅ stored turn (uid={self.evermemos_uid}, pid={self.persona.persona_id})")
                else:
                    print(f"  [evermemos] ⚠️ store skipped/failed (uid={self.evermemos_uid}, pid={self.persona.persona_id})")
            except Exception as e:
                print(f"  [evermemos] ❌ store failed: {type(e).__name__}: {e}")
        try:
            asyncio.create_task(_do_store())
        except Exception as e:
            print(f"  [evermemos] create_task error: {e}")

    def _evermemos_search_bg(self, user_message: str) -> None:
        """
        Step 12: Fire async RRF search for the current user_message.
        Results are collected at Step 8.5 of the NEXT turn.
        Cancels any pending search before starting a new one.
        """
        if not (self.evermemos and self.evermemos.available):
            return
        if not self._session_ctx or not self._session_ctx.has_history:
            return

        # Cancel any orphaned previous search task
        if self._search_task and not self._search_task.done():
            self._search_task.cancel()
            self._search_task = None

        try:
            self._search_turn_id = self._turn_count  # Tag with origin turn
            self._search_task = asyncio.create_task(
                self.evermemos.search_relevant_memories(
                    query=user_message,
                    user_id=self.evermemos_uid,
                    group_id=self._group_id,
                )
            )
        except Exception as e:
            print(f"  [evermemos] search create_task error: {e}")
            self._search_task = None

    async def _collect_search_results(self) -> None:
        """
        Collect previous turn's async search results (called at Step 8.5).
        Validates turn_id to prevent concurrent mismatch.
        Waits up to 0.5s; on timeout/error falls back to empty (static used).
        """
        if self._search_task is None:
            return

        # Concurrency guard: reject stale results from wrong turn
        expected_turn = self._turn_count - 1
        if self._search_turn_id != expected_turn:
            self._search_task.cancel()
            self._search_task = None
            self._relevant_facts = ""
            self._relevant_episodes = ""
            self._relevant_profile = ""   # P1a fix: was missing, caused stale profile injection
            return


        try:
            facts, episodes, profile = await asyncio.wait_for(
                self._search_task, timeout=0.5
            )
            self._relevant_facts = facts
            self._relevant_episodes = episodes
            self._relevant_profile = profile   # P1
            self._search_hit += 1
        except asyncio.TimeoutError:
            self._search_timeout += 1
            total = self._search_hit + self._search_timeout
            pct = self._search_timeout / total * 100 if total else 0
            print(f"  [evermemos] 🔍 search timeout (>500ms), "
                  f"static fallback ({self._search_timeout}/{total} = {pct:.0f}%)")
            self._relevant_facts = ""
            self._relevant_episodes = ""
            self._relevant_profile = ""
        except Exception as e:
            print(f"  [evermemos] 🔍 search collect error: {e}")
            self._relevant_facts = ""
            self._relevant_episodes = ""
            self._relevant_profile = ""
        finally:
            self._search_task = None
