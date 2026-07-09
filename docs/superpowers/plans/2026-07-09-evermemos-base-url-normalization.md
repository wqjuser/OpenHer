# EverMemOS Base URL Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize EverMemOS base URLs so deprecated cloud `/api/v0` values resolve to `/api/v1`.

**Architecture:** Put one helper in `providers/config.py`. Reuse it from `get_memory_config()` and `EverMemOSClient.__init__()`.

**Tech Stack:** Python 3.11+, pytest, pyright.

## Global Constraints

- Do not add a URL parsing dependency.
- Do not change EverMemOS public client methods.
- Preserve local host auto-append behavior for base URLs without `/api/`.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `tests/test_provider_config.py`
- Modify: `tests/test_security_regressions.py`

- [x] **Step 1: Add config normalization test**

Assert `EVERMEMOS_BASE_URL=https://api.evermind.ai/api/v0` resolves to `https://api.evermind.ai/api/v1`.

- [x] **Step 2: Add client normalization test**

Assert `EverMemOSClient(base_url="https://api.evermind.ai/api/v0")` stores `_base_url` as `https://api.evermind.ai/api/v1`.

- [x] **Step 3: Run red tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_memory_config_normalizes_deprecated_cloud_v0_url tests/test_security_regressions.py::EverMemOSLoggingRegressionTests::test_evermemos_client_normalizes_deprecated_cloud_v0_base_url -q
```

Expected: FAIL on `/api/v0` values.

### Task 2: Implement

**Files:**
- Modify: `providers/config.py`
- Modify: `providers/api_config.py`
- Modify: `providers/memory/evermemos/evermemos_client.py`
- Modify: `providers/memory/evermemos/memory_config.yaml`

- [x] **Step 1: Add helper**

Add `normalize_evermemos_base_url(base_url: str) -> str`.

- [x] **Step 2: Reuse helper**

Call it from `get_memory_config()` and `EverMemOSClient.__init__()`.

- [x] **Step 3: Update bundled YAML**

Change the EverMemOS cloud base URL to `https://api.evermind.ai/api/v1`.

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
make doctor backend-acceptance-smoke backend-runtime-smoke backend-chat-smoke desktop-acceptance-smoke desktop-build
```

Expected: exit 0. Optional doctor warnings are acceptable.

- [x] **Step 2: Commit and push**

Run:

```bash
git add docs/superpowers/specs/2026-07-09-evermemos-base-url-normalization-design.md docs/superpowers/plans/2026-07-09-evermemos-base-url-normalization.md providers/config.py providers/api_config.py providers/memory/evermemos/evermemos_client.py providers/memory/evermemos/memory_config.yaml tests/test_provider_config.py tests/test_security_regressions.py
git commit -m "fix: normalize evermemos cloud base url"
git push origin main
```
