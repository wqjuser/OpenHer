# Data Reset Corruption Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/data_lifecycle.py reset` report corrupt `openher.db` failures as structured JSON instead of crashing with a traceback.

**Architecture:** Extend the reset summary with an `errors` list, catch SQLite database errors inside `reset_runtime_data()`, and make the reset CLI return exit code `1` when that list is non-empty. Keep the default pre-reset backup behavior, leave corrupt `openher.db` untouched, and make the legacy reset wrapper stop if reset errors are reported.

**Tech Stack:** Python 3.11+, sqlite3, argparse, subprocess, pytest, existing Makefile quality gates.

---

### Task 1: Add Reset Corruption Regression Tests

**Files:**
- Modify: `tests/test_data_lifecycle.py`

- [x] **Step 1: Add imports for CLI testing**

Add `subprocess` and `sys` imports beside the existing stdlib imports.

```python
import subprocess
import sys
```

- [x] **Step 2: Add a failing function-level reset test**

Add a test that writes an invalid `openher.db`, creates ancillary runtime files, and expects `reset_runtime_data()` to return a structured SQLite error without deleting `openher.db`.

```python
def test_reset_runtime_data_reports_corrupt_openher_db_without_raising(tmp_path):
    lifecycle = load_data_lifecycle_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("chat.db", "memory.db", "task.db", "server.log"):
        (data_dir / name).write_text(name, encoding="utf-8")
    openher_db = data_dir / "openher.db"
    openher_db.write_bytes(b"not sqlite")

    summary = lifecycle.reset_runtime_data(data_dir=data_dir)

    assert sorted(summary["deleted_files"]) == ["chat.db", "memory.db", "server.log", "task.db"]
    assert openher_db.read_bytes() == b"not sqlite"
    assert summary["cleared_tables"] == []
    assert summary["genesis_seed_count"] == 0
    assert summary["errors"]
    assert "SQLite reset failed for openher.db" in summary["errors"][0]
```

- [x] **Step 3: Add a failing CLI reset test**

Add a subprocess test that runs the reset subcommand with `--no-backup`, then verifies JSON error output and no traceback.

```python
def test_data_lifecycle_reset_cli_reports_corrupt_openher_db_as_json(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "openher.db").write_bytes(b"not sqlite")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--data-dir",
            str(data_dir),
            "reset",
            "--no-backup",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "error"
    assert payload["reset"]["errors"]
    assert "SQLite reset failed for openher.db" in payload["reset"]["errors"][0]
    assert result.stderr == ""
```

- [x] **Step 4: Run tests to verify red**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py::test_reset_runtime_data_reports_corrupt_openher_db_without_raising tests/test_data_lifecycle.py::test_data_lifecycle_reset_cli_reports_corrupt_openher_db_as_json -v`

Expected: FAIL because reset currently raises `sqlite3.DatabaseError` and the CLI prints a traceback.

### Task 2: Harden Reset Summary and CLI Status

**Files:**
- Modify: `scripts/data_lifecycle.py`

- [x] **Step 1: Add `errors` to the reset summary**

Initialize the summary with an empty `errors` list.

```python
summary: dict[str, Any] = {
    "data_dir": str(root),
    "deleted_files": [],
    "missing_files": [],
    "cleared_tables": [],
    "genesis_seed_count": 0,
    "errors": [],
}
```

- [x] **Step 2: Catch SQLite reset failures**

Wrap the `openher.db` table-clearing block with `except sqlite3.DatabaseError` and append the error message to the summary.

```python
if openher_db.exists():
    conn = sqlite3.connect(openher_db)
    try:
        for table in OPENHER_RUNTIME_TABLES:
            if _table_exists(conn, table):
                conn.execute(f"DELETE FROM {table}")
                summary["cleared_tables"].append(table)
        conn.commit()
        if _table_exists(conn, "genesis_seed"):
            row = conn.execute("SELECT COUNT(*) FROM genesis_seed").fetchone()
            summary["genesis_seed_count"] = int(row[0]) if row else 0
    except sqlite3.DatabaseError as exc:
        summary["errors"].append(f"SQLite reset failed for openher.db: {exc}")
    finally:
        conn.close()
```

- [x] **Step 3: Make the CLI return non-zero on reset errors**

Set the payload status from `summary["errors"]`.

```python
reset_summary = reset_runtime_data(data_dir)
result["reset"] = reset_summary
if reset_summary["errors"]:
    result["status"] = "error"
_print_json(result)
return 0 if result["status"] == "ok" else 1
```

- [x] **Step 4: Run red-green reset tests**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py::test_reset_runtime_data_reports_corrupt_openher_db_without_raising tests/test_data_lifecycle.py::test_data_lifecycle_reset_cli_reports_corrupt_openher_db_as_json -v`

Expected: PASS.

### Task 3: Stop Legacy Reset Wrapper on Reset Errors

**Files:**
- Modify: `tests/test_data_lifecycle.py`
- Modify: `scripts/reset_data.py`

- [x] **Step 1: Add a failing legacy wrapper source contract**

Extend `test_reset_data_legacy_entrypoint_delegates_to_data_lifecycle_module()` to require handling for `summary.get("errors", [])` and `raise SystemExit(1)`.

```python
assert 'summary.get("errors", [])' in source
assert "raise SystemExit(1)" in source
```

- [x] **Step 2: Run the legacy wrapper test to verify red**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py::test_reset_data_legacy_entrypoint_delegates_to_data_lifecycle_module -v`

Expected: FAIL because `scripts/reset_data.py` ignores reset summary errors.

- [x] **Step 3: Add legacy wrapper error handling**

In `clean_data()`, print each reset error and exit before seed import.

```python
for error in summary.get("errors", []):
    print(f"  ❌ {error}")
if summary.get("errors", []):
    print("  ⚠️  请先备份并检查 openher.db，未继续导入种子")
    raise SystemExit(1)
```

- [x] **Step 4: Run legacy wrapper and data lifecycle tests**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py::test_reset_data_legacy_entrypoint_delegates_to_data_lifecycle_module -v` and `.venv/bin/python -m pytest tests/test_data_lifecycle.py -v`

Expected: PASS.

### Task 4: Verify the Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-data-reset-corruption.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so every executed step is checked.

- [x] **Step 2: Run targeted regression tests**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py -v`

Expected: all data lifecycle tests pass.

- [x] **Step 3: Run repository checks**

Run: `make check`

Expected: pyright reports 0 errors and the full pytest suite passes.

- [x] **Step 4: Run local doctor and smoke/build gates**

Run: `make doctor`, `make backend-acceptance-smoke`, and `make desktop-build`.

Expected: each command exits 0. `make doctor` may still report optional warnings depending on local configuration.

- [x] **Step 5: Commit and push**

```bash
git add docs/superpowers/specs/2026-07-02-data-reset-corruption-design.md docs/superpowers/plans/2026-07-02-data-reset-corruption.md tests/test_data_lifecycle.py scripts/data_lifecycle.py scripts/reset_data.py
git commit -m "fix: report reset sqlite failures"
git push origin main
```
