# LLM Availability Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose LLM provider availability in central config and let the opt-in integration smoke profile skip unconfigured LLM providers with a clear reason.

**Architecture:** Extend `providers.config.get_llm_config()` with `available` and `missing_key_env`, matching TTS/Image semantics while honoring no-key providers like Ollama. Keep runtime chat startup unchanged; only the diagnostic smoke script uses the availability flag to avoid noisy failures when credentials are absent.

**Tech Stack:** Python 3.11+, pytest, existing provider config facade, existing integration smoke script.

---

### Task 1: Add Failing LLM Availability Tests

**Files:**
- Modify: `tests/test_provider_config.py`
- Modify: `tests/test_integration_smoke_profile.py`

- [x] **Step 1: Add missing-key LLM config test**

Add a provider config test asserting a key-required selected provider reports unavailable when no provider-specific key or `LLM_API_KEY` exists:

```python
def test_llm_config_marks_key_required_provider_unavailable_when_key_is_missing(self):
    with patch.dict(os.environ, {"DEFAULT_PROVIDER": "deepseek"}, clear=True):
        _api_config, provider_config = self._reload_configs()

        llm = provider_config.get_llm_config()

    self.assertEqual(llm["provider"], "deepseek")
    self.assertFalse(llm["available"])
    self.assertEqual(llm["api_key"], "")
    self.assertEqual(llm["missing_key_env"], "DEEPSEEK_API_KEY or LLM_API_KEY")
```

- [x] **Step 2: Add no-key LLM provider availability test**

Add a provider config test asserting Ollama is available without a key:

```python
def test_llm_config_marks_no_key_provider_available_without_key(self):
    with patch.dict(os.environ, {"DEFAULT_PROVIDER": "ollama"}, clear=True):
        _api_config, provider_config = self._reload_configs()

        llm = provider_config.get_llm_config()

    self.assertEqual(llm["provider"], "ollama")
    self.assertTrue(llm["available"])
    self.assertEqual(llm["api_key"], "")
    self.assertEqual(llm["missing_key_env"], "")
```

- [x] **Step 3: Add integration smoke skip test**

Add an async test patching `providers.config.get_llm_config()` to return `available=False` and patching `providers.llm.client.LLMClient` with a class that raises if constructed. Assert `smoke_llm_chat()` returns:

```python
{"status": "skipped", "provider": "deepseek", "reason": "DEEPSEEK_API_KEY or LLM_API_KEY"}
```

- [x] **Step 4: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_llm_config_marks_key_required_provider_unavailable_when_key_is_missing tests/test_provider_config.py::ProviderConfigBoundaryTests::test_llm_config_marks_no_key_provider_available_without_key tests/test_integration_smoke_profile.py::test_llm_smoke_skips_when_provider_is_unavailable -q
```

Expected: fail because LLM config does not expose `available`/`missing_key_env`, and `smoke_llm_chat()` ignores unavailable state.

### Task 2: Implement LLM Availability

**Files:**
- Modify: `providers/config.py`
- Modify: `scripts/integration/provider_smoke.py`

- [x] **Step 5: Add LLM availability fields**

In `get_llm_config()`, calculate:

```python
api_key_env_options = _api_key_env_options(provider_name, api_key_env, "LLM_API_KEY")
no_key_required = bool(preset.get("no_key_required", False))
available = no_key_required or bool(api_key)
missing_key_env = "" if available else _missing_key_env(api_key_env_options)
```

Return `available`, `missing_key_env`, and `active_provider_config`.

- [x] **Step 6: Skip unavailable LLM smoke**

In `smoke_llm_chat()`, before constructing `LLMClient`, return a skipped result when `llm_cfg["available"]` is false:

```python
if not bool(llm_cfg.get("available", True)):
    reason = str(llm_cfg.get("missing_key_env") or "not_configured")
    return {"status": "skipped", "provider": provider, "reason": reason}
```

- [x] **Step 7: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py tests/test_integration_smoke_profile.py -q
```

Expected: all provider config and integration smoke profile tests pass.

### Task 3: Verify And Ship

**Files:**
- Verify: full Python checks
- Verify: live provider smoke
- Verify: macOS Swift package build

- [x] **Step 8: Run full checks**

Run:

```bash
source .venv/bin/activate && make check
```

- [x] **Step 9: Run runtime smoke and desktop build**

Run:

```bash
source .venv/bin/activate && make integration-smoke
cd desktop/OpenHer && swift build
```

- [x] **Step 10: Commit, merge to main, and push**

Commit message:

```bash
git commit -m "feat: expose llm provider availability"
```
