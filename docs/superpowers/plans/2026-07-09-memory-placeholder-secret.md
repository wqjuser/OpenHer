# Memory Placeholder Secret Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent placeholder EverMemOS API keys from enabling memory.

**Architecture:** Reuse `_configured_secret()` in `providers/config.py` for memory API-key resolution. Add focused tests that fail before the production change.

**Tech Stack:** Python 3.11+, pytest, pyright.

## Global Constraints

- Do not change real EverMemOS key or base URL precedence.
- Do not add dependencies.
- Do not filter base URLs with secret-specific logic.

---

### Task 1: Test And Fix Memory Placeholder Secrets

**Files:**
- Modify: `tests/test_provider_config.py`
- Modify: `providers/config.py`

- [x] **Step 1: Add red tests**

Add tests asserting placeholder `EVERMEMOS_API_KEY` and `MEMORY_API_KEY` values do not enable memory.

- [x] **Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_memory_config_ignores_provider_placeholder_api_key tests/test_provider_config.py::ProviderConfigBoundaryTests::test_memory_config_ignores_generic_placeholder_api_key -q
```

Expected: FAIL because memory currently accepts placeholder API keys.

- [x] **Step 3: Reuse `_configured_secret()`**

Wrap memory API-key resolution with `_configured_secret()`.

- [x] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py -v
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
git add docs/superpowers/specs/2026-07-09-memory-placeholder-secret-design.md docs/superpowers/plans/2026-07-09-memory-placeholder-secret.md providers/config.py tests/test_provider_config.py
git commit -m "fix: ignore memory placeholder keys"
git push origin main
```
