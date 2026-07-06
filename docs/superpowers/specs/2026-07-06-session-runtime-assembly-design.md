# Session Runtime Assembly Design

## Purpose

Reduce `server/bootstrap.py` startup responsibility by extracting REST chat, session lifecycle, and WebSocket service assembly into a focused session runtime module.

## Problem

`startup()` still owns a dense session/WebSocket block:

- It constructs `SessionAgentFactory`.
- It constructs `SessionManager`.
- It constructs `ChatApiService`.
- It constructs WebSocket persona switching, chat turn, demo command, and route services.
- It owns the LLM-unavailable degradation branch for those services.

This mixes low-level service wiring with bootstrap orchestration. Provider, persistence, and skill assembly are already isolated; session/WebSocket assembly is now the largest remaining constructor cluster in startup.

## Scope

This phase moves only session and WebSocket service assembly:

- `SessionAgentFactory` construction.
- `SessionManager` construction.
- `ChatApiService` construction for available and unavailable chat modes.
- `WebSocketPersonaSwitchService` construction.
- `WebSocketChatTurnService` construction.
- `WebSocketDemoCommandService` construction.
- `WebSocketRouteService` construction.

Out of scope:

- Session manager behavior.
- Chat API behavior.
- WebSocket message routing behavior.
- Cron scheduler construction.
- Proactive service construction and heartbeat lifecycle.
- Persona loading.
- Provider, skill, or persistence assembly.

## Architecture

Add `server/session_runtime.py` with:

- `SessionRuntimeServices`: dataclass containing all assembled session and WebSocket services.
- `build_session_runtime_services(...)`: accepts already-built provider, skill, persistence, WebSocket registry, and callback dependencies; constructs the same services that bootstrap currently constructs.

`startup()` calls `build_session_runtime_services(...)`, assigns returned services to `AppContext`, and continues to use the returned session manager for cron/proactive orchestration.

The builder accepts factory callables for tests. Production callers use defaults.

## Compatibility

Behavior remains the same:

- When LLM is configured, chat sessions, REST chat, WebSocket chat, persona switching, and demo commands are enabled.
- When LLM is unavailable, session manager and WebSocket chat/persona/demo services remain disabled.
- REST chat still has a `ChatApiService` instance with `session_manager=None`, so routes return the same service-unavailable response.
- `WebSocketRouteService` is always constructed and receives whatever chat/persona/demo/TTS services are available.
- Demo command presets still load from `<repo>/demo/presets/showcase.yaml`.
- Bootstrap still owns cron scheduler and proactive heartbeat construction.

## Testing

- Add direct unit tests for session runtime assembly with injected fake factories.
- Cover both LLM-available and LLM-unavailable degradation paths.
- Update bootstrap source boundary tests to require `server.session_runtime` delegation.
- Update existing Chat API, SessionAgentFactory, and WebSocket route boundary tests to reflect the new assembly owner.
- Run focused session/bootstrap/chat/WebSocket tests, then full quality and smoke/build gates.
