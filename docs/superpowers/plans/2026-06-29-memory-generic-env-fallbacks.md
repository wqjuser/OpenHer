# Memory Generic Env Fallbacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let EverMemOS memory configuration support generic `MEMORY_*` environment fallbacks while preserving `EVERMEMOS_*` provider-specific precedence.

**Architecture:** Keep `providers.config.get_memory_config()` as the single source used by bootstrap and integration smoke. Add fallback resolution for `MEMORY_API_KEY` and `MEMORY_BASE_URL`, and make `EverMemOSClient` mirror the same constructor/env behavior when used directly. Update docs and contract tests so the convention stays visible.

**Tech Stack:** Python 3.11+, pytest, existing provider config facade, existing EverMemOS HTTP client.

---

### Task 1: Add Failing Config Tests

**Files:**
- Modify: `tests/test_provider_config.py`
- Modify: `tests/test_security_regressions.py`

- [x] **Step 1: Add generic memory API-key config test**

Add a provider config test asserting `MEMORY_API_KEY` enables EverMemOS with the cloud default URL:

```python
def test_memory_config_uses_generic_api_key_with_cloud_default_url(self):
    with patch.dict(os.environ, {"MEMORY_API_KEY": "generic-memory-key"}, clear=True):
        api_config, provider_config = self._reload_configs()

        api_memory = api_config.get_memory_config()
        provider_memory = provider_config.get_memory_config()
        provider_nested = provider_config.get_memory_provider_config()["evermemos"]

    self.assertEqual(api_memory, provider_memory)
    self.assertTrue(provider_memory["enabled"])
    self.assertEqual(provider_memory["base_url"], "https://api.evermind.ai/api/v1")
    self.assertEqual(provider_memory["api_key"], "generic-memory-key")
    self.assertEqual(provider_nested, provider_memory)
```

- [x] **Step 2: Add generic memory base-url config test**

Add a provider config test asserting `MEMORY_BASE_URL` enables EverMemOS without requiring a key:

```python
def test_memory_config_uses_generic_base_url(self):
    with patch.dict(os.environ, {"MEMORY_BASE_URL": "http://memory.example.test/api/v1"}, clear=True):
        _api_config, provider_config = self._reload_configs()

        memory = provider_config.get_memory_config()

    self.assertTrue(memory["enabled"])
    self.assertEqual(memory["base_url"], "http://memory.example.test/api/v1")
    self.assertEqual(memory["api_key"], "")
```

- [x] **Step 3: Add provider-specific precedence regression test**

Add or extend a security regression asserting `EVERMEMOS_API_KEY` and `EVERMEMOS_BASE_URL` still win over generic `MEMORY_*` variables.

- [x] **Step 4: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_memory_config_uses_generic_api_key_with_cloud_default_url tests/test_provider_config.py::ProviderConfigBoundaryTests::test_memory_config_uses_generic_base_url tests/test_security_regressions.py::EverMemOSLoggingRegressionTests::test_evermemos_env_precedence_prefers_provider_specific_values -q
```

Expected: fail because `MEMORY_API_KEY` and `MEMORY_BASE_URL` are not currently read.

### Task 2: Implement Memory Fallbacks

**Files:**
- Modify: `providers/config.py`
- Modify: `providers/memory/evermemos/evermemos_client.py`

- [x] **Step 5: Resolve generic memory env in central config**

In `get_memory_config()`, resolve:

```python
env_base_url = _first_env("EVERMEMOS_BASE_URL", "MEMORY_BASE_URL")
api_key = _first_env(api_key_env, "EVERMEMOS_API_KEY", "MEMORY_API_KEY")
```

Keep the cloud default behavior: when an API key exists and no base URL exists, set `base_url` to `EVERMEMOS_CLOUD_BASE_URL`.

- [x] **Step 6: Mirror direct EverMemOSClient env fallback**

In `EverMemOSClient.__init__`, use `MEMORY_BASE_URL` and `MEMORY_API_KEY` as fallbacks when constructor args and `EVERMEMOS_*` values are absent.

- [x] **Step 7: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py tests/test_security_regressions.py::EverMemOSLoggingRegressionTests -q
```

Expected: all selected tests pass.

### Task 3: Document Memory Env Convention

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `tests/test_integration_smoke_profile.py`

- [x] **Step 8: Add documentation contract assertions**

Update integration smoke profile docs test to assert README and `.env.example` mention `MEMORY_API_KEY` and `MEMORY_BASE_URL`.

- [x] **Step 9: Verify documentation test fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_integration_smoke_profile.py::test_makefile_and_readme_document_integration_smoke -q
```

Expected: fail until the docs mention the new generic memory env vars.

- [x] **Step 10: Update `.env.example` and README**

Document that `EVERMEMOS_*` wins and `MEMORY_*` is a generic fallback:

```bash
# MEMORY_API_KEY=your_current_memory_api_key_here
# MEMORY_BASE_URL=http://localhost:1995/api/v1
```

- [x] **Step 11: Verify documentation tests pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_integration_smoke_profile.py -q
```

Expected: all integration smoke profile tests pass.

### Task 4: Verify And Ship

**Files:**
- Verify: full Python checks
- Verify: live provider smoke
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
git commit -m "feat: add generic memory env fallbacks"
```
