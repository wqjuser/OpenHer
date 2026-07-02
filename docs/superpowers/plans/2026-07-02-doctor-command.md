# Doctor Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only doctor command that summarizes configuration, runtime data, and backup readiness without calling external providers.

**Architecture:** Create `scripts/doctor.py` as a thin orchestration script over `providers.config` and `scripts.data_lifecycle`. Keep output JSON-first and secret-safe, with a pretty text mode for manual runs.

**Tech Stack:** Python stdlib (`argparse`, `json`, `os`, `pathlib`), `python-dotenv`, pytest, Makefile, README docs.

---

### Task 1: Report Contract

**Files:**
- Create: `tests/test_doctor.py`
- Create: `scripts/doctor.py`

- [x] **Step 1: Write failing tests**

Add tests that require `build_doctor_report()` to return top-level `status`, `checks`, and `summary`; verify missing LLM key is an error and optional provider keys are warnings.

- [x] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_doctor.py -v`

Expected: FAIL because `scripts/doctor.py` does not exist.

- [x] **Step 3: Implement minimal report**

Create `scripts/doctor.py` with provider readiness checks that never expose API key values.

- [x] **Step 4: Run tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_doctor.py -v`

Expected: PASS.

### Task 2: Data And Backup Checks

**Files:**
- Modify: `tests/test_doctor.py`
- Modify: `scripts/doctor.py`

- [x] **Step 1: Write failing tests**

Add tests that require runtime data inventory and backup verification summaries, including invalid backup errors.

- [x] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_doctor.py -v`

Expected: FAIL because doctor does not include data/backup checks yet.

- [x] **Step 3: Implement data and backup checks**

Use `resolve_data_dir()`, `inventory_data_dir()`, and `verify_backup_archive()` from `scripts.data_lifecycle`.

- [x] **Step 4: Run tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_doctor.py -v`

Expected: PASS.

### Task 3: CLI, Makefile, And Docs

**Files:**
- Modify: `scripts/doctor.py`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `tests/test_quality_gates.py`
- Modify: `tests/test_integration_smoke_profile.py`

- [x] **Step 1: Write failing tests**

Update quality-gate and README smoke tests to require `make doctor`, compile coverage, and README references.

- [x] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_quality_gates.py tests/test_integration_smoke_profile.py -v`

Expected: FAIL because Makefile and README do not expose doctor yet.

- [x] **Step 3: Implement wrappers and documentation**

Add `make doctor`, compile `scripts/doctor.py`, and document the local-only behavior.

- [x] **Step 4: Verify end to end**

Run: `.venv/bin/python -m pytest tests/test_doctor.py tests/test_quality_gates.py tests/test_integration_smoke_profile.py -v`, `make doctor`, `make check`, `make backend-acceptance-smoke`, and `make desktop-build`.

Expected: all commands exit 0 except missing optional warnings remain visible in doctor output.
