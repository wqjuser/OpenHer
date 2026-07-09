"""
EverMemOS Client — 长期记忆适配器 (Async v4 — Self-Hosted)

v4 改进：
  P0 — 从 evermemos SDK (Cloud) 迁移到 httpx 直连 (Self-Hosted Open Source)
  沿用 v3 全部功能：config 集中管理、超时可配、失败熔断、命中率指标
  Foresight / Profile / RRF 检索逻辑不变

记忆涌现架构：
  1. 每轮对话结束后 → asyncio.create_task(store_turn(...)) 后台存储
  2. EverMemOS 自动提取 Episode / EventLog(atomic_fact) / Profile / Foresight
  3. Session 开始时拉取 Profile + Foresight 文本 → 注入 Critic + Actor
  4. 每轮 RRF 检索：event_log + episodic_memory + profile → 注入 Actor
  5. Session 结束时 flush → 触发边界提取

API 变化 (Cloud → Self-Hosted):
  - Base URL:  api.evermind.ai/api/v0 → localhost:1995/api/v1
  - Auth:      Bearer token → 无需 (local)
  - SDK:       evermemos.AsyncEverMemOS → httpx.AsyncClient
  - 接口字段完全兼容，仅 URL path 不同
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING, Optional

try:
    import httpx
except ImportError:
    httpx = None

from providers.memory.evermemos.circuit_breaker import _CircuitBreaker, _NoOpBreaker
from providers.memory.evermemos.config import _CFG, _fmt_latency, _load_memory_config
from providers.memory.evermemos.projection import (
    build_relevant_memory_projection,
    build_session_context_from_memories,
    empty_session_context,
    extract_search_memories,
    flatten_memory_results,
    relationship_vector_from_context,
)
from providers.memory.evermemos.protocol import (
    GET_PATHS,
    STORE_PATHS,
    build_cloud_search_body,
    build_compat_get_body,
    build_health_search_body,
    build_legacy_memory_payload,
    build_legacy_search_body,
    build_memory_flush_body,
    build_memory_batch_body,
    build_oss_health_search_body,
    build_oss_search_body,
    build_proactive_messages,
    build_session_flush_messages,
    build_turn_messages,
    build_v1_get_body,
    normalize_search_method,
    search_top_k,
)
from providers.memory.evermemos.types import SessionContext

if TYPE_CHECKING:
    import httpx as httpx_types


# ─────────────────────────────────────────────────────────────
# Main Client
# ─────────────────────────────────────────────────────────────

class EverMemOSClient:
    """
    Async EverMemOS adapter for OpenHer (Self-Hosted — httpx).

    All public methods are async. Use asyncio.create_task() for fire-and-forget
    storage operations to avoid blocking the main conversation flow.

    v4: Uses httpx.AsyncClient to call EverMemOS open-source REST API
    directly (localhost:1995/api/v1) instead of evermemos SDK cloud calls.
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self._base_url = (
            base_url
            or os.environ.get("EVERMEMOS_BASE_URL")
            or os.environ.get("MEMORY_BASE_URL")
            or _CFG.get("base_url")
            or "http://localhost:1995/api/v1"
        )
        # Normalize: strip trailing slash, ensure /api/v1 suffix
        self._base_url = self._base_url.rstrip("/")
        if not self._base_url.endswith("/api/v1"):
            # If user provides "http://localhost:1995", auto-append
            if "/api/" not in self._base_url:
                self._base_url += "/api/v1"

        # Optional API key (for cloud fallback or authenticated setups)
        self._api_key = api_key or os.environ.get("EVERMEMOS_API_KEY") or os.environ.get("MEMORY_API_KEY")

        self._client: Optional["httpx_types.AsyncClient"] = None
        self._initialized = False

        # Circuit breaker
        cb_enabled = _CFG.get("circuit_breaker_enabled", True)
        if cb_enabled:
            self._cb = _CircuitBreaker(
                threshold=_CFG["failure_threshold"],
                recovery_sec=_CFG["recovery_timeout_sec"],
            )
        else:
            self._cb = _NoOpBreaker()

        if not _CFG.get("enabled", True):
            print("⚠ EverMemOS disabled via config")
            return

        if httpx is None:
            print("⚠ httpx not installed (pip install httpx)")
            return

        try:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=10.0,
                trust_env=False,  # Bypass system/mac proxy for localhost
            )
            self._initialized = True
            print(f"✓ EverMemOS client initialized (base_url={self._base_url}, retrieve_method={_CFG['retrieve_method']})")
        except Exception as e:
            print(f"⚠ EverMemOS init failed: {e}")

    async def verify_connection(self) -> bool:
        """Validate API key by making a lightweight request.
        Call at server startup to fail fast on auth errors.
        Returns True if connection is valid, False otherwise.
        """
        if not self._initialized or not self._client:
            return False
        try:
            resp = await self._client.request(
                "POST",
                "/memories/search",
                json=build_health_search_body(),
                timeout=8.0,
            )
            if resp.status_code in (404, 405):
                resp = await self._client.request(
                    "POST",
                    "/memory/search",
                    json=build_oss_health_search_body(),
                    timeout=8.0,
                )
            if resp.status_code == 401:
                print(
                    "✗ EverMemOS API key 无效 (HTTP 401) — "
                    "请检查 .env 中的 EVERMEMOS_API_KEY 或 MEMORY_API_KEY"
                )
                self._initialized = False
                return False
            if resp.status_code == 200:
                print(f"  ↳ EverMemOS API key 验证通过 ✓")
                return True
            # Other status codes (e.g. 500) — warn but don't disable
            print(f"  ↳ EverMemOS health check: HTTP {resp.status_code} (non-fatal)")
            return True
        except Exception as e:
            print(f"  ↳ EverMemOS health check failed: {e} (non-fatal)")
            return True  # Network issue, don't disable — might be transient

    @property
    def available(self) -> bool:
        return self._initialized and self._client is not None and not self._cb.is_open

    async def _post_memories(
        self,
        user_id: str,
        group_id: str,
        messages: list[dict],
        label: str,
        flush_after: bool = False,
    ) -> bool:
        """Post memories using the cloud batch shape, with legacy flat fallback."""
        if not self._client:
            return False

        body = build_memory_batch_body(user_id, group_id, messages)

        last_resp = None
        success_path = ""
        for path in STORE_PATHS:
            resp = await self._client.post(path, json=body)
            last_resp = resp
            print(f"  [evermemos] POST {label} {path}: HTTP {resp.status_code} gid={group_id}")
            if resp.status_code in (200, 201, 202):
                success_path = path
                break
            if resp.status_code != 404:
                break

        if success_path:
            if flush_after and success_path == "/memory/add":
                flush_resp = await self._client.post(
                    "/memory/flush",
                    json=build_memory_flush_body(user_id, group_id),
                )
                print(f"  [evermemos] POST {label} /memory/flush: HTTP {flush_resp.status_code} gid={group_id}")
            self._cb.record_success()
            return True

        failure_text = last_resp.text[:200] if last_resp is not None else "no response"
        print(f"  [evermemos] store {label} batch failed: {failure_text}")

        # Older self-hosted builds accepted one flat message per POST.
        for index, message in enumerate(messages):
            legacy_payload = build_legacy_memory_payload(
                user_id=user_id,
                group_id=group_id,
                message=message,
                flush=flush_after and index == len(messages) - 1,
            )
            legacy_resp = await self._client.post("/memories", json=legacy_payload)
            print(
                f"  [evermemos] POST {label} legacy {message.get('role', 'message')}: "
                f"HTTP {legacy_resp.status_code} gid={group_id} sender={message.get('sender_id')}"
            )
            if legacy_resp.status_code not in (200, 201, 202):
                print(f"  [evermemos] store {label} legacy failed: {legacy_resp.text[:200]}")
                self._cb.record_failure()
                return False

        self._cb.record_success()
        return True

    async def _request_json_candidates(
        self,
        method: str,
        paths: tuple[str, ...],
        body: dict,
        timeout: float,
    ):
        """Try equivalent EverMemOS/EverOS routes and return the first response."""
        if not self._client:
            return None
        client = self._client
        last_resp = None
        for path in paths:
            resp = await client.request(method, path, json=body, timeout=timeout)
            last_resp = resp
            if resp.status_code == 200:
                return resp
            if resp.status_code not in (404, 405):
                return resp
        return last_resp

    # ─────────────────────────────────────────────────────────────
    # Session Lifecycle
    # ─────────────────────────────────────────────────────────────

    async def load_session_context(
        self,
        user_id: str,
        persona_id: str,
        group_id: str = "",
    ) -> SessionContext:
        """
        Called once at session start. Pulls user profile + episodes + foresight
        content from EverMemOS and builds a SessionContext for use throughout
        the session.

        Returns a zero-context SessionContext if unavailable or error.
        """
        empty = empty_session_context()

        if not self.available:
            return empty
        if not self._client:
            return empty
        client = self._client

        t0 = time.monotonic()
        try:
            timeout = _CFG["load_timeout_sec"]

            async def _get_type(mtype: str):
                try:
                    v1_type = {
                        "profile": "profile",
                        "episodic_memory": "episode",
                    }.get(mtype)
                    if v1_type:
                        resp = await self._request_json_candidates(
                            "POST",
                            GET_PATHS,
                            build_v1_get_body(user_id, v1_type),
                            timeout,
                        )
                        if resp and resp.status_code == 200:
                            data = resp.json().get("data", {})
                            key = "profiles" if v1_type == "profile" else "episodes"
                            return {"result": {"memories": data.get(key, [])}}
                        if resp and resp.status_code in (404, 405):
                            resp = await client.request(
                                "POST",
                                "/memories/get",
                                json=build_compat_get_body(user_id, mtype),
                                timeout=timeout,
                            )
                            if resp.status_code == 200:
                                data = resp.json().get("data", {})
                                key = "profiles" if mtype == "profile" else "episodes"
                                return {"result": {"memories": data.get(key, [])}}
                        return None

                    body: dict[str, object] = {"memory_type": mtype, "user_id": user_id}
                    if group_id:
                        body["group_ids"] = [group_id]
                    resp = await client.request(
                        "GET", "/memories",
                        json=body,
                        timeout=timeout,
                    )
                    if resp.status_code == 200:
                        return resp.json()
                    return None
                except Exception:
                    return None

            results = await asyncio.gather(
                _get_type("profile"),
                _get_type("event_log"),
                _get_type("episodic_memory"),
                _get_type("foresight"),
            )

            all_memories = flatten_memory_results(results)

            if not all_memories:
                self._cb.record_success()
                return empty

            ctx = build_session_context_from_memories(all_memories, _CFG)
            self._cb.record_success()
            elapsed_ms = (time.monotonic() - t0) * 1000

            if ctx.has_history and _CFG["log_hit_rates"]:
                print(
                    f"  [evermemos] 📚 loaded{_fmt_latency(elapsed_ms)}: "
                    f"{ctx.interaction_count} interactions, depth={ctx.relationship_depth:.2f}, "
                    f"facts={ctx._fact_count}, profile={ctx._profile_count}, "
                    f"episodes={ctx._episode_count}, foresights={ctx._foresight_count}"
                    + (f" [foresight_text: {ctx.foresight_text[:40]}...]" if ctx.foresight_text else "")
                )

            return ctx

        except Exception as e:
            self._cb.record_failure()
            elapsed_ms = (time.monotonic() - t0) * 1000
            print(f"  [evermemos] load_session_context error{_fmt_latency(elapsed_ms)}: {e}")
            return empty

    async def store_turn(
        self,
        user_id: str,
        persona_id: str,
        persona_name: str,
        user_name: str,
        group_id: str,
        user_message: str,
        agent_reply: str,
    ) -> bool:
        """
        Store one conversation turn (user + agent messages) to EverMemOS.
        Called as asyncio.create_task — fire and forget, never blocks.

        EverMemOS automatically extracts Episodes, EventLogs (atomic facts),
        Profiles, and Foresights from stored messages.
        """
        if not self.available:
            return False

        now_ms = int(time.time() * 1000)

        try:
            return await self._post_memories(
                user_id=user_id,
                group_id=group_id,
                label="turn",
                flush_after=True,
                messages=build_turn_messages(
                    user_id=user_id,
                    persona_id=persona_id,
                    persona_name=persona_name,
                    user_name=user_name,
                    user_message=user_message,
                    agent_reply=agent_reply,
                    timestamp_ms=now_ms,
                ),
            )

        except Exception as e:
            self._cb.record_failure()
            print(f"  [evermemos] store_turn error: {e}")
            return False

    async def store_proactive_turn(
        self,
        user_id: str,
        persona_id: str,
        persona_name: str,
        group_id: str,
        reply: str,
        tick_id: str,
    ) -> None:
        """
        Store a proactive message (AI-initiated, no user_message).
        """
        if not self.available:
            return

        now_ms = int(time.time() * 1000)

        try:
            stored = await self._post_memories(
                user_id=user_id,
                group_id=group_id,
                label="proactive",
                flush_after=True,
                messages=build_proactive_messages(
                    persona_id=persona_id,
                    persona_name=persona_name,
                    reply=reply,
                    timestamp_ms=now_ms,
                ),
            )
            if stored:
                print(f"  [evermemos] stored proactive turn (tick={tick_id[:8]})")
        except Exception as e:
            self._cb.record_failure()
            print(f"  [evermemos] store_proactive error: {e}")

    async def close_session(
        self,
        user_id: str,
        persona_id: str,
        group_id: str,
    ) -> None:
        """
        Signal session end to EverMemOS (flush = boundary trigger).
        Forces memory extraction from buffered messages.
        """
        if not self.available:
            return

        try:
            flushed = await self._post_memories(
                user_id=user_id,
                group_id=group_id,
                label="session flush",
                flush_after=True,
                messages=build_session_flush_messages(
                    persona_id=persona_id,
                    timestamp_ms=int(time.time() * 1000),
                ),
            )
            if flushed:
                print(f"  [evermemos] 🔚 session flushed for {user_id}")
        except Exception as e:
            print(f"  [evermemos] close_session error: {e}")

    # ─────────────────────────────────────────────────────────────
    # Relationship Vector (for GenomeEngine 4D context)
    # ─────────────────────────────────────────────────────────────

    def relationship_vector(self, ctx: SessionContext) -> dict:
        """
        Build the 4D relationship PRIOR vector from SessionContext.
        These are deterministic priors; Critic provides deltas each turn.
        """
        return relationship_vector_from_context(ctx)

    # ─────────────────────────────────────────────────────────────
    # Query-Based Relevance Retrieval (Phase 3) — P1 enhanced
    # ─────────────────────────────────────────────────────────────

    async def search_relevant_memories(
        self,
        query: str,
        user_id: str,
        group_id: str = "",
    ) -> tuple[str, str, str]:
        """
        Search for memories most relevant to the current user message.

        P1 improvement: Also searches profile type and returns profile context.
        Uses retrieve_method from config (rrf / hybrid / agentic).

        Returns: (relevant_facts, relevant_episodes, relevant_profile)
                 Empty strings on error or no results.
        """
        if not self.available or not query.strip():
            return "", "", ""
        if not self._client:
            return "", "", ""
        client = self._client

        t0 = time.monotonic()
        retrieve_method = _CFG.get("retrieve_method", "rrf")

        # P2: Agentic rollout percentage
        agentic_pct = _CFG.get("agentic_rollout_pct", 0)
        if agentic_pct > 0:
            import random
            if random.randint(1, 100) <= agentic_pct:
                retrieve_method = "agentic"

        try:
            # EverMemOS cloud SDK shape:
            # memories.search(filters={...}, query=..., method=..., top_k=...)
            method = normalize_search_method(retrieve_method)
            top_k = search_top_k(_CFG)
            resp = await client.request(
                "POST",
                "/memories/search",
                json=build_cloud_search_body(query, user_id, method, top_k),
                timeout=_CFG["search_timeout_sec"],
            )

            if resp and resp.status_code in (404, 405):
                resp = await client.request(
                    "POST",
                    "/memory/search",
                    json=build_oss_search_body(query, user_id, group_id, method, top_k),
                    timeout=_CFG["search_timeout_sec"],
                )

            if resp and resp.status_code in (404, 405):
                resp = await client.request(
                    "GET",
                    "/memories/search",
                    json=build_legacy_search_body(query, user_id, group_id, retrieve_method),
                    timeout=_CFG["search_timeout_sec"],
                )

            elapsed_ms = (time.monotonic() - t0) * 1000

            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else "no-response"
                print(f"  [evermemos] 🔍 search: HTTP {status_code}{_fmt_latency(elapsed_ms)}")
                self._cb.record_success()
                return "", "", ""

            memories = extract_search_memories(resp.json())

            if not memories:
                print(f"  [evermemos] 🔍 search: 0 results{_fmt_latency(elapsed_ms)} [{retrieve_method}]")
                self._cb.record_success()
                return "", "", ""

            projection = build_relevant_memory_projection(memories, _CFG)

            self._cb.record_success()

            if _CFG["log_hit_rates"]:
                print(
                    f"  [evermemos] 🔍 search{_fmt_latency(elapsed_ms)} [{retrieve_method}]: "
                    f"facts={len(projection.facts)}, episodes={len(projection.episodes)}, "
                    f"profile={len(projection.profile_attrs)}"
                )

            return projection.as_tuple()

        except Exception as e:
            self._cb.record_failure()
            elapsed_ms = (time.monotonic() - t0) * 1000
            print(f"  [evermemos] 🔍 search error{_fmt_latency(elapsed_ms)}: {type(e).__name__}: {e}")
            return "", "", ""
