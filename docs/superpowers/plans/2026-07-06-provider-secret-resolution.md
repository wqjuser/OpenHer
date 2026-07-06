# Provider Secret Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize provider API-key availability and missing-key hint resolution for LLM, TTS, and Image config without changing public config dictionaries.

**Architecture:** Add a small `ResolvedProviderSecret` dataclass and pure helper functions in `providers/config.py`. Refactor `get_llm_config()`, `get_tts_config()`, and `get_image_config()` to reuse those helpers while preserving every existing return key and value.

**Tech Stack:** Python 3.11+, dataclasses, pytest, pyright, existing Makefile quality gates.

---

### Task 1: Add Secret Resolution Contract Tests

**Files:**
- Modify: `tests/test_provider_config.py`

- [x] **Step 1: Test active provider secret resolution**

Add this test inside `ProviderConfigBoundaryTests`:

```python
def test_provider_secret_resolution_prefers_provider_key_over_generic_key(self):
    from providers import config as provider_config

    preset = {"api_key_env": "DEEPSEEK_API_KEY"}
    with patch.dict(
        os.environ,
        {
            "DEEPSEEK_API_KEY": "deepseek-key",
            "LLM_API_KEY": "generic-llm-key",
        },
        clear=True,
    ):
        secret = provider_config._resolve_provider_secret("deepseek", preset, "LLM_API_KEY")

    self.assertEqual(secret.api_key, "deepseek-key")
    self.assertTrue(secret.available)
    self.assertEqual(secret.missing_key_env, "")
    self.assertEqual(secret.env_options, ["DEEPSEEK_API_KEY", "LLM_API_KEY"])
```

- [x] **Step 2: Test no-key provider availability**

Add:

```python
def test_provider_secret_resolution_marks_no_key_provider_available(self):
    from providers import config as provider_config

    secret = provider_config._resolve_provider_secret(
        "ollama",
        {"api_key_env": "", "no_key_required": True},
        "LLM_API_KEY",
    )

    self.assertEqual(secret.api_key, "")
    self.assertTrue(secret.available)
    self.assertEqual(secret.missing_key_env, "")
    self.assertEqual(secret.env_options, ["OLLAMA_API_KEY", "LLM_API_KEY"])
```

- [x] **Step 3: Test media secret map generic key scoping**

Add:

```python
def test_provider_secret_map_applies_generic_key_only_to_active_provider(self):
    from providers import config as provider_config

    providers = {
        "dashscope": {"api_key_env": "DASHSCOPE_API_KEY"},
        "openai": {"api_key_env": "OPENAI_API_KEY"},
    }
    with patch.dict(os.environ, {"TTS_API_KEY": "generic-tts-key"}, clear=True):
        api_keys, active_secret = provider_config._resolve_provider_secret_map(
            providers,
            "dashscope",
            "TTS_API_KEY",
        )

    self.assertEqual(api_keys, {
        "dashscope": "generic-tts-key",
        "openai": "",
    })
    self.assertEqual(active_secret.api_key, "generic-tts-key")
    self.assertTrue(active_secret.available)
    self.assertEqual(active_secret.missing_key_env, "")
```

- [x] **Step 4: Run tests to verify red**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_provider_secret_resolution_prefers_provider_key_over_generic_key tests/test_provider_config.py::ProviderConfigBoundaryTests::test_provider_secret_resolution_marks_no_key_provider_available tests/test_provider_config.py::ProviderConfigBoundaryTests::test_provider_secret_map_applies_generic_key_only_to_active_provider -v`

Expected: FAIL because `_resolve_provider_secret()` and `_resolve_provider_secret_map()` do not exist yet.

### Task 2: Implement Shared Secret Resolution

**Files:**
- Modify: `providers/config.py`

- [x] **Step 1: Add dataclass import and result type**

Add near the top of `providers/config.py`:

```python
from dataclasses import dataclass
```

Add after `_PROVIDER_DEFAULT_MODELS`:

```python
@dataclass(frozen=True)
class ResolvedProviderSecret:
    api_key: str
    available: bool
    missing_key_env: str
    env_options: list[str]
```

- [x] **Step 2: Add active secret helper**

Add after `_missing_key_env()`:

```python
def _resolve_provider_secret(
    provider_name: str,
    preset: dict,
    generic_env: str = "",
) -> ResolvedProviderSecret:
    env_options = _api_key_env_options(
        provider_name,
        str(preset.get("api_key_env") or ""),
        generic_env,
    )
    api_key = _first_env(*env_options)
    available = bool(preset.get("no_key_required", False)) or bool(api_key)
    missing_key_env = "" if available else _missing_key_env(env_options)
    return ResolvedProviderSecret(
        api_key=api_key,
        available=available,
        missing_key_env=missing_key_env,
        env_options=env_options,
    )
```

- [x] **Step 3: Add media secret map helper**

Add:

```python
def _resolve_provider_secret_map(
    providers: dict,
    active_provider: str,
    generic_env: str,
) -> tuple[dict[str, str], ResolvedProviderSecret]:
    api_keys = {}
    active_secret: ResolvedProviderSecret | None = None
    for name, provider_cfg in providers.items():
        preset = provider_cfg if isinstance(provider_cfg, dict) else {}
        secret = _resolve_provider_secret(
            name,
            preset,
            generic_env if name == active_provider else "",
        )
        api_keys[name] = secret.api_key
        if name == active_provider:
            active_secret = secret
    if active_secret is None:
        active_secret = _resolve_provider_secret(active_provider, {}, generic_env)
    return api_keys, active_secret
```

- [x] **Step 4: Refactor `get_llm_config()`**

Replace local `api_key_env_options`, `api_key`, `available`, and `missing_key_env` assignment with:

```python
secret = _resolve_provider_secret(provider_name, preset, "LLM_API_KEY")
```

Then return:

```python
"api_key": secret.api_key,
"available": secret.available,
"missing_key_env": secret.missing_key_env,
```

- [x] **Step 5: Refactor `get_tts_config()`**

Replace the media `api_keys` loop and active availability calculation with:

```python
api_keys, active_secret = _resolve_provider_secret_map(providers, provider_name, "TTS_API_KEY")
```

Then return:

```python
"active_api_key": active_secret.api_key,
"available": active_secret.available,
"missing_key_env": active_secret.missing_key_env,
```

- [x] **Step 6: Refactor `get_image_config()`**

Apply the same pattern with:

```python
api_keys, active_secret = _resolve_provider_secret_map(providers, provider_name, "IMAGE_API_KEY")
```

Then return `active_secret` values for the active key, availability, and missing key.

- [x] **Step 7: Run provider config tests**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py -v`

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-provider-secret-resolution.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so every executed step is checked.

- [x] **Step 2: Run focused provider diagnostics tests**

Run: `.venv/bin/python -m pytest tests/test_provider_config.py tests/test_provider_diagnostics.py tests/test_doctor.py tests/test_server_routes.py -v`

Expected: all focused config, diagnostics, doctor, and backend status tests pass.

- [x] **Step 3: Run repository checks**

Run: `make check`

Expected: pyright reports 0 errors and the full pytest suite passes.

- [x] **Step 4: Run local doctor and smoke/build gates**

Run: `make doctor`, `make backend-acceptance-smoke`, and `make desktop-build`.

Expected: each command exits 0. `make doctor` may report optional warnings for unconfigured optional providers or missing local backups.

- [x] **Step 5: Commit and push**

```bash
git add docs/superpowers/specs/2026-07-06-provider-secret-resolution-design.md docs/superpowers/plans/2026-07-06-provider-secret-resolution.md providers/config.py tests/test_provider_config.py
git commit -m "refactor: centralize provider secret resolution"
git push origin main
```
