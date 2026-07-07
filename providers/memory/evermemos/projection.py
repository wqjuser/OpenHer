"""Pure projection helpers for EverMemOS response data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
import math

from providers.memory.evermemos.types import SessionContext


_PROFILE_SKIP_KEYS = {"id", "memory_type", "user_id", "user_name"}


@dataclass(frozen=True)
class RelevantMemoryProjection:
    facts: list[str]
    episodes: list[str]
    profile_attrs: list[str]

    def as_tuple(self) -> tuple[str, str, str]:
        return (
            "；".join(self.facts) if self.facts else "",
            "；".join(self.episodes) if self.episodes else "",
            "；".join(self.profile_attrs) if self.profile_attrs else "",
        )


def empty_session_context() -> SessionContext:
    return SessionContext(
        user_profile="",
        episode_summary="",
        foresight_text="",
        interaction_count=0,
        has_history=False,
        relationship_depth=0.0,
        pending_foresight=0.0,
    )


def flatten_memory_results(results: Iterable[Mapping[str, Any] | None]) -> list[Mapping[str, Any]]:
    memories: list[Mapping[str, Any]] = []
    for response_data in results:
        if not response_data:
            continue
        result = response_data.get("result")
        if not isinstance(result, Mapping):
            continue
        response_memories = result.get("memories")
        if isinstance(response_memories, list):
            memories.extend(item for item in response_memories if isinstance(item, Mapping))
    return memories


def build_session_context_from_memories(
    memories: Iterable[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> SessionContext:
    all_memories = list(memories)
    if not all_memories:
        return empty_session_context()

    profile_lines: list[str] = []
    fact_lines: list[str] = []
    episode_lines: list[str] = []
    foresight_lines: list[str] = []
    interaction_count = 0

    for memory in all_memories:
        if "profile_data" in memory:
            profile_data = memory.get("profile_data", {})
            if isinstance(profile_data, Mapping):
                profile_lines.extend(_profile_attrs(profile_data, None))
            interaction_count += int(memory.get("memcell_count", 0) or 0)
        elif "atomic_fact" in memory:
            fact = _clean_text(memory.get("atomic_fact"))
            if fact:
                fact_lines.append(fact)
        elif "episode_id" in memory or "summary" in memory:
            summary = _episode_summary(memory)
            if summary:
                episode_lines.append(summary)
        elif "foresight" in memory:
            foresight = _foresight_text(memory)
            if foresight:
                foresight_lines.append(foresight)

    if interaction_count == 0:
        interaction_count = len(all_memories)

    max_facts = int(config["facts_max_items"])
    max_profile = int(config["profile_max_items"])
    user_profile_parts = []
    if profile_lines:
        user_profile_parts.append("【用户画像】" + "；".join(profile_lines[:max_profile]))
    if fact_lines:
        user_profile_parts.append("【已知偏好/事实】" + "；".join(fact_lines[:max_facts]))

    max_eps = int(config["episodes_max_items"])
    max_foresight = int(config["foresight_max_items"])
    max_foresight_chars = int(config.get("foresight_max_chars", 200))
    foresight_items = [text[:max_foresight_chars] for text in foresight_lines[:max_foresight]]

    data_richness = (
        len(fact_lines) * 2
        + len(profile_lines) * 3
        + len(episode_lines) * 5
    )
    depth = 1.0 - math.exp(-data_richness / 30.0) if data_richness > 0 else 0.0
    if data_richness == 0 and interaction_count > 0:
        depth = 1.0 - math.exp(-interaction_count / 40.0)

    foresight_count = len(foresight_lines)
    pending_foresight = 1.0 - math.exp(-foresight_count / 1.5) if foresight_count > 0 else 0.0

    return SessionContext(
        user_profile="\n".join(user_profile_parts) if user_profile_parts else "",
        episode_summary="；".join(episode_lines[-max_eps:]) if episode_lines else "",
        foresight_text="；".join(foresight_items) if foresight_items else "",
        interaction_count=interaction_count,
        has_history=True,
        relationship_depth=round(depth, 3),
        pending_foresight=round(pending_foresight, 3),
        _fact_count=len(fact_lines),
        _profile_count=len(profile_lines),
        _episode_count=len(episode_lines),
        _foresight_count=foresight_count,
    )


def extract_search_memories(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if "data" not in data:
        result = data.get("result", {})
        if isinstance(result, Mapping):
            memories = result.get("memories", [])
            if isinstance(memories, list):
                return [item for item in memories if isinstance(item, Mapping)]
        return []

    search_data = data.get("data", {})
    if not isinstance(search_data, Mapping):
        return []

    memories: list[Mapping[str, Any]] = []
    episodes = search_data.get("episodes", []) or []
    profiles = search_data.get("profiles", []) or []
    if isinstance(episodes, list):
        memories.extend(item for item in episodes if isinstance(item, Mapping))
    if isinstance(profiles, list):
        memories.extend(item for item in profiles if isinstance(item, Mapping))
    for episode in episodes:
        if not isinstance(episode, Mapping):
            continue
        atomic_facts = episode.get("atomic_facts", []) or []
        if not isinstance(atomic_facts, list):
            continue
        for fact in atomic_facts:
            if not isinstance(fact, Mapping):
                continue
            fact_text = (
                fact.get("content")
                or fact.get("atomic_fact")
                or fact.get("text")
                or fact.get("fact")
            )
            fact_text = _clean_text(fact_text)
            if fact_text:
                memories.append({"atomic_fact": fact_text})
    return memories


def build_relevant_memory_projection(
    memories: Iterable[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> RelevantMemoryProjection:
    facts: list[str] = []
    episodes: list[str] = []
    profile_attrs: list[str] = []

    max_facts = int(config["facts_max_items"])
    max_episodes = int(config["episodes_max_items"])
    max_profile = int(config["profile_max_items"])

    for memory in memories:
        if "atomic_fact" in memory and len(facts) < max_facts:
            fact = _clean_text(memory.get("atomic_fact"))
            if fact:
                facts.append(fact)
        elif ("episode_id" in memory or "summary" in memory) and len(episodes) < max_episodes:
            summary = _episode_summary(memory)
            if summary:
                episodes.append(summary)
        elif "profile_data" in memory and len(profile_attrs) < max_profile:
            profile_data = memory.get("profile_data", {})
            if isinstance(profile_data, Mapping):
                profile_attrs.extend(_profile_attrs(profile_data, max_profile - len(profile_attrs)))

    return RelevantMemoryProjection(
        facts=facts,
        episodes=episodes,
        profile_attrs=profile_attrs,
    )


def relationship_vector_from_context(ctx: SessionContext) -> dict[str, float]:
    trust = 1.0 - math.exp(-ctx.interaction_count / 40.0) if ctx.interaction_count > 0 else 0.0
    return {
        "relationship_depth": round(ctx.relationship_depth, 3),
        "emotional_valence": 0.0,
        "trust_level": round(trust, 3),
        "pending_foresight": round(ctx.pending_foresight, 3),
    }


def _profile_attrs(profile_data: Mapping[str, Any], limit: int | None) -> list[str]:
    attrs: list[str] = []
    for key, value in profile_data.items():
        if key in _PROFILE_SKIP_KEYS:
            continue
        text = _clean_text(value)
        if not text:
            continue
        attrs.append(f"{key}: {text}")
        if limit is not None and len(attrs) >= limit:
            break
    return attrs


def _episode_summary(memory: Mapping[str, Any]) -> str:
    return _clean_text(
        memory.get("summary")
        or memory.get("narrative")
        or memory.get("content")
    )


def _foresight_text(memory: Mapping[str, Any]) -> str:
    return _clean_text(
        memory.get("content")
        or memory.get("foresight")
        or memory.get("prediction")
        or memory.get("summary")
    )


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()
