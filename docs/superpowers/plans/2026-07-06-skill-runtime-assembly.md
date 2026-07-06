# Skill Runtime Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move tool registry setup, task/modality skill engine loading, and cron skill discovery out of `server/bootstrap.py` into a focused skill runtime module.

**Architecture:** Add `server/skill_runtime.py` with `SkillRuntimeServices` and `build_skill_runtime_services()`. Bootstrap will call the builder, assign returned engines to `AppContext`, print returned summary messages, and continue owning cron scheduler/proactive orchestration.

**Tech Stack:** Python 3.11+, dataclasses, pathlib, pytest, pyright, existing skill engine classes and Makefile gates.

---

### Task 1: Add Skill Runtime Boundary Tests

**Files:**
- Create: `tests/test_skill_runtime.py`
- Modify: `tests/test_server_bootstrap.py`

- [x] **Step 1: Add skill runtime happy-path unit test**

Create `tests/test_skill_runtime.py`:

```python
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
    assert runtime.tool_registry.tool_names == ["generate_photo", "synthesize_voice", "split_messages"]
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
```

- [x] **Step 2: Add unavailable voice tools test**

Append:

```python
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
```

- [x] **Step 3: Update bootstrap source boundary test**

Update `tests/test_server_bootstrap.py::test_bootstrap_degrades_when_llm_provider_is_unavailable()` with these assertions:

```python
assert "from server.skill_runtime import build_skill_runtime_services" in bootstrap_source
assert "skill_runtime = build_skill_runtime_services(" in bootstrap_source
assert "voice_tools_enabled=provider_runtime.tts_available" in bootstrap_source
assert "context.task_skill_engine = skill_runtime.task_skill_engine" in bootstrap_source
assert "context.modality_skill_engine = skill_runtime.modality_skill_engine" in bootstrap_source
assert "cron_skills = skill_runtime.cron_skills" in bootstrap_source
assert "for message in skill_runtime.messages:" in bootstrap_source
assert "ToolRegistry(" not in bootstrap_source
assert "register_photo_tools(" not in bootstrap_source
assert "register_voice_tools(" not in bootstrap_source
assert "register_split_tools(" not in bootstrap_source
assert "TaskSkillEngine(" not in bootstrap_source
assert "ModalitySkillEngine(" not in bootstrap_source
```

- [x] **Step 4: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill_runtime.py tests/test_server_bootstrap.py::test_bootstrap_degrades_when_llm_provider_is_unavailable -v
```

Expected: FAIL because `server.skill_runtime` does not exist and bootstrap still constructs tools and skill engines inline.

### Task 2: Implement Skill Runtime Module

**Files:**
- Create: `server/skill_runtime.py`
- Modify: `server/bootstrap.py`

- [x] **Step 1: Add skill runtime module**

Create `server/skill_runtime.py`:

```python
"""Skill runtime service assembly for OpenHer startup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent.skills import ModalitySkillEngine, TaskSkillEngine
from agent.skills.skill_types import Skill
from agent.skills.tool_registry import ToolRegistry
from agent.skills.tools.photo_tools import register_photo_tools
from agent.skills.tools.split_tools import register_split_tools
from agent.skills.tools.voice_tools import register_voice_tools


@dataclass(frozen=True)
class SkillRuntimeServices:
    tool_registry: Any
    task_skill_engine: Any
    modality_skill_engine: Any
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
```

- [x] **Step 2: Refactor bootstrap imports**

In `server/bootstrap.py`, remove:

```python
from agent.skills import ModalitySkillEngine, TaskSkillEngine
from agent.skills.tool_registry import ToolRegistry
from agent.skills.tools.photo_tools import register_photo_tools
from agent.skills.tools.split_tools import register_split_tools
from agent.skills.tools.voice_tools import register_voice_tools
```

Add:

```python
from server.skill_runtime import build_skill_runtime_services
```

- [x] **Step 3: Refactor startup skill assembly**

Replace the inline tool/skill block with:

```python
    skill_runtime = build_skill_runtime_services(
        base_dir,
        voice_tools_enabled=provider_runtime.tts_available,
    )
    context.task_skill_engine = skill_runtime.task_skill_engine
    context.modality_skill_engine = skill_runtime.modality_skill_engine
    cron_skills = skill_runtime.cron_skills
    for message in skill_runtime.messages:
        print(message)
```

- [x] **Step 4: Run skill runtime tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill_runtime.py tests/test_server_bootstrap.py -v
```

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-skill-runtime-assembly.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so every executed step is checked.

- [x] **Step 2: Run focused skill/bootstrap/session tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill_runtime.py tests/test_server_bootstrap.py tests/test_skill_engine.py tests/test_session_agent_factory.py tests/test_task_skills.py -v
```

Expected: all focused skill, bootstrap, session factory, and task skill tests pass.

- [x] **Step 3: Run repository checks**

Run:

```bash
make check
```

Expected: pyright reports 0 errors and the full pytest suite passes.

- [x] **Step 4: Run runtime/smoke/build gates**

Run:

```bash
make doctor backend-acceptance-smoke backend-runtime-smoke backend-chat-smoke desktop-acceptance-smoke desktop-build
```

Expected: each command exits 0. `make doctor` may report optional warnings for unconfigured optional providers or missing local backups.

- [x] **Step 5: Commit and push**

Run:

```bash
git add docs/superpowers/specs/2026-07-06-skill-runtime-assembly-design.md docs/superpowers/plans/2026-07-06-skill-runtime-assembly.md server/skill_runtime.py server/bootstrap.py tests/test_skill_runtime.py tests/test_server_bootstrap.py
git commit -m "refactor: extract skill runtime assembly"
git push origin main
```
