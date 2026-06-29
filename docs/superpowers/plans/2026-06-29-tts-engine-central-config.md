# TTS Engine Central Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the legacy `TTSEngine` facade consume `providers.config.get_tts_config()` instead of duplicating provider API-key resolution.

**Architecture:** Keep `TTSEngine` as the compatibility facade used by server media routes and WebSocket TTS. Move provider key/model/cache resolution into the existing central provider config facade, then let `TTSEngine` call `providers.registry.get_tts()` with only resolved overrides. Simplify server bootstrap so it passes provider and cache directory, while availability and skill registration still come from one `get_tts_config()` result.

**Tech Stack:** Python 3.11+, pytest, existing provider config facade, existing provider registry.

---

### Task 1: Add Central Config Contract Test

**Files:**
- Modify: `tests/test_provider_config.py`

- [x] **Step 1: Write the failing test**

Add a test that patches `providers.media.tts_engine.get_tts_config` to return a central MiniMax config and patches `providers.registry.get_tts` to capture factory kwargs. The expected factory call must use `central-minimax-key` and `central-minimax-model`, not environment fallbacks.

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_tts_engine_reuses_central_config_resolution -q`

Expected: FAIL because `TTSEngine` does not currently call `get_tts_config()`.

### Task 2: Refactor TTSEngine

**Files:**
- Modify: `providers/media/tts_engine.py`

- [x] **Step 3: Resolve active provider/cache via central config**

Import `get_tts_config`, allow `provider=None`, and use central config to choose the active provider and default cache directory.

- [x] **Step 4: Resolve per-provider API keys/models via central config**

In `_get_provider`, call `get_tts_config(provider_name)` and pass the active provider key/model to `get_tts()`, while explicit constructor API-key arguments remain overrides.

- [x] **Step 5: Remove direct provider env-var reads from TTSEngine**

Keep `os.makedirs` but remove all `os.getenv("OPENAI_API_KEY")`, `os.getenv("DASHSCOPE_API_KEY")`, and `os.getenv("MINIMAX_API_KEY")` reads from the facade.

### Task 3: Simplify Bootstrap

**Files:**
- Modify: `server/bootstrap.py`

- [x] **Step 6: Stop expanding all TTS provider keys in bootstrap**

Construct `TTSEngine` with only active provider and cache directory. Continue using `tts_available` from `get_tts_config()` for voice tool registration and WebSocket TTS enablement.

### Task 4: Verify And Commit

**Files:**
- Verify: `tests/test_provider_config.py`
- Verify: full project quality gates

- [x] **Step 7: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py -q`

- [x] **Step 8: Run project checks**

Run: `source .venv/bin/activate && make check`

- [x] **Step 9: Run runtime smoke and desktop build**

Run: `source .venv/bin/activate && make integration-smoke`

Run: `cd desktop/OpenHer && swift build`

- [x] **Step 10: Commit, merge to main, and push**

Commit message: `refactor: centralize tts engine config resolution`
