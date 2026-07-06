# Provider Doctor Checks Design

## Purpose

Continue consolidating provider diagnostics by moving doctor-specific LLM/TTS/Image check construction out of `scripts/doctor.py` and into `providers.diagnostics`.

## Scope

This phase covers provider-only doctor checks:

- Required provider checks, currently used by LLM.
- Optional provider checks, currently used by TTS and Image.
- Source contract tests that keep `scripts/doctor.py` as an orchestration script instead of a second provider diagnostics implementation.

It does not change memory, runtime data, backup, `/api/status`, desktop models, provider config resolution, or live provider behavior.

## Architecture

`providers.diagnostics` gains two pure functions:

- `required_provider_doctor_check(label, cfg)`
- `optional_provider_doctor_check(label, cfg)`

Both functions return the existing doctor check shape:

```python
{
    "status": "...",
    "message": "...",
    "setup_hint": "...",
    "details": {...},
}
```

`scripts/doctor.py` imports these helpers and uses them for `llm`, `tts`, and `image`. It keeps local functions for memory, data, backup, summary, pretty output, and CLI exit behavior because those still depend on local runtime context.

## Compatibility

Doctor JSON and pretty output remain unchanged for provider checks:

- LLM missing key remains an `error`.
- TTS and Image missing keys remain `warn`.
- Successful provider checks keep `setup_hint: "No action needed."`.
- Secret values are never emitted.

## Testing

- Add diagnostics unit tests for required and optional provider doctor checks.
- Add doctor source contract tests requiring the shared helpers and rejecting local `_llm_check` / `_optional_provider_check` definitions.
- Re-run doctor tests, provider diagnostics tests, server route tests, full quality gates, and smoke/build checks.
