# Provider Diagnostics Boundary Design

## Purpose

Reduce drift between backend `/api/status`, desktop configuration diagnostics, and local `doctor` output by introducing a shared, secret-safe provider diagnostics boundary.

## Scope

This phase is intentionally compatibility-preserving:

- Add `providers.diagnostics` for provider readiness, setup hints, capability summaries, and secret-presence checks.
- Make `server/routes/health.py` use the shared diagnostics helpers while keeping the `/api/status` JSON shape unchanged.
- Make `scripts/doctor.py` reuse the shared secret-presence helper instead of owning a second implementation.

It does not change provider config resolution, desktop model names, live provider calls, or doctor JSON shape.

## Architecture

`providers.config` remains the source of raw provider configuration. The new `providers.diagnostics` module becomes the source for derived readiness payloads:

- `provider_secret_configured(cfg, active=False)` reports whether a secret-like config value exists without leaking it.
- `provider_capability_status(cfg)` converts LLM/TTS/Image config into the `/api/status.providers.<name>` shape.
- `memory_runtime_status(cfg, runtime_available)` converts memory config plus runtime client availability into the `/api/status.providers.memory` shape.
- `capabilities_status(providers)` derives chat, voice, image, and memory feature summaries from provider status.

`server.routes.health` keeps route orchestration only: read app context, read raw config, call diagnostics helpers, and return the existing status payload.

## Error Handling And Security

- The new diagnostics helpers only use booleans, provider names, missing env names, and setup hints.
- API keys, active API keys, base URLs, and memory URLs are not emitted by diagnostics helpers.
- Memory diagnostics keep the existing runtime distinction: configured does not imply available if the runtime EverMemOS client is unavailable.

## Testing

- Add unit tests for the diagnostics helpers and their secret-redaction behavior.
- Add source contract tests that keep `server.routes.health` thin and prevent reintroducing local provider status helpers.
- Extend doctor source contract tests so doctor uses `provider_secret_configured`.
- Re-run existing status route, doctor, desktop readiness, full quality gates, and smoke/build checks.
