# Smoke Contracts Design

## Purpose

Make integration smoke checks easier to maintain by centralizing repeated response-shape helpers and `/api/status` diagnostics validation.

## Problem

The current smoke scripts repeat several helper functions:

- Safe value rendering for assertion messages.
- Sorted result-line formatting.
- JSON object decoding.
- HTTP status assertions.
- Status diagnostics checks for providers and capabilities.

The duplication is small in each file, but it is now spread across backend acceptance, backend runtime, backend WebSocket, backend chat, desktop acceptance, and provider smoke scripts. This makes the smoke layer harder to extend because contract changes can drift between scripts.

## Scope

This phase only changes smoke-test support code under `scripts/integration/` and matching tests.

In scope:

- Add `scripts/integration/smoke_contracts.py`.
- Move shared helper behavior into that module.
- Refactor smoke scripts to import shared helpers.
- Keep command output names and result fields unchanged.
- Add compile coverage for the new helper module.

Out of scope:

- Backend API behavior.
- Provider configuration or diagnostics behavior.
- Desktop Swift code.
- Live provider calls.
- WebSocket message contracts beyond using shared formatting helpers.

## Architecture

Add a small smoke helper module:

- `StatusDiagnostics`: typed container for validated `/api/status` provider and capability sections.
- `validate_status_diagnostics(body, require_setup_hints=False)`: validates shared `/api/status` contract and returns `StatusDiagnostics`.
- `format_result(name, result)`: formats smoke result lines.
- `safe_value(value)`: truncates values for error messages.
- `require_dict(value, label)`: enforces object shapes.
- `require_status(status_code, expected, label, detail=None)`: enforces HTTP status.
- `bool_text(value, label)`: renders validated booleans as lowercase strings.
- `auth_headers(token)` and `decode_json(raw)`: shared HTTP request helpers.

The scripts keep their flow-specific checks, such as persona list validation, chat body validation, WebSocket event handling, and server lifecycle management.

## Compatibility

Smoke command output remains stable:

- Existing result names remain unchanged.
- Existing result fields remain unchanged.
- Failure messages remain secret-safe.
- Live smoke behavior remains opt-in where it already is.

## Testing

- Add unit tests for `smoke_contracts`.
- Add source boundary tests requiring smoke scripts to import shared helpers and stop defining duplicate local helpers.
- Run focused smoke tests first.
- Run full local quality gates, doctor, backend acceptance smoke, and desktop build.
