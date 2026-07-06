# Skill Runtime Assembly Design

## Purpose

Reduce `server/bootstrap.py` startup responsibility by extracting tool registry setup, skill engine construction, skill loading, and cron skill discovery into a focused skill runtime module.

## Problem

`startup()` still mixes tool/skill assembly with process orchestration:

- It constructs `ToolRegistry`.
- It always registers photo and split tools.
- It conditionally registers voice tools from TTS readiness.
- It constructs `TaskSkillEngine` and `ModalitySkillEngine`.
- It loads all task/modality skills.
- It discovers cron skills from the task skill engine.
- It prints tool and skill load summaries.

This makes bootstrap own low-level skill runtime details while the rest of startup also handles provider, persistence, session, WebSocket, cron, and proactive orchestration.

## Scope

This phase moves only skill runtime assembly:

- Tool registry creation.
- Photo, voice, and split tool registration.
- Task skill engine construction and load.
- Modality skill engine construction and load.
- Cron skill discovery.
- Startup summary messages for registered tools and loaded skills.

Out of scope:

- Skill execution behavior.
- Skill parser or loader behavior.
- Cron scheduler construction and lifecycle.
- Session agent factory construction.
- Provider readiness and media runtime behavior.
- Persona loading.

## Architecture

Add `server/skill_runtime.py` with:

- `SkillRuntimeServices`: dataclass containing the assembled tool registry, task skill engine, modality skill engine, loaded skill dictionaries, cron skills, and summary messages.
- `build_skill_runtime_services(base_dir, voice_tools_enabled, ...)`: constructs the registry, registers tools, builds/loads skill engines, discovers cron skills, and returns messages instead of printing.

`startup()` calls `build_skill_runtime_services(base_dir, voice_tools_enabled=provider_runtime.tts_available)`, assigns returned engines to `AppContext`, prints returned messages, and passes returned `cron_skills` into existing cron/proactive orchestration.

The builder accepts optional factory and registration callables so tests can exercise behavior without depending on real skill files or global tool implementations.

## Compatibility

Behavior remains the same:

- Photo tools are still registered at startup.
- Split tools are still registered at startup.
- Voice tools are registered only when TTS is available.
- Task skills are still loaded from `<repo>/skills/task`.
- Modality skills are still loaded from `<repo>/skills/modality`.
- Both skill engines share the same `ToolRegistry`.
- Cron skills are still discovered from the task skill engine.
- Startup still prints the same style of tool and skill summary messages.
- Bootstrap still owns cron scheduler creation and proactive service orchestration.

## Testing

- Add direct unit tests for skill runtime assembly with injected fake registry, fake engines, and fake registration callables.
- Add a test verifying voice tools are skipped when TTS is unavailable.
- Update bootstrap source boundary tests so `server/bootstrap.py` delegates skill construction to `server.skill_runtime`.
- Run focused skill/bootstrap/session tests, then full quality and smoke/build gates.
