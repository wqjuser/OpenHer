# CI Backend Smokes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend smoke commands to GitHub Actions so CI verifies real backend startup, HTTP routes, WebSocket behavior, and chat degradation/live-chat flow.

**Architecture:** Keep the existing backend Python matrix and desktop Swift job. Add a dedicated backend smoke step in `.github/workflows/ci.yml` after the existing backend quality commands. The step uses existing Makefile targets, which already isolate runtime data and skip chat generation when LLM keys are absent.

**Tech Stack:** GitHub Actions, Makefile, Python smoke scripts, pytest quality-gate tests.

---

### Task 1: CI Smoke Contract Test

**Files:**
- Modify: `tests/test_quality_gates.py`

- [ ] **Step 1: Write failing test**

Add:

```python
def test_ci_workflow_runs_backend_smoke_commands():
    workflow = load_ci_workflow()
    run_blocks = all_ci_run_blocks(workflow)

    assert "make backend-acceptance-smoke" in run_blocks
    assert "make backend-runtime-smoke" in run_blocks
    assert "make backend-websocket-smoke" in run_blocks
    assert "make backend-chat-smoke" in run_blocks
```

- [ ] **Step 2: Verify RED**

Run:

```bash
source .venv/bin/activate
python -m pytest tests/test_quality_gates.py::test_ci_workflow_runs_backend_smoke_commands -q
```

Expected: FAIL because `.github/workflows/ci.yml` does not run the backend smoke targets.

### Task 2: CI Workflow Wiring

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add backend smoke step**

Add this step to the backend job after `Check whitespace`:

```yaml
      - name: Run backend smokes
        run: |
          make backend-acceptance-smoke
          make backend-runtime-smoke
          make backend-websocket-smoke
          make backend-chat-smoke
```

- [ ] **Step 2: Verify focused test**

Run:

```bash
source .venv/bin/activate
python -m pytest tests/test_quality_gates.py::test_ci_workflow_runs_backend_smoke_commands -q
```

Expected: PASS.

### Task 3: Full Verification and Finish

**Files:**
- All changed files

- [ ] **Step 1: Run local backend smokes**

Run:

```bash
source .venv/bin/activate
make backend-acceptance-smoke
make backend-runtime-smoke
make backend-websocket-smoke
make backend-chat-smoke
```

Expected: all exit 0.

- [ ] **Step 2: Run full gates**

Run:

```bash
source .venv/bin/activate
make check
swift build --package-path desktop/OpenHer
make integration-smoke
```

Expected: all exit 0, with optional media providers allowed to skip when keys are absent.

- [ ] **Step 3: Commit, merge, and push**

Run:

```bash
git add .github/workflows/ci.yml tests/test_quality_gates.py docs/superpowers/specs/2026-06-30-ci-backend-smokes-design.md docs/superpowers/plans/2026-06-30-ci-backend-smokes.md
git commit -m "ci: run backend smoke checks"
git checkout main
git pull --ff-only origin main
git merge --ff-only codex/ci-backend-smokes
git push origin main
```

Expected: branch fast-forwards and push succeeds.
