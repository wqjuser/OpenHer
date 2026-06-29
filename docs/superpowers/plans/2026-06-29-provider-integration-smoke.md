# Provider Integration Smoke Profile

**Goal:** Add an explicit, reusable live-provider smoke profile for OpenHer so configured LLM and EverMemOS providers can be verified without making default tests or CI call external services.

**Architecture:** Add `scripts/integration/provider_smoke.py` as the single opt-in CLI for live provider checks. It loads `.env`, exits successfully with a clear skip message unless `RUN_OPENHER_INTEGRATION=1` is set, then runs a compact LLM chat smoke and an EverMemOS connection smoke through the existing provider configuration and client adapters. Add a `make integration-smoke` target and README instructions.

**Tech Stack:** Python 3.11+, pytest, existing provider config, existing `LLMClient`, existing `EverMemOSClient`.

## Implementation Tasks

- [x] Create a failing structural/runtime test for the integration smoke profile.
- [x] Implement `scripts/integration/provider_smoke.py` with explicit opt-in and secret-safe output.
- [x] Add `make integration-smoke`.
- [x] Document the command in README.
- [x] Verify targeted tests, skip-mode execution, live-mode execution when configured, `make check`, and Swift build.

## Verification Plan

- `.venv/bin/python -m pytest tests/test_integration_smoke_profile.py -q`
- `.venv/bin/python scripts/integration/provider_smoke.py`
- `RUN_OPENHER_INTEGRATION=1 .venv/bin/python scripts/integration/provider_smoke.py`
- `source .venv/bin/activate && make check`
- `cd desktop/OpenHer && swift build`
