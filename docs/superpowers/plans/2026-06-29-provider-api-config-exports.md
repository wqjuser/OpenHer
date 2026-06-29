# Provider API Config Exports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `providers.api_config` as a complete backward-compatible facade for all central provider configuration entrypoints.

**Architecture:** `providers.api_config` will re-export every public resolver from `providers.config` that callers may reasonably use: LLM, TTS, Memory, Image, and their compatibility provider-config shapes. Contract tests will compare the wrapper functions against `providers.config` directly and assert the facade `__all__` remains complete.

**Tech Stack:** Python 3.11+, unittest/pytest, existing provider config modules.

---

### Task 1: Complete Provider API Config Facade

**Files:**
- Modify: `tests/test_provider_config.py`
- Modify: `providers/api_config.py`

- [x] **Step 1: Write the failing tests**

Add tests that assert `providers.api_config.__all__` includes all provider resolver functions and that image/TTS facade functions delegate to `providers.config`.

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_api_config_exports_all_provider_config_entrypoints -q`

Expected: FAIL because `providers.api_config` does not expose `get_image_config`.

- [x] **Step 3: Write minimal implementation**

Update `providers/api_config.py` to import and include these names in `__all__`:

```python
get_llm_provider_config
get_tts_provider_config
get_memory_provider_config
get_image_config
get_image_provider_config
```

- [x] **Step 4: Run target tests**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py -q`

Expected: PASS.

- [x] **Step 5: Run full verification**

Run: `source .venv/bin/activate && make check`

Run: `source .venv/bin/activate && make integration-smoke`

Run: `cd desktop/OpenHer && swift build`

Expected: all commands exit 0.
