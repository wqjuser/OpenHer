# Data Inventory Corruption Handling Design

## Purpose

Make local diagnostics resilient when `.data/openher.db` is present but not readable as SQLite. `make doctor` and `scripts/data_lifecycle.py inventory` should report the problem instead of crashing while trying to inspect table counts.

## Scope

This change covers read-only diagnostics only:

- `inventory_data_dir()` catches SQLite inventory failures for `openher.db`.
- `doctor` marks corrupt runtime SQLite inventory as an error with a concrete recovery hint.
- Tests cover the function-level inventory path and the doctor report path.

It does not repair, migrate, delete, or rewrite a damaged database.

## Architecture

`scripts/data_lifecycle.py` remains the boundary for runtime data inspection. On the normal path, `inventory["sqlite"]["openher.db"]` stays as the existing table-count dictionary. On failure, that entry becomes a small error dictionary so callers can inspect the failure without catching SQLite exceptions themselves.

`scripts/doctor.py` interprets that error dictionary as a data check failure. The report keeps the full secret-safe data inventory in `details["sqlite"]` and uses a setup hint that tells the developer to back up data if possible, inspect `openher.db`, or run `make data-reset` after backing up.

## Error Handling

- Catch `sqlite3.DatabaseError` around known-table inventory only.
- Preserve file inventory even when SQLite inspection fails.
- Avoid stack traces in JSON and pretty doctor output.
- Do not include secrets or environment values in the new error details.

## Testing

- Add a data lifecycle test that writes non-SQLite bytes to `openher.db`, calls `inventory_data_dir()`, and asserts it returns a structured SQLite error.
- Add a doctor test that uses a corrupt `openher.db` and asserts the data check is `error`, the top-level status is `error`, and the setup hint points to backup/reset recovery.
- Run targeted tests first, then full quality gates and runtime smoke commands.
