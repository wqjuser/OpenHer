"""
Shared types for the Skill subsystem.

Both TaskSkillEngine and ModalitySkillEngine import from here
to avoid cross-dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import frontmatter


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """Loaded skill definition (L1 metadata from SKILL.md frontmatter)."""
    skill_id: str
    name: str
    description: str = ""
    trigger: str = "manual"          # modality | tool | cron | manual
    modality: str = ""               # bound modality (e.g. "照片") for trigger:modality skills
    executor: str = "handler"        # handler | sandbox
    handler_fn: str = ""             # Python entry point (legacy, replaced by tools)
    tools: list[str] = field(default_factory=list)  # tool names this skill mounts
    resources: list[str] = field(default_factory=list)
    needs_chat_history: bool = False  # Skill declares if it needs chat history injected
    excludes: list[str] = field(default_factory=list)  # modalities that must be removed from plan when this skill is selected
    prompt_injection: str = ""
    base_dir: str = ""
    body: Optional[str] = None       # L2 instructions (lazy-loaded by activate())

    # deprecated — kept for backward compat
    handler: Optional[str] = None
    cron_schedule: Optional[str] = None
    requires: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def is_activated(self) -> bool:
        """L2 body has been loaded."""
        return self.body is not None


class ExecutionStatus(Enum):
    """Skill execution state machine."""
    COMPLETED = "completed"
    NEEDS_INFO = "needs_info"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"


@dataclass
class SkillExecutionResult:
    """Result of a skill execution."""
    skill_id: str
    success: bool
    status: ExecutionStatus
    output: dict
    next_skills: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public parsing function (used by both engines)
# ---------------------------------------------------------------------------

SKILL_FILENAME = "SKILL.md"


def _meta_str(value: object, default: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def _meta_optional_str(value: object) -> Optional[str]:
    return value if isinstance(value, str) else None


def _meta_bool(value: object, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _meta_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    return []


def load_skill(skill_dir: Path) -> Skill:
    """Parse SKILL.md frontmatter into Skill (L1 only, body=None).

    Extracted from the old SkillEngine._load_one() so both
    TaskSkillEngine and ModalitySkillEngine can share it.
    """
    skill_file = skill_dir / SKILL_FILENAME
    post = frontmatter.load(str(skill_file))
    meta = post.metadata

    # trigger: smart default
    trigger = _meta_str(meta.get("trigger"), "")
    if not trigger:
        has_scripts = (skill_dir / "scripts").exists()
        trigger = "tool" if has_scripts else "manual"

    # executor: infer from trigger
    executor = _meta_str(meta.get("executor"), "")
    if not executor:
        executor = "sandbox" if trigger == "tool" else "handler"

    # handler_fn: prefer new field, fallback to legacy
    handler_fn = _meta_str(
        meta.get("handler_fn")
        or meta.get("handler_module")
        or meta.get("handler"),
        "",
    )

    return Skill(
        skill_id=skill_dir.name,
        name=_meta_str(meta.get("name"), skill_dir.name),
        description=_meta_str(meta.get("description"), ""),
        trigger=trigger,
        modality=_meta_str(meta.get("modality"), ""),
        executor=executor,
        handler_fn=handler_fn,
        tools=_meta_str_list(meta.get("tools")),
        resources=_meta_str_list(meta.get("resources")),
        needs_chat_history=_meta_bool(meta.get("needs_chat_history"), False),
        excludes=_meta_str_list(meta.get("excludes")),
        prompt_injection=_meta_str(meta.get("prompt_injection"), ""),
        base_dir=str(skill_dir),
        body=None,  # L1 only — activate() loads L2
        # legacy fields
        handler=_meta_optional_str(meta.get("handler_module") or meta.get("handler")),
        cron_schedule=_meta_optional_str(meta.get("cron")),
        requires=_meta_str_list(meta.get("requires")),
        tags=_meta_str_list(meta.get("tags")),
    )
