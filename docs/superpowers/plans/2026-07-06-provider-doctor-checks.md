# Provider Doctor Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move LLM/TTS/Image doctor check construction into `providers.diagnostics` while preserving existing doctor output.

**Architecture:** Add `required_provider_doctor_check()` and `optional_provider_doctor_check()` to `providers/diagnostics.py`, then make `scripts/doctor.py` call those helpers for provider checks. Keep memory/data/backup checks local to doctor because they depend on runtime data and backup context.

**Tech Stack:** Python 3.11+, pytest, pyright, existing Makefile quality gates.

---

### Task 1: Add Provider Doctor Check Regression Tests

**Files:**
- Modify: `tests/test_provider_diagnostics.py`
- Modify: `tests/test_doctor.py`

- [x] **Step 1: Add required provider doctor check tests**

Add tests requiring the diagnostics module to construct the existing LLM doctor check shape.

```python
def test_required_provider_doctor_check_matches_llm_doctor_contract():
    from providers.diagnostics import required_provider_doctor_check

    check = required_provider_doctor_check("LLM", {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "available": False,
        "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        "api_key": "secret-llm-key",
        "base_url": "https://api.deepseek.com",
    })

    assert check["status"] == "error"
    assert check["message"] == "Missing required LLM key: DEEPSEEK_API_KEY or LLM_API_KEY"
    assert "DEEPSEEK_API_KEY or LLM_API_KEY" in check["setup_hint"]
    assert check["details"] == {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "api_key_configured": True,
        "base_url_configured": True,
        "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
    }
    assert "secret" not in repr(check)
```

- [x] **Step 2: Add optional provider doctor check tests**

Add tests requiring the diagnostics module to construct existing TTS/Image-style optional warning checks and include model when present.

- [x] **Step 3: Add doctor source boundary tests**

Extend `test_doctor_script_exposes_secret_safe_local_contracts()`:

```python
assert "required_provider_doctor_check" in source
assert "optional_provider_doctor_check" in source
assert "def _llm_check" not in source
assert "def _optional_provider_check" not in source
```

- [x] **Step 4: Run tests to verify red**

Run: `.venv/bin/python -m pytest tests/test_provider_diagnostics.py tests/test_doctor.py::test_doctor_script_exposes_secret_safe_local_contracts -v`

Expected: FAIL because the new diagnostics helpers do not exist and doctor still defines local provider check builders.

### Task 2: Implement Shared Doctor Provider Checks

**Files:**
- Modify: `providers/diagnostics.py`
- Modify: `scripts/doctor.py`

- [x] **Step 1: Add check builder helper**

Add a private `_diagnostic_check()` helper in `providers/diagnostics.py` so doctor check helpers reuse the existing check shape.

```python
def _diagnostic_check(status: str, message: str, setup_hint: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "setup_hint": setup_hint,
        "details": details,
    }
```

- [x] **Step 2: Implement required provider doctor check**

Add `required_provider_doctor_check(label, cfg)` with the current LLM behavior.

- [x] **Step 3: Implement optional provider doctor check**

Add `optional_provider_doctor_check(label, cfg)` with the current TTS/Image behavior.

- [x] **Step 4: Refactor doctor to use shared helpers**

Import both helpers and replace:

```python
"llm": _llm_check(get_llm_config()),
"tts": _optional_provider_check("TTS", get_tts_config()),
"image": _optional_provider_check("Image", get_image_config()),
```

with:

```python
"llm": required_provider_doctor_check("LLM", get_llm_config()),
"tts": optional_provider_doctor_check("TTS", get_tts_config()),
"image": optional_provider_doctor_check("Image", get_image_config()),
```

Then remove `_llm_check()` and `_optional_provider_check()` from `scripts/doctor.py`.

- [x] **Step 5: Run red-green tests**

Run: `.venv/bin/python -m pytest tests/test_provider_diagnostics.py tests/test_doctor.py -v`

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-provider-doctor-checks.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so every executed step is checked.

- [x] **Step 2: Run focused diagnostics tests**

Run: `.venv/bin/python -m pytest tests/test_provider_diagnostics.py tests/test_doctor.py tests/test_server_routes.py -v`

Expected: all focused diagnostics and status tests pass.

- [x] **Step 3: Run repository checks**

Run: `make check`

Expected: pyright reports 0 errors and the full pytest suite passes.

- [x] **Step 4: Run local doctor and smoke/build gates**

Run: `make doctor`, `make backend-acceptance-smoke`, and `make desktop-build`.

Expected: each command exits 0. `make doctor` may still report optional warnings depending on local configuration.

- [x] **Step 5: Commit and push**

```bash
git add docs/superpowers/specs/2026-07-06-provider-doctor-checks-design.md docs/superpowers/plans/2026-07-06-provider-doctor-checks.md providers/diagnostics.py scripts/doctor.py tests/test_provider_diagnostics.py tests/test_doctor.py
git commit -m "refactor: share provider doctor checks"
git push origin main
```
