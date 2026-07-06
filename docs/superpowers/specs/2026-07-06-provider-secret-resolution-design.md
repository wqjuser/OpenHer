# Provider Secret Resolution Design

## Purpose

Reduce duplication in provider configuration resolution by centralizing API-key availability and missing-key hint construction for LLM, TTS, and Image providers.

## Problem

`providers/config.py` currently repeats the same rules in three places:

- Resolve provider-specific API-key env vars before generic feature env vars.
- Mark providers available when `no_key_required` is true or when the active key is present.
- Render `missing_key_env` using the accepted env var names in priority order.

This duplication makes future provider additions fragile because LLM, TTS, and Image can drift even though they share the same secret-resolution contract.

## Scope

This phase only changes provider secret resolution inside `providers/config.py`.

In scope:

- Add a small typed result for resolved provider secrets.
- Add pure helpers for a single active provider secret and for a media provider key map.
- Refactor `get_llm_config()`, `get_tts_config()`, and `get_image_config()` to use the helpers.
- Preserve all existing return keys and values for public config functions.

Out of scope:

- Memory provider configuration.
- Provider registry constructor behavior.
- `providers/api.yaml` content.
- Doctor/status output shape.
- Live provider calls.

## Architecture

Add a `ResolvedProviderSecret` dataclass to `providers/config.py`:

```python
@dataclass(frozen=True)
class ResolvedProviderSecret:
    api_key: str
    available: bool
    missing_key_env: str
    env_options: list[str]
```

Add helper functions:

- `_resolve_provider_secret(provider_name, preset, generic_env)`
- `_resolve_provider_secret_map(providers, active_provider, generic_env)`

`_resolve_provider_secret()` owns key option ordering, env lookup, `no_key_required`, and missing-key rendering. `_resolve_provider_secret_map()` builds the media `api_keys` dictionary while applying the generic feature key only to the active provider.

## Compatibility

The public config dictionaries remain unchanged:

- LLM still returns `api_key`, `available`, and `missing_key_env`.
- TTS and Image still return `api_keys`, `active_api_key`, `available`, and `missing_key_env`.
- Provider-specific env vars still win over generic feature env vars.
- Generic feature env vars still apply only to the active TTS/Image provider.
- No secret values are exposed in diagnostics.

## Testing

- Add unit tests for the new pure helper behavior.
- Keep existing provider config boundary tests passing.
- Run provider config, registry, diagnostics, doctor, and status focused tests.
- Run full local quality gates plus doctor, backend acceptance smoke, and desktop build.
