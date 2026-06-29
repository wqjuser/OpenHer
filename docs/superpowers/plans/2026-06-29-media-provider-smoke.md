# Media Provider Smoke Coverage

**Goal:** Extend the optional provider integration smoke profile so TTS and image provider configuration/factory paths are verified alongside LLM and EverMemOS.

**Architecture:** Keep `scripts/integration/provider_smoke.py` as the single opt-in provider smoke CLI. Add TTS and image checks that resolve config from `providers.config` and instantiate providers through `providers.registry` only when the active provider has enough credentials. These checks must not call synthesize/generate or create real media.

**Tech Stack:** Python 3.11+, pytest, existing provider config facade, existing provider registry.

## Implementation Tasks

- [x] Add structural tests requiring TTS/Image config and registry coverage in the smoke profile.
- [x] Implement TTS provider factory smoke with safe skipped output when the provider is not configured.
- [x] Implement image provider factory smoke with safe skipped output when the provider is not configured.
- [x] Update README integration-smoke docs to describe media factory checks.
- [x] Verify targeted tests, skip mode, live opt-in smoke, `make check`, and Swift build.

## Verification Plan

- `.venv/bin/python -m pytest tests/test_integration_smoke_profile.py -q`
- `.venv/bin/python scripts/integration/provider_smoke.py`
- `RUN_OPENHER_INTEGRATION=1 .venv/bin/python scripts/integration/provider_smoke.py`
- `source .venv/bin/activate && make check`
- `cd desktop/OpenHer && swift build`
