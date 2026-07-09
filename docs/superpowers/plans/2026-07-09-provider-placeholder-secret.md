# Provider Placeholder Secret Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent placeholder API keys copied from `.env.example` from marking providers as configured.

**Architecture:** Add one small placeholder filter in `providers/config.py` and reuse the existing provider secret resolution path. Update `.env.example` so placeholder keys are comments.

**Tech Stack:** Python 3.11+, pytest, pyright.

## Global Constraints

- Do not change real provider key precedence.
- Do not add dependencies.
- Do not filter base URL placeholders through secret-specific logic.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `tests/test_provider_config.py`
- Modify: `tests/test_integration_smoke_profile.py`

- [x] **Step 1: Add provider secret placeholder test**

Assert `DASHSCOPE_API_KEY=your_dashscope_api_key_here` does not make DashScope available.

- [x] **Step 2: Add env example contract test**

Assert `.env.example` does not contain active `API_KEY=your_*` placeholder assignments.

- [x] **Step 3: Run red tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_provider_secret_resolution_ignores_placeholder_values tests/test_integration_smoke_profile.py::test_env_example_does_not_ship_active_placeholder_api_keys -q
```

Expected: FAIL because placeholders are currently accepted and `.env.example` has an active DashScope placeholder.

### Task 2: Implement

**Files:**
- Modify: `providers/config.py`
- Modify: `.env.example`

- [x] **Step 1: Add placeholder filter**

Add a helper that returns empty string for values shaped like `your_*key*_here`.

- [x] **Step 2: Use it for provider secrets**

Call the helper inside `_resolve_provider_secret()` after `_first_env()`.

- [x] **Step 3: Comment sample key**

Change active `DASHSCOPE_API_KEY=your_dashscope_api_key_here` to a commented example.

- [x] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py tests/test_integration_smoke_profile.py::test_env_example_does_not_ship_active_placeholder_api_keys -v
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
git add docs/superpowers/specs/2026-07-09-provider-placeholder-secret-design.md docs/superpowers/plans/2026-07-09-provider-placeholder-secret.md providers/config.py .env.example tests/test_provider_config.py tests/test_integration_smoke_profile.py
git commit -m "fix: ignore placeholder provider keys"
git push origin main
```
