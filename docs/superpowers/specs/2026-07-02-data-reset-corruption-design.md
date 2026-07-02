# Data Reset Corruption Handling Design

## Purpose

Make the runtime data reset command safe and understandable when `.data/openher.db` is corrupt. The previous diagnostic phase can now detect an unreadable SQLite database; this phase makes the recommended reset path avoid raw Python tracebacks.

## Scope

This change covers the `scripts/data_lifecycle.py reset` path:

- `reset_runtime_data()` reports SQLite reset failures in its summary instead of raising.
- The CLI `reset` subcommand returns structured JSON with `status: "error"` and exit code `1` when reset errors are present.
- The legacy `scripts/reset_data.py` wrapper stops after reset errors instead of continuing into seed import or verification.
- Existing backup-before-reset behavior remains unchanged.

It does not repair, delete, rename, or replace a corrupt `openher.db`. A corrupt database may contain user data, so destructive recovery stays a manual decision.

## Architecture

`reset_runtime_data()` remains the single function that clears runtime files and known runtime tables. Its summary gains an `errors` list. Normal resets return `errors: []`; corrupt SQLite resets append a message like `SQLite reset failed for openher.db: file is not a database`.

The CLI `reset` branch builds the same JSON payload as before, but sets top-level `status` from the summary. It still writes a pre-reset backup before clearing files unless `--no-backup` is passed. If the SQLite reset fails, the JSON includes the backup path when one was created and returns exit code `1`.

The legacy reset wrapper prints the structured reset errors and exits with code `1`. This keeps the old command path from hiding reset failures and then crashing later during seed import.

## Error Handling

- Catch `sqlite3.DatabaseError` only around the `openher.db` table-clearing work.
- Preserve deleted-file and missing-file summary details even when SQLite reset fails.
- Leave `openher.db` in place on SQLite errors.
- Avoid tracebacks for expected corrupt-database conditions.
- Stop legacy seed import when reset already reported errors.

## Testing

- Add a function-level test for corrupt `openher.db` that verifies reset returns a structured error, removes ancillary runtime files, and leaves `openher.db` untouched.
- Add a CLI test for `reset --no-backup` that verifies JSON error output, exit code `1`, and empty stderr.
- Extend the legacy reset source contract test to require explicit handling for `summary["errors"]`.
- Re-run the full data lifecycle tests, then repository quality gates and runtime smoke/build checks.
