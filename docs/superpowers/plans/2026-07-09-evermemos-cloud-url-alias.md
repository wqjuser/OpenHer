# EverMemOS Cloud URL Alias Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize the stale EverMemOS cloud URL `https://api.evermind.ai/v1` to `https://api.evermind.ai/api/v1`.

**Architecture:** Reuse `normalize_evermemos_base_url()` in `providers/config.py`. No new module.

**Tech Stack:** Python 3.11+, pytest, pyright.

## Global Constraints

- Do not add dependencies.
- Do not change custom/self-hosted `/api/v1` URLs.
- Keep all EverMemOS URL normalization in `normalize_evermemos_base_url()`.

---

### Task 1: Add Red Test

**Files:**
- Modify: `tests/test_provider_config.py`

- [x] **Step 1: Add helper assertions**

Assert `normalize_evermemos_base_url("https://api.evermind.ai/v1")` returns `https://api.evermind.ai/api/v1`.

- [x] **Step 2: Run red test**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_evermemos_base_url_normalizer_handles_cloud_aliases -q
```

Expected: FAIL because the stale alias currently becomes `https://api.evermind.ai/v1/api/v1`.

### Task 2: Implement Alias Mapping

**Files:**
- Modify: `providers/config.py`
- Modify: `providers/api_config.py`
- Modify: `tests/test_provider_config.py`

- [x] **Step 1: Add alias constant**

Add `https://api.evermind.ai/v1` to the known EverMemOS cloud alias set.

- [x] **Step 2: Normalize aliases**

Return `EVERMEMOS_CLOUD_BASE_URL` when the stripped URL is a known alias.

- [x] **Step 3: Lock wrapper export**

Add `normalize_evermemos_base_url` to the `providers.api_config` export contract test.

- [x] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py tests/test_security_regressions.py::EverMemOSLoggingRegressionTests -v
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
git add docs/superpowers/specs/2026-07-09-evermemos-cloud-url-alias-design.md docs/superpowers/plans/2026-07-09-evermemos-cloud-url-alias.md providers/config.py tests/test_provider_config.py
git commit -m "fix: normalize evermemos cloud url alias"
git push origin main
```
