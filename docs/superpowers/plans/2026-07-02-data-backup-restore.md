# Data Backup Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the runtime data lifecycle tooling from inventory/backup/reset into a backup verification and restore workflow.

**Architecture:** Keep the data lifecycle boundary in `scripts/data_lifecycle.py` so backend runtime code remains unaware of local operations tooling. Add pure functions for backup verification and restoration, then expose thin CLI and Makefile wrappers.

**Tech Stack:** Python stdlib (`argparse`, `json`, `pathlib`, `shutil`, `sqlite3`, `zipfile`), pytest, Makefile, README docs.

---

### Task 1: Backup Verification

**Files:**
- Modify: `tests/test_data_lifecycle.py`
- Modify: `scripts/data_lifecycle.py`

- [x] **Step 1: Write failing tests**

Add tests that require `verify_backup_archive()` to accept a normal backup and reject unsafe archive paths such as `../evil.txt`.

- [x] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py -v`

Expected: FAIL because `verify_backup_archive` does not exist yet.

- [x] **Step 3: Implement verification**

Add `verify_backup_archive(backup_path)` that reads `manifest.json`, validates schema version 1, validates each manifest path is relative and safe, confirms every listed archive entry exists, and checks file sizes.

- [x] **Step 4: Run tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py -v`

Expected: PASS.

### Task 2: Backup Restore

**Files:**
- Modify: `tests/test_data_lifecycle.py`
- Modify: `scripts/data_lifecycle.py`

- [x] **Step 1: Write failing tests**

Add tests that require `restore_data_backup()` to refuse non-empty targets without `overwrite=True`, restore all manifest files into an empty target, remove stale target files when overwriting, and preserve a pre-restore backup when requested.

- [x] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py -v`

Expected: FAIL because `restore_data_backup` does not exist yet.

- [x] **Step 3: Implement restore**

Add `restore_data_backup(backup_path, data_dir, overwrite=False, backup_existing=True, backup_dir=None)` that verifies the archive, optionally backs up existing data, safely clears stale files, and extracts only manifest-listed entries.

- [x] **Step 4: Run tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py -v`

Expected: PASS.

### Task 3: CLI, Makefile, and Docs

**Files:**
- Modify: `scripts/data_lifecycle.py`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `tests/test_quality_gates.py`
- Modify: `tests/test_integration_smoke_profile.py`

- [x] **Step 1: Write failing tests**

Update quality-gate and README smoke tests to require `data-verify` and `data-restore` Make targets and README examples.

- [x] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_quality_gates.py tests/test_integration_smoke_profile.py -v`

Expected: FAIL because Makefile and README entries do not exist yet.

- [x] **Step 3: Implement wrappers and documentation**

Add `verify` and `restore` CLI subcommands, `make data-verify BACKUP=...`, `make data-restore BACKUP=... ARGS=--overwrite`, and matching README snippets.

- [x] **Step 4: Verify end to end**

Run: `.venv/bin/python -m pytest tests/test_data_lifecycle.py tests/test_quality_gates.py tests/test_integration_smoke_profile.py -v`, `make check`, a temp-dir CLI restore smoke, `make backend-acceptance-smoke`, and `make desktop-build`.

Expected: all commands exit 0.
