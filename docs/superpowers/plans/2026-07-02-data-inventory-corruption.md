# Data Inventory Corruption Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep runtime data diagnostics usable when `.data/openher.db` is corrupt or otherwise unreadable by SQLite.

**Architecture:** Extend `scripts/data_lifecycle.py` to convert SQLite inventory failures into structured inventory data, then teach `scripts/doctor.py` to surface that condition as a data error. Preserve the successful inventory JSON shape for compatibility.

**Tech Stack:** Python 3.11+, sqlite3, pytest, existing Makefile quality gates.

---

### Task 1: Add Corrupt SQLite Regression Tests

**Files:**
- Modify: `tests/test_data_lifecycle.py`
- Modify: `tests/test_doctor.py`

- [x] **Step 1: Add a failing lifecycle test**

Add a test that creates a data directory with an invalid `openher.db`, calls `inventory_data_dir()`, and expects a structured error instead of an exception.

```python
def test_inventory_data_dir_reports_corrupt_openher_db_without_raising(tmp_path):
    lifecycle = load_data_lifecycle_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "openher.db").write_bytes(b"not sqlite")

    inventory = lifecycle.inventory_data_dir(data_dir)

    sqlite_inventory = inventory["sqlite"]["openher.db"]
    assert inventory["exists"] is True
    assert sqlite_inventory["error"]
    assert "file is not a database" in sqlite_inventory["error"]
```

- [x] **Step 2: Add a failing doctor test**

Add a doctor report test that points at the same kind of corrupt runtime database and asserts the data check is an error with actionable recovery guidance.

```python
def test_doctor_report_marks_corrupt_openher_db_as_data_error(monkeypatch, tmp_path):
    doctor = load_doctor_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("DEFAULT_PROVIDER", "ollama")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "openher.db").write_bytes(b"not sqlite")

    report = doctor.build_doctor_report(base_dir=ROOT, data_dir=data_dir, load_env=False)

    assert report["status"] == "error"
    assert report["checks"]["data"]["status"] == "error"
    assert "SQLite inventory failed" in report["checks"]["data"]["message"]
    assert "make data-reset" in report["checks"]["data"]["setup_hint"]
    assert report["checks"]["data"]["details"]["sqlite"]["openher.db"]["error"]
```

- [x] **Step 3: Run tests to verify red**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py::test_inventory_data_dir_reports_corrupt_openher_db_without_raising tests/test_doctor.py::test_doctor_report_marks_corrupt_openher_db_as_data_error -v`

Expected: FAIL because `inventory_data_dir()` currently raises `sqlite3.DatabaseError`.

### Task 2: Harden Runtime Data Inventory

**Files:**
- Modify: `scripts/data_lifecycle.py`

- [x] **Step 1: Catch SQLite inventory failures**

Wrap the `openher.db` table count call in `inventory_data_dir()` and return `{"error": "SQLite inventory failed: ..."}` on `sqlite3.DatabaseError`.

```python
try:
    inventory["sqlite"]["openher.db"] = _sqlite_table_counts(
        openher_db,
        ("genesis_seed", *OPENHER_RUNTIME_TABLES),
    )
except sqlite3.DatabaseError as exc:
    inventory["sqlite"]["openher.db"] = {
        "error": f"SQLite inventory failed: {exc}",
    }
```

- [x] **Step 2: Run lifecycle red-green test**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py::test_inventory_data_dir_reports_corrupt_openher_db_without_raising -v`

Expected: PASS.

### Task 3: Surface Data Inventory Errors in Doctor

**Files:**
- Modify: `scripts/doctor.py`

- [x] **Step 1: Mark corrupt SQLite as a data error**

Teach `_data_check()` to inspect `inventory["sqlite"]["openher.db"]`. If that dictionary has an `error`, return an error check with the existing inventory details.

```python
openher_db = sqlite.get("openher.db") if isinstance(sqlite, dict) else {}
sqlite_error = ""
if isinstance(openher_db, dict):
    sqlite_error = str(openher_db.get("error") or "")
if sqlite_error:
    return _check(
        "error",
        "Runtime data SQLite inventory failed",
        "Back up .data if possible, inspect openher.db, or run make data-reset after backing up.",
        {
            "data_dir": str(inventory.get("data_dir") or ""),
            "exists": exists,
            "file_count": len(files) if isinstance(files, list) else 0,
            "sqlite": sqlite if isinstance(sqlite, dict) else {},
        },
    )
```

- [x] **Step 2: Run doctor red-green test**

Run: `.venv/bin/python -m pytest tests/test_doctor.py::test_doctor_report_marks_corrupt_openher_db_as_data_error -v`

Expected: PASS.

### Task 4: Verify the Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-data-inventory-corruption.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so each executed step is checked.

- [x] **Step 2: Run targeted regression tests**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py tests/test_doctor.py -v`

Expected: all tests pass.

- [x] **Step 3: Run repository checks**

Run: `make check`

Expected: pyright reports 0 errors and pytest reports the full suite passing.

- [x] **Step 4: Run local doctor and smoke/build gates**

Run: `make doctor`, `make backend-acceptance-smoke`, and `make desktop-build`.

Expected: each command exits 0. `make doctor` may still report optional warnings depending on local configuration, but it must not crash.

- [x] **Step 5: Commit and push**

```bash
git add docs/superpowers/specs/2026-07-02-data-inventory-corruption-design.md docs/superpowers/plans/2026-07-02-data-inventory-corruption.md tests/test_data_lifecycle.py tests/test_doctor.py scripts/data_lifecycle.py scripts/doctor.py
git commit -m "fix: harden data inventory diagnostics"
git push origin main
```
