from __future__ import annotations

from typing import Any, Protocol, cast


class _MemorySessionContext(Protocol):
    has_history: bool


class _MemoryPersona(Protocol):
    lang: str


class _MemoryInjectionHost(Protocol):
    _session_ctx: _MemorySessionContext | None
    persona: _MemoryPersona
    user_name: str | None
    _relevant_facts: str
    _user_profile: str
    _relevant_episodes: str
    _episode_summary: str
    _foresight_text: str
    _relevant_profile: str
    _search_relevant_used: int

    async def _collect_search_results(self) -> None:
        ...

    def _memory_injection_budget(self, context: dict) -> tuple[int, int]:
        ...

    def _blend_injection(self, relevant: str, static: str, budget: int) -> str:
        ...


def _append_section(sections: list[str], title: str, text: str) -> None:
    if text:
        sections.append(f"\n\n[{title}] {text}")


def _memory_sections(
    *,
    lang: str,
    name: str,
    profile_text: str,
    episode_text: str,
    foresight_text: str,
    relevant_profile: str,
) -> list[str]:
    sections: list[str] = []
    if lang == "en":
        _append_section(sections, f"{name}'s preferences", profile_text)
        _append_section(sections, f"Past interactions with {name}", episode_text)
        _append_section(sections, "Worth noting", foresight_text)
        _append_section(sections, f"{name}'s profile", relevant_profile)
    else:
        _append_section(sections, f"关于{name}的偏好", profile_text)
        _append_section(sections, f"与{name}过去发生的事", episode_text)
        _append_section(sections, "近期值得关心", foresight_text)
        _append_section(sections, f"{name}的画像", relevant_profile)
    return sections


class MemoryInjectionMixin:
    async def _inject_memory_context(self, prompt: str, context: dict[str, Any]) -> str:
        host = cast(_MemoryInjectionHost, self)
        if not host._session_ctx or not host._session_ctx.has_history:
            return prompt

        await host._collect_search_results()
        profile_budget, episode_budget = host._memory_injection_budget(context)
        profile_text = host._blend_injection(
            host._relevant_facts,
            host._user_profile,
            profile_budget,
        )
        episode_text = host._blend_injection(
            host._relevant_episodes,
            host._episode_summary,
            episode_budget,
        )
        name = host.user_name or "你"
        sections = _memory_sections(
            lang=host.persona.lang,
            name=name,
            profile_text=profile_text,
            episode_text=episode_text,
            foresight_text=host._foresight_text,
            relevant_profile=host._relevant_profile,
        )
        if host._relevant_facts or host._relevant_episodes or host._relevant_profile:
            host._search_relevant_used += 1
        return prompt + "".join(sections)
