"""Skill runtime assembly boundary tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FakeRegistry:
    def __init__(self) -> None:
        self.tool_names: list[str] = []

    def register_named(self, name: str) -> None:
        self.tool_names.append(name)


class FakeSkillEngine:
    def __init__(self, skills_dir: str, tool_registry: FakeRegistry) -> None:
        self.skills_dir = skills_dir
        self.tool_registry = tool_registry
        self.loaded = False

    def load_all(self) -> dict[str, str]:
        self.loaded = True
        directory_name = Path(self.skills_dir).name
        return {f"{directory_name}-skill": directory_name}

    def get_cron_skills(self) -> list[str]:
        return ["cron-weather"]


def test_skill_runtime_builds_registry_engines_and_cron_skills(tmp_path):
    from server.skill_runtime import build_skill_runtime_services

    registrations: list[str] = []

    def register_photo(registry: FakeRegistry) -> None:
        registrations.append("photo")
        registry.register_named("generate_photo")

    def register_voice(registry: FakeRegistry) -> None:
        registrations.append("voice")
        registry.register_named("synthesize_voice")

    def register_split(registry: FakeRegistry) -> None:
        registrations.append("split")
        registry.register_named("split_messages")

    runtime = build_skill_runtime_services(
        tmp_path,
        voice_tools_enabled=True,
        tool_registry_factory=FakeRegistry,
        task_skill_engine_factory=FakeSkillEngine,
        modality_skill_engine_factory=FakeSkillEngine,
        register_photo_tools_fn=register_photo,
        register_voice_tools_fn=register_voice,
        register_split_tools_fn=register_split,
    )

    assert registrations == ["photo", "voice", "split"]
    assert runtime.tool_registry.tool_names == [
        "generate_photo",
        "synthesize_voice",
        "split_messages",
    ]
    assert isinstance(runtime.task_skill_engine, FakeSkillEngine)
    assert isinstance(runtime.modality_skill_engine, FakeSkillEngine)
    assert runtime.task_skill_engine.skills_dir == str(tmp_path / "skills" / "task")
    assert runtime.modality_skill_engine.skills_dir == str(tmp_path / "skills" / "modality")
    assert runtime.task_loaded == {"task-skill": "task"}
    assert runtime.modality_loaded == {"modality-skill": "modality"}
    assert runtime.cron_skills == ["cron-weather"]
    assert runtime.messages == (
        "✓ 注册了 3 个工具: ['generate_photo', 'synthesize_voice', 'split_messages']",
        "✓ 加载了 1+1 个技能 (task+modality), 1 个定时任务",
    )


def test_skill_runtime_skips_voice_tools_when_tts_is_unavailable(tmp_path):
    from server.skill_runtime import build_skill_runtime_services

    registrations: list[str] = []

    def register_photo(registry: FakeRegistry) -> None:
        registrations.append("photo")
        registry.register_named("generate_photo")

    def register_voice(registry: FakeRegistry) -> None:
        registrations.append("voice")
        registry.register_named("synthesize_voice")

    def register_split(registry: FakeRegistry) -> None:
        registrations.append("split")
        registry.register_named("split_messages")

    runtime = build_skill_runtime_services(
        tmp_path,
        voice_tools_enabled=False,
        tool_registry_factory=FakeRegistry,
        task_skill_engine_factory=FakeSkillEngine,
        modality_skill_engine_factory=FakeSkillEngine,
        register_photo_tools_fn=register_photo,
        register_voice_tools_fn=register_voice,
        register_split_tools_fn=register_split,
    )

    assert registrations == ["photo", "split"]
    assert runtime.tool_registry.tool_names == ["generate_photo", "split_messages"]
