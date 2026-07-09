# EverMemOS Client Placeholder Secret Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent direct EverMemOS client construction from using placeholder API keys.

**Architecture:** Import and reuse the existing `_configured_secret()` helper in `providers/memory/evermemos/evermemos_client.py`. Add one focused regression in `tests/test_security_regressions.py`.

**Tech Stack:** Python 3.11+, pytest, pyright.

## Global Constraints

- Do not change real EverMemOS key precedence.
- Do not change base URL behavior.
- Do not add dependencies.

---

### Task 1: Test And Fix EverMemOS Client Placeholder Secrets

**Files:**
- Modify: `tests/test_security_regressions.py`
- Modify: `providers/memory/evermemos/evermemos_client.py`

- [x] **Step 1: Add red regression**

Add a test asserting `EverMemOSClient()` ignores placeholder `EVERMEMOS_API_KEY` and `MEMORY_API_KEY` values from env fallback and omits the Authorization header.

- [x] **Step 2: Run red test**

Run:

```bash
.venv/bin/python -m pytest tests/test_security_regressions.py::EverMemOSLoggingRegressionTests::test_evermemos_client_ignores_placeholder_env_api_keys -q
```

Expected: FAIL because the client currently stores the placeholder key.

- [x] **Step 3: Reuse `_configured_secret()`**

Import `_configured_secret` from `providers.config` and wrap the client API-key fallback expression with it.

- [x] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_security_regressions.py::EverMemOSLoggingRegressionTests tests/test_provider_config.py -v
```

Expected: PASS.

### Task 2: Verify And Ship

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
git add docs/superpowers/specs/2026-07-09-evermemos-client-placeholder-secret-design.md docs/superpowers/plans/2026-07-09-evermemos-client-placeholder-secret.md providers/memory/evermemos/evermemos_client.py tests/test_security_regressions.py
git commit -m "fix: ignore evermemos client placeholder keys"
git push origin main
```
