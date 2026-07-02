# Doctor Command Design

## Goal

Add a local-only `doctor` command that helps developers verify OpenHer setup before running live provider smoke tests or launching the backend.

## Design

The command lives in `scripts/doctor.py` and is intentionally separate from backend startup. It loads `.env`, calls the existing provider configuration boundary, and composes a read-only report covering:

- LLM provider, model, base URL presence, and missing key hint.
- TTS and image provider readiness without constructing providers.
- EverMemOS memory configuration readiness, including cloud default behavior when only a key is set.
- Runtime data directory inventory through `scripts.data_lifecycle`.
- Latest backup archive verification when a backup is present or a path is supplied.

The command does not call external APIs, does not instantiate provider clients, and does not print secret values. It reports `status` as `ok`, `warn`, or `error`; the process exits with `1` only when an `error` check exists. Missing optional TTS/image/memory keys are warnings. Missing LLM key is an error because chat cannot run without it unless the provider does not require a key.

## Interfaces

- `build_doctor_report(base_dir=ROOT, data_dir=None, backup_path=None, load_env=True) -> dict`
- `python scripts/doctor.py --json`
- `python scripts/doctor.py --pretty`
- `make doctor`

JSON is the default machine-readable output. Pretty output is a compact text summary for humans.

## Testing

Tests should cover report shape, missing-key redaction, EverMemOS cloud default behavior, data directory inventory, backup verification, CLI output, Makefile exposure, README documentation, and compile inclusion.

## Scope Notes

The doctor command is not a live smoke test. Existing `make integration-smoke` remains the opt-in path for real provider calls.
