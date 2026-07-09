# EverMemOS English README Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the English EverMemOS setup docs so cloud setup uses only the API key.

**Architecture:** Docs-only change plus one README contract test. No runtime code.

**Tech Stack:** Markdown, pytest.

## Global Constraints

- Do not change runtime EverMemOS behavior.
- Keep `EVERMEMOS_BASE_URL` documented for self-hosted/private gateway setup only.

---

### Task 1: Add Red Test

**Files:**
- Modify: `tests/test_integration_smoke_profile.py`

- [x] **Step 1: Add README_EN contract assertions**

Assert `README_EN.md` does not document `https://api.evermind.ai/v1` and tells cloud users to set only `EVERMEMOS_API_KEY`.

- [x] **Step 2: Run red test**

Run:

```bash
.venv/bin/python -m pytest tests/test_integration_smoke_profile.py::test_makefile_and_readme_document_integration_smoke -q
```

Expected: FAIL because README_EN still includes the stale cloud base URL.

### Task 2: Fix README_EN

**Files:**
- Modify: `README_EN.md`

- [x] **Step 1: Remove cloud base URL**

Keep only `EVERMEMOS_API_KEY=your_api_key` in the cloud setup snippet.

- [x] **Step 2: Mention default cloud URL**

Add one sentence that OpenHer uses the default EverMemOS cloud URL unless self-hosted/private gateway is configured.

- [x] **Step 3: Run focused test**

Run:

```bash
.venv/bin/python -m pytest tests/test_integration_smoke_profile.py::test_makefile_and_readme_document_integration_smoke -q
```

Expected: PASS.

### Task 3: Verify And Ship

- [x] **Step 1: Run gates**

Run:

```bash
make check
```

Expected: exit 0.

- [x] **Step 2: Commit and push**

Run:

```bash
git add docs/superpowers/specs/2026-07-09-evermemos-english-readme-config-design.md docs/superpowers/plans/2026-07-09-evermemos-english-readme-config.md README_EN.md tests/test_integration_smoke_profile.py
git commit -m "docs: fix evermemos english cloud setup"
git push origin main
```
