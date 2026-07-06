"""Skill runtime service assembly for OpenHer startup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent.skills import ModalitySkillEngine, TaskSkillEngine
from agent.skills.tool_registry import ToolRegistry
from agent.skills.tools.photo_tools import register_photo_tools
from agent.skills.tools.split_tools import register_split_tools
from agent.skills.tools.voice_tools import register_voice_tools


@dataclass(frozen=True)
class SkillRuntimeServices:
    tool_registry: ToolRegistry
    task_skill_engine: TaskSkillEngine
    modality_skill_engine: ModalitySkillEngine
    task_loaded: dict[str, Any]
    modality_loaded: dict[str, Any]
    cron_skills: list[Any]
    messages: tuple[str, ...]


RegistryFactory = Callable[[], Any]
SkillEngineFactory = Callable[..., Any]
ToolRegistration = Callable[[Any], None]


def build_skill_runtime_services(
    base_dir: Path,
    *,
    voice_tools_enabled: bool,
    tool_registry_factory: RegistryFactory = ToolRegistry,
    task_skill_engine_factory: SkillEngineFactory = TaskSkillEngine,
    modality_skill_engine_factory: SkillEngineFactory = ModalitySkillEngine,
    register_photo_tools_fn: ToolRegistration = register_photo_tools,
    register_voice_tools_fn: ToolRegistration = register_voice_tools,
    register_split_tools_fn: ToolRegistration = register_split_tools,
) -> SkillRuntimeServices:
    tool_registry = tool_registry_factory()
    register_photo_tools_fn(tool_registry)
    if voice_tools_enabled:
        register_voice_tools_fn(tool_registry)
    register_split_tools_fn(tool_registry)

    task_skill_engine = task_skill_engine_factory(
        str(Path(base_dir) / "skills" / "task"),
        tool_registry=tool_registry,
    )
    task_loaded = task_skill_engine.load_all()

    modality_skill_engine = modality_skill_engine_factory(
        str(Path(base_dir) / "skills" / "modality"),
        tool_registry=tool_registry,
    )
    modality_loaded = modality_skill_engine.load_all()
    cron_skills = task_skill_engine.get_cron_skills()

    messages = (
        f"✓ 注册了 {len(tool_registry.tool_names)} 个工具: {tool_registry.tool_names}",
        f"✓ 加载了 {len(task_loaded)}+{len(modality_loaded)} 个技能 (task+modality), {len(cron_skills)} 个定时任务",
    )

    return SkillRuntimeServices(
        tool_registry=tool_registry,
        task_skill_engine=task_skill_engine,
        modality_skill_engine=modality_skill_engine,
        task_loaded=task_loaded,
        modality_loaded=modality_loaded,
        cron_skills=cron_skills,
        messages=messages,
    )
