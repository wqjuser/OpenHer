# Doctor Hints Strict Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add actionable setup hints and strict preflight behavior to the local doctor command.

**Architecture:** Extend `scripts/doctor.py` in place by adding `setup_hint` to check objects and `--strict` to CLI exit handling. Keep provider config parsing and data lifecycle boundaries unchanged.

**Tech Stack:** Python stdlib (`argparse`, `json`, `pathlib`, `subprocess`), pytest, Makefile, README docs.

---

### Task 1: Setup Hints

**Files:**
- Modify: `tests/test_doctor.py`
- Modify: `scripts/doctor.py`

- [x] **Step 1: Write failing tests**

Add tests requiring `setup_hint` on LLM, optional media, data, and backup checks, plus pretty output containing hint lines.

- [x] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_doctor.py -v`

Expected: FAIL because check objects do not include `setup_hint` yet.

- [x] **Step 3: Implement hints**

Update `_check()` to include `setup_hint`, pass hints from each check builder, and render hints in pretty output.

- [x] **Step 4: Run tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_doctor.py -v`

Expected: PASS.

### Task 2: Strict Mode And Docs

**Files:**
- Modify: `tests/test_doctor.py`
- Modify: `tests/test_quality_gates.py`
- Modify: `tests/test_integration_smoke_profile.py`
- Modify: `scripts/doctor.py`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `README_EN.md`

- [x] **Step 1: Write failing tests**

Add tests requiring `--strict` to exit non-zero on warning-only reports, plus `doctor-strict` Makefile and README coverage.

- [x] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_doctor.py tests/test_quality_gates.py tests/test_integration_smoke_profile.py -v`

Expected: FAIL because strict mode and docs do not exist yet.

- [x] **Step 3: Implement strict mode and docs**

Add `--strict`, `make doctor-strict`, and README notes explaining normal versus strict exit behavior.

- [x] **Step 4: Verify end to end**

Run: `.venv/bin/python -m pytest tests/test_doctor.py tests/test_quality_gates.py tests/test_integration_smoke_profile.py -v`, `make doctor`, a controlled `doctor --strict` warning smoke, `make check`, `make backend-acceptance-smoke`, and `make desktop-build`.

Expected: normal doctor exits 0 on warnings, strict exits 1 on warnings, all repository quality commands pass.
