# Provider Config Single Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `providers.config.get_llm_config()` the single source of truth for LLM provider resolution used by the registry.

**Architecture:** `providers.registry.get_llm()` will keep responsibility for provider class lookup and explicit argument overrides, but it will stop duplicating env fallback and base URL resolution. The registry will consume the full resolved config from `get_llm_config()` and pass those values into provider constructors.

**Tech Stack:** Python 3.11+, pytest/unittest, existing provider registry/config modules.

---

### Task 1: Lock Registry Against Duplicated LLM Resolution

**Files:**
- Modify: `tests/test_provider_config.py`
- Modify: `providers/registry.py`

- [x] **Step 1: Write the failing test**

Add a regression test that patches `providers.registry.get_llm_config()` to return a central resolved config that intentionally differs from environment variables. A fake provider captures constructor arguments, proving `get_llm()` uses the central config rather than recomputing env fallback locally.

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_registry_reuses_central_llm_config_resolution -q`

Expected: FAIL because `providers.registry` does not yet expose or call `get_llm_config()`.

- [x] **Step 3: Write minimal implementation**

Update `providers/registry.py` to import `get_llm_config`, remove local LLM env helper functions, and resolve LLM constructor defaults from the central config:

```python
cfg = get_llm_config(provider)
provider_name = cfg["provider"]
resolved_model = model or cfg["model"]
resolved_key = api_key or cfg.get("api_key") or None
resolved_url = base_url or cfg.get("base_url") or None
```

- [x] **Step 4: Run target tests**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py tests/test_security_regressions.py::DeepSeekProviderRegressionTests tests/test_integration_smoke_profile.py -q`

Expected: PASS.

- [x] **Step 5: Run full verification**

Run: `source .venv/bin/activate && make check`

Run: `source .venv/bin/activate && make integration-smoke`

Run: `cd desktop/OpenHer && swift build`

Expected: all commands exit 0.
