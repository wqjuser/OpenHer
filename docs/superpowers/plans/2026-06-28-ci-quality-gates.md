# CI Quality Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repeatable CI and local quality-check entrypoints so every push and pull request can run backend tests, static typing, compile checks, and Swift package build checks.

**Architecture:** Keep release packaging in the existing tag-only macOS workflow and add a separate `.github/workflows/ci.yml` for ordinary push/PR validation. Add `requirements-dev.txt` and `Makefile` as local developer entrypoints, and add structural tests that assert the CI and tool commands stay present.

**Tech Stack:** GitHub Actions, Python 3.11/3.13, pytest, pyright, Swift Package Manager, Make.

---

### Task 1: Red Tests For Quality Gate Structure

**Files:**
- Create: `tests/test_quality_gates.py`

- [x] **Step 1: Write structural tests**

Add tests that assert:
- `.github/workflows/ci.yml` exists.
- CI runs on `pull_request`, `push` to `main`, and `workflow_dispatch`.
- CI has backend and desktop jobs.
- CI installs `requirements-dev.txt`.
- CI runs `pyright`, `pytest`, `py_compile`, `compileall`, `git diff --check`, and `swift build`.
- `requirements-dev.txt` includes `-r requirements.txt`, `pyright`, and `ruff`.
- `Makefile` exposes `install`, `test`, `typecheck`, `compile`, `check`, and `desktop-build`.

- [x] **Step 2: Run tests and verify expected failure**

Run: `.venv/bin/python -m pytest tests/test_quality_gates.py -q`

Expected: FAIL because the CI workflow, dev requirements, and Makefile do not exist yet.

### Task 2: Add CI And Local Entrypoints

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `requirements-dev.txt`
- Create: `Makefile`
- Modify: `README.md`

- [x] **Step 1: Add backend CI job**

Create `.github/workflows/ci.yml` with a backend matrix for Python `3.11` and `3.13`, pip cache, `requirements-dev.txt` install, `pyright`, `py_compile`, `pytest`, `compileall`, and `git diff --check`.

- [x] **Step 2: Add desktop CI job**

Add a `desktop` job on `macos-latest` that runs `swift build` in `desktop/OpenHer`.

- [x] **Step 3: Add local Makefile**

Add a `Makefile` wrapping install, test, typecheck, compile, check, and desktop-build commands.

- [x] **Step 4: Add dev requirements**

Add `requirements-dev.txt` with `-r requirements.txt`, pinned `pyright`, and a ruff dependency for future lint rollout.

- [x] **Step 5: Document the quality gate**

Add a short README section describing `make install`, `make check`, and `make desktop-build`.

### Task 3: Verification And Delivery

**Files:**
- Test: `tests/test_quality_gates.py`
- Verify: full suite

- [x] **Step 1: Run structural tests**

Run: `.venv/bin/python -m pytest tests/test_quality_gates.py -q`

Expected: PASS.

- [x] **Step 2: Run full verification**

Run:
- `.venv/bin/pyright`
- `.venv/bin/python -m pytest tests/ -q`
- `.venv/bin/python -m py_compile tests/test_quality_gates.py`
- `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`
- `git diff --check`
- `make -n check`
- `make -n desktop-build`

Expected: all commands exit 0.

- [x] **Step 3: Commit branch**

Run:
```bash
git add .github/workflows/ci.yml Makefile requirements-dev.txt README.md tests/test_quality_gates.py docs/superpowers/plans/2026-06-28-ci-quality-gates.md
git commit -m "ci: add quality gate workflow"
```

Expected: branch contains the CI quality gate commit.

- [ ] **Step 4: Merge and push**

Run:
```bash
git switch main
git pull --ff-only
git merge --no-ff codex/ci-quality-gates -m "merge: ci quality gates"
git push origin main
```

Expected: `main` contains the CI quality gate merge commit and is pushed to `origin/main`.
