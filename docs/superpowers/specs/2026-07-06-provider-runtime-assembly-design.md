# Provider Runtime Assembly Design

## Purpose

Reduce `server/bootstrap.py` startup responsibility by extracting LLM, TTS, WebSocket TTS, and REST media service assembly into a focused provider runtime module.

## Problem

`startup()` currently mixes several responsibilities:

- Persona and persona API service loading.
- Provider readiness checks for LLM, TTS, and Image.
- Provider client construction.
- Tool registry and skill loading.
- Runtime data stores.
- Memory provider initialization.
- Session, WebSocket, cron, and proactive service wiring.

Recent provider config and diagnostics work made provider readiness more explicit, but startup still owns the low-level construction details. That makes bootstrap harder to read and harder to unit-test without starting the whole app.

## Scope

This phase only moves provider runtime assembly:

- LLM config resolution and `LLMClient` construction.
- TTS config resolution and `TTSEngine` construction.
- WebSocket TTS service construction.
- REST `MediaApiService` construction from TTS/Image readiness.
- Startup warning strings for unavailable LLM/TTS providers.

Out of scope:

- Memory provider initialization.
- Runtime data directory and store setup.
- Persona loading.
- Tool registry and skill loading.
- Session manager and WebSocket route service wiring.
- Cron/proactive behavior.
- API response contracts.

## Architecture

Add `server/provider_runtime.py` with:

- `ProviderRuntimeServices`: dataclass containing assembled provider services and readiness metadata.
- `build_provider_runtime_services(base_dir, ...)`: resolves provider configs, builds runtime services, and returns warnings instead of printing.

`startup()` calls `build_provider_runtime_services(base_dir)`, assigns the returned services to `AppContext`, prints returned warnings, and uses `provider_runtime.tts_available` when deciding whether to register voice tools.

The builder accepts optional config objects and factory callables for tests. Production callers use defaults.

## Compatibility

Behavior remains the same:

- Available LLM still creates `LLMClient` with provider, model, temperature, and max tokens from config.
- Missing LLM still disables chat/session/WebSocket chat/proactive services and prints the same warning.
- TTS engine is still constructed from configured provider/cache dir.
- Missing TTS still disables voice skill registration and WebSocket TTS.
- REST media service still receives no TTS engine when TTS is unavailable.
- Image readiness still drives REST image availability and missing-key reason.

## Testing

- Add direct unit tests for provider runtime assembly with injected fake factories.
- Add source boundary tests ensuring `server/bootstrap.py` delegates provider construction to `server.provider_runtime`.
- Update existing bootstrap/media boundary tests to reflect the new module boundary.
- Run focused provider runtime/bootstrap/media tests, then full quality and smoke/build gates.
