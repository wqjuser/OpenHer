# Background Runtime Assembly Design

## Purpose

Reduce `server/bootstrap.py` startup responsibility by extracting cron scheduler and proactive heartbeat assembly into a focused background runtime module.

## Problem

`startup()` still owns background-task details:

- It defines cron message generation and delivery helpers.
- It reads proactive configuration from the EverMemOS memory config file.
- It constructs and starts `CronScheduler`.
- It constructs `ProactiveService` and starts its heartbeat task.
- It owns the LLM-unavailable degradation branch for cron/proactive behavior.

Provider, persistence, skill, and session assembly are already isolated. Background service assembly is now the largest constructor cluster still embedded in bootstrap.

## Scope

This phase moves only background service startup assembly:

- Cron message generation for scheduled skills.
- Cron message delivery into the broadcast memory store.
- Proactive config loading.
- `CronScheduler` construction, callback wiring, registration, and start.
- `ProactiveService` construction.
- Proactive heartbeat task creation.
- LLM/session-unavailable degradation messages.

Out of scope:

- `CronScheduler` scheduling behavior.
- `ProactiveService` sweep, outbox, delivery, or metrics behavior.
- Shutdown cleanup order.
- Session, provider, persistence, or skill runtime assembly.

## Architecture

Add `server/background_runtime.py` with:

- `BackgroundRuntimeServices`: dataclass containing the optional cron scheduler, proactive service, heartbeat task, and startup messages.
- `load_proactive_config(base_dir)`: reads `providers/memory/evermemos/memory_config.yaml` and returns defaults when the file is missing or invalid.
- `generate_cron_message(...)`: builds the persona-scoped prompt and calls the configured LLM.
- `deliver_cron_message(...)`: writes cron output to local memory as a broadcast event.
- `build_background_runtime_services(...)`: accepts already-built provider, skill, persistence, session, and WebSocket dependencies; wires cron/proactive services when chat runtime is available.

`startup()` calls `build_background_runtime_services(...)`, assigns returned services to `AppContext`, and prints returned messages. `shutdown()` remains the single owner of cancellation, scheduler stop, store close, and EverMemOS session close.

The builder accepts factory callables and a task creator for tests. Production callers use defaults.

## Compatibility

Behavior remains the same:

- Cron scheduling starts only when both LLM and session manager are available and cron skills exist.
- Proactive heartbeat starts only when both LLM and session manager are available.
- When LLM/session runtime is unavailable, cron scheduling is skipped and proactive service/task remain disabled.
- Proactive config defaults remain `cooldown_hours=4`, `max_pending=3`, and `lock_ttl=600`.
- Cron generated messages still use the persona name in the system prompt.
- Cron delivery still stores broadcast memory with category `event` and importance `0.6`.

## Testing

- Add direct unit tests for background runtime assembly with injected fake factories.
- Cover LLM/session available and unavailable paths.
- Cover proactive config defaults and YAML overrides.
- Cover cron message generation and delivery helpers.
- Update bootstrap source boundary tests to require `server.background_runtime` delegation.
- Run focused background/bootstrap/proactive tests, then full quality and smoke/build gates.
