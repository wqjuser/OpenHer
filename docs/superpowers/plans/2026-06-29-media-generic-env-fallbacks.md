# Media Generic Env Fallbacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let TTS and image providers use modality-level API-key fallbacks, matching the existing LLM generic fallback convention.

**Architecture:** Keep `providers.config` as the single source of truth. Add a small helper that resolves provider-specific API-key env vars first and then falls back to `TTS_API_KEY` or `IMAGE_API_KEY` only for the selected provider. Preserve existing provider-specific env behavior and availability semantics.

**Tech Stack:** Python 3.11+, pytest, existing provider config and registry tests.

---

### Task 1: Add Failing Config Tests

**Files:**
- Modify: `tests/test_provider_config.py`

- [x] **Step 1: Add TTS generic fallback test**

Add a test asserting `get_tts_config()` uses `TTS_API_KEY` for the selected provider when `DASHSCOPE_API_KEY` is absent:

```python
def test_tts_config_uses_generic_api_key_for_active_provider(self):
    with patch.dict(os.environ, {"TTS_API_KEY": "generic-tts-key"}, clear=True):
        _api_config, provider_config = self._reload_configs()

        tts = provider_config.get_tts_config()

    self.assertTrue(tts["available"])
    self.assertEqual(tts["provider"], "dashscope")
    self.assertEqual(tts["active_api_key"], "generic-tts-key")
    self.assertEqual(tts["api_keys"]["dashscope"], "generic-tts-key")
    self.assertEqual(tts["api_keys"].get("openai", ""), "")
    self.assertEqual(tts["missing_key_env"], "")
```

- [x] **Step 2: Add image generic fallback test**

Add a test asserting `get_image_config()` uses `IMAGE_API_KEY` for the selected provider when `GEMINI_API_KEY` is absent:

```python
def test_image_config_uses_generic_api_key_for_active_provider(self):
    with patch.dict(os.environ, {"IMAGE_API_KEY": "generic-image-key"}, clear=True):
        _api_config, provider_config = self._reload_configs()

        image = provider_config.get_image_config()

    self.assertTrue(image["available"])
    self.assertEqual(image["provider"], "gemini")
    self.assertEqual(image["active_api_key"], "generic-image-key")
    self.assertEqual(image["api_keys"]["gemini"], "generic-image-key")
    self.assertEqual(image["missing_key_env"], "")
```

- [x] **Step 3: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_tts_config_uses_generic_api_key_for_active_provider tests/test_provider_config.py::ProviderConfigBoundaryTests::test_image_config_uses_generic_api_key_for_active_provider -q
```

Expected: both tests fail because `providers.config` does not currently read `TTS_API_KEY` or `IMAGE_API_KEY`.

### Task 2: Implement Generic Media Fallbacks

**Files:**
- Modify: `providers/config.py`

- [x] **Step 4: Add reusable media key resolver**

Add helpers near `_first_env`:

```python
def _api_key_env_options(provider: str, preset_env: str, generic_env: str) -> list[str]:
    provider_env = f"{_provider_env_prefix(provider)}_API_KEY"
    return list(dict.fromkeys([preset_env, provider_env, generic_env]))


def _missing_key_env(options: list[str]) -> str:
    return " or ".join(name for name in options if name)
```

- [x] **Step 5: Use resolver in TTS config**

In `get_tts_config()`, resolve `api_keys` with provider-specific env vars first and `TTS_API_KEY` only for the selected provider.

- [x] **Step 6: Use resolver in image config**

In `get_image_config()`, resolve `api_keys` with provider-specific env vars first and `IMAGE_API_KEY` only for the selected provider.

- [x] **Step 7: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py -q
```

Expected: all provider config tests pass.

### Task 3: Document Configuration Convention

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `tests/test_integration_smoke_profile.py`

- [x] **Step 8: Add documentation contract test**

Update `test_makefile_and_readme_document_integration_smoke()` or add a focused test asserting README and `.env.example` mention `TTS_API_KEY` and `IMAGE_API_KEY`.

- [x] **Step 9: Verify documentation test fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_integration_smoke_profile.py::test_makefile_and_readme_document_integration_smoke -q
```

Expected: fail until README and `.env.example` document the new env convention.

- [x] **Step 10: Update `.env.example` and README**

Document:

```bash
# TTS_API_KEY=your_current_tts_api_key_here
# IMAGE_API_KEY=your_current_image_api_key_here
```

State that provider-specific variables still win over the generic fallback.

- [x] **Step 11: Verify documentation tests pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_integration_smoke_profile.py -q
```

Expected: all integration smoke profile contract tests pass.

### Task 4: Verify And Ship

**Files:**
- Verify: full Python checks
- Verify: live smoke profile
- Verify: macOS Swift package build

- [x] **Step 12: Run full checks**

Run:

```bash
source .venv/bin/activate && make check
```

- [x] **Step 13: Run runtime smoke and desktop build**

Run:

```bash
source .venv/bin/activate && make integration-smoke
cd desktop/OpenHer && swift build
```

- [x] **Step 14: Commit, merge to main, and push**

Commit message:

```bash
git commit -m "feat: add generic media api key fallbacks"
```
