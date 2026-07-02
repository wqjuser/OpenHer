# Doctor Hints And Strict Mode Design

## Goal

Make `make doctor` more actionable by telling developers how to fix each warning or error, and add a strict mode for preflight checks that should fail on warnings.

## Design

Each doctor check gains a `setup_hint` string alongside `status`, `message`, and `details`. Hints are static and secret-safe. They point to concrete local actions such as setting a specific environment variable, running `make data-backup`, or ignoring optional media warnings when the feature is not needed.

The CLI gains `--strict`. Normal mode keeps the current behavior: `error` exits `1`, while `warn` exits `0`. Strict mode exits `1` for either `warn` or `error`, which lets CI or release scripts require a fully clean local setup when desired.

Makefile exposes:

- `make doctor`
- `make doctor-strict`

`doctor-strict` is not added to default `make check` because the repository should remain testable without optional media keys or runtime backups.

## Testing

Tests should verify:

- Required LLM failures include a hint naming accepted env vars.
- Optional TTS/Image warnings include hints that distinguish optional setup.
- Missing backup warnings include `make data-backup`.
- Pretty output includes hints.
- `--strict` exits non-zero on warnings.
- Makefile and README document `doctor-strict`.

## Scope Notes

This remains a local-only diagnostic layer. It does not call external providers, generate media, or mutate runtime data.
