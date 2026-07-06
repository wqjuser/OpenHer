# Provider Diagnostics Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a shared provider diagnostics boundary so `/api/status` and local diagnostics stop owning duplicate provider readiness logic.

**Architecture:** Add `providers/diagnostics.py` as a pure, secret-safe transformation layer over provider config dictionaries. Refactor `server/routes/health.py` to call it for provider and capability status, and refactor `scripts/doctor.py` to reuse its secret-presence helper.

**Tech Stack:** Python 3.11+, FastAPI route tests, pytest, pyright, existing Makefile quality gates.

---

### Task 1: Add Diagnostics Boundary Tests

**Files:**
- Create: `tests/test_provider_diagnostics.py`
- Modify: `tests/test_server_routes.py`
- Modify: `tests/test_doctor.py`

- [x] **Step 1: Add provider diagnostics unit tests**

Create tests requiring `providers.diagnostics` to emit the existing `/api/status` provider and capability shapes without secrets.

```python
def test_provider_capability_status_redacts_secret_values():
    from providers.diagnostics import provider_capability_status

    status = provider_capability_status({
        "provider": "deepseek",
        "available": False,
        "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        "api_key": "secret-llm-key",
    })

    assert status == {
        "provider": "deepseek",
        "available": False,
        "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        "setup_hint": "Set DEEPSEEK_API_KEY or LLM_API_KEY in .env, then restart the backend.",
    }
    assert "secret" not in repr(status)
```

- [x] **Step 2: Add memory and capability tests**

Add tests for `memory_runtime_status()` and `capabilities_status()` matching the existing status route contract.

- [x] **Step 3: Add source boundary tests**

Extend route and doctor tests:

```python
health_source = (ROOT / "server" / "routes" / "health.py").read_text(encoding="utf-8")
assert "from providers.diagnostics import" in health_source
assert "def _capability_status" not in health_source
assert "def _provider_setup_hint" not in health_source
assert "def _capabilities_status" not in health_source

doctor_source = SCRIPT.read_text(encoding="utf-8")
assert "provider_secret_configured" in doctor_source
```

- [x] **Step 4: Run tests to verify red**

Run: `.venv/bin/python -m pytest tests/test_provider_diagnostics.py tests/test_server_routes.py::test_api_status_reports_provider_readiness_without_secrets tests/test_doctor.py::test_doctor_script_exposes_secret_safe_local_contracts -v`

Expected: FAIL because `providers.diagnostics` does not exist and health/doctor still own local helper logic.

### Task 2: Implement Shared Provider Diagnostics

**Files:**
- Create: `providers/diagnostics.py`
- Modify: `server/routes/health.py`
- Modify: `scripts/doctor.py`

- [x] **Step 1: Create `providers/diagnostics.py`**

Implement:

```python
from __future__ import annotations

from typing import Any


def provider_secret_configured(cfg: dict[str, Any], active: bool = False) -> bool:
    secret_key = "api_" + "key"
    key = f"active_{secret_key}" if active else secret_key
    return bool(cfg.get(key))
```

Add `provider_setup_hint()`, `provider_capability_status()`, `memory_runtime_status()`, `provider_feature_status()`, and `capabilities_status()` with behavior matching the existing health route tests.

- [x] **Step 2: Refactor health route**

Replace local provider/capability helper definitions with imports from `providers.diagnostics`, keeping `_providers_status(ctx)` as the route-level composition point.

- [x] **Step 3: Refactor doctor secret checks**

Import `provider_secret_configured` and replace `_has_secret()` calls. Remove the local `_has_secret()` helper.

- [x] **Step 4: Run red-green tests**

Run: `.venv/bin/python -m pytest tests/test_provider_diagnostics.py tests/test_server_routes.py::test_api_status_reports_provider_readiness_without_secrets tests/test_doctor.py::test_doctor_script_exposes_secret_safe_local_contracts -v`

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-provider-diagnostics-boundary.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so each executed step is checked.

- [x] **Step 2: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_provider_diagnostics.py tests/test_server_routes.py tests/test_doctor.py tests/test_desktop_provider_readiness.py tests/test_desktop_configuration_diagnostics.py -v`

Expected: all focused diagnostics/status tests pass.

- [x] **Step 3: Run repository checks**

Run: `make check`

Expected: pyright reports 0 errors and the full pytest suite passes.

- [x] **Step 4: Run local doctor and smoke/build gates**

Run: `make doctor`, `make backend-acceptance-smoke`, and `make desktop-build`.

Expected: each command exits 0. `make doctor` may still report optional warnings depending on local configuration.

- [x] **Step 5: Commit and push**

```bash
git add docs/superpowers/specs/2026-07-06-provider-diagnostics-boundary-design.md docs/superpowers/plans/2026-07-06-provider-diagnostics-boundary.md providers/diagnostics.py server/routes/health.py scripts/doctor.py tests/test_provider_diagnostics.py tests/test_server_routes.py tests/test_doctor.py
git commit -m "refactor: share provider diagnostics"
git push origin main
```
