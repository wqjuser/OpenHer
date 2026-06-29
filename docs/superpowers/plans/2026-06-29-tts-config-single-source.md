# TTS Config Single Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `providers.config.get_tts_config()` the single source of truth for TTS provider resolution used by the registry.

**Architecture:** `providers.registry.get_tts()` will keep responsibility for provider class lookup and explicit constructor overrides, but it will stop duplicating API-key and provider-preset resolution. `get_tts_config(provider)` will support provider overrides and return the active provider preset so registry consumers can create DashScope, OpenAI, and MiniMax providers from the same resolved configuration used by server bootstrap.

**Tech Stack:** Python 3.11+, pytest/unittest, existing provider registry/config modules.

---

### Task 1: Centralize TTS Registry Resolution

**Files:**
- Modify: `tests/test_provider_config.py`
- Modify: `providers/config.py`
- Modify: `providers/registry.py`

- [x] **Step 1: Write the failing tests**

Add regression tests proving `providers.registry.get_tts()` calls `get_tts_config()` and uses its resolved `provider`, `cache_dir`, `active_api_key`, and model values instead of recomputing env fallback locally. Add a provider-override test proving `get_tts(provider="openai")` resolves OpenAI config even when the active config defaults to DashScope.

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_registry_reuses_central_tts_config_resolution -q`

Expected: FAIL because `providers.registry` does not yet expose or call `get_tts_config()`.

- [x] **Step 3: Write minimal implementation**

Update `providers.config.get_tts_config(provider=None)` to support provider override and return `active_provider_config`. Update `providers.registry.get_tts()` to import `get_tts_config`, resolve defaults from it, and pass provider-specific constructor kwargs:

```python
cfg = get_tts_config(provider)
provider_name = cfg["provider"]
resolved_cache = cache_dir or cfg["cache_dir"]
resolved_key = api_key or cfg.get("active_api_key") or None
```

- [x] **Step 4: Run target tests**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py tests/test_security_regressions.py::TTSResultRegressionTests -q`

Expected: PASS.

- [x] **Step 5: Run full verification**

Run: `source .venv/bin/activate && make check`

Run: `source .venv/bin/activate && make integration-smoke`

Run: `cd desktop/OpenHer && swift build`

Expected: all commands exit 0.
