# Status Provider Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose safe provider readiness details from `/api/status` so operators and clients can see which configured capabilities are available without leaking secrets.

**Architecture:** Keep `/api/status` backward compatible by preserving existing top-level fields and adding a new `providers` object. Resolve provider readiness through the central config helpers already used by runtime startup and smoke checks. Do not return API keys, base URLs, model names, or raw provider config blobs.

**Tech Stack:** Python 3.11+, FastAPI, pytest, TestClient, existing provider config facade.

---

### Task 1: Add Failing Status Contract Tests

**Files:**
- Modify: `tests/test_server_routes.py`

- [x] **Step 1: Add provider readiness status test**

Add a test that patches `server.routes.health` config helpers and asserts `/api/status` includes a safe `providers` snapshot:

```python
def test_api_status_reports_provider_readiness_without_secrets():
    from fastapi.testclient import TestClient
    import main
    from server.context import AppContext

    app = main.create_app(AppContext())

    with patch("server.routes.health.get_llm_config", return_value={
        "provider": "deepseek",
        "available": False,
        "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        "api_key": "secret-llm-key",
    }):
        with patch("server.routes.health.get_tts_config", return_value={
            "provider": "dashscope",
            "available": False,
            "missing_key_env": "DASHSCOPE_API_KEY or TTS_API_KEY",
            "active_api_key": "secret-tts-key",
        }):
            with patch("server.routes.health.get_image_config", return_value={
                "provider": "gemini",
                "available": True,
                "missing_key_env": "",
                "active_api_key": "secret-image-key",
            }):
                with patch("server.routes.health.get_memory_config", return_value={
                    "enabled": True,
                    "base_url": "https://memory.example.test/api/v1",
                    "api_key": "secret-memory-key",
                }):
                    response = TestClient(app, raise_server_exceptions=False).get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["providers"] == {
        "llm": {
            "provider": "deepseek",
            "available": False,
            "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        },
        "tts": {
            "provider": "dashscope",
            "available": False,
            "missing_key_env": "DASHSCOPE_API_KEY or TTS_API_KEY",
        },
        "image": {
            "provider": "gemini",
            "available": True,
            "missing_key_env": "",
        },
        "memory": {
            "provider": "evermemos",
            "enabled": True,
            "configured": True,
            "available": False,
        },
    }
    assert "secret" not in response.text
    assert "memory.example.test" not in response.text
```

- [x] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_server_routes.py::test_api_status_reports_provider_readiness_without_secrets -q
```

Expected: fail because `/api/status` does not include `providers`.

### Task 2: Implement Safe Provider Snapshot

**Files:**
- Modify: `server/routes/health.py`

- [x] **Step 3: Import central provider config helpers**

Import:

```python
from providers.api_config import get_image_config, get_llm_config, get_memory_config, get_tts_config
```

- [x] **Step 4: Add provider status helpers**

Add helpers:

```python
def _capability_status(cfg: dict) -> dict:
    return {
        "provider": str(cfg.get("provider") or ""),
        "available": bool(cfg.get("available", False)),
        "missing_key_env": str(cfg.get("missing_key_env") or ""),
    }


def _memory_status(ctx) -> dict:
    cfg = get_memory_config()
    return {
        "provider": "evermemos",
        "enabled": bool(cfg.get("enabled", False)),
        "configured": bool(cfg.get("base_url") or cfg.get("api_key")),
        "available": bool(ctx.evermemos and ctx.evermemos.available),
    }


def _providers_status(ctx) -> dict:
    return {
        "llm": _capability_status(get_llm_config()),
        "tts": _capability_status(get_tts_config()),
        "image": _capability_status(get_image_config()),
        "memory": _memory_status(ctx),
    }
```

- [x] **Step 5: Include providers in `/api/status`**

Add `"providers": _providers_status(ctx)` to the existing response without changing existing top-level fields.

- [x] **Step 6: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_server_routes.py tests/test_observability.py -q
```

Expected: all status and observability route tests pass.

### Task 3: Verify And Ship

**Files:**
- Verify: full Python checks
- Verify: live provider smoke
- Verify: macOS Swift package build

- [x] **Step 7: Run full checks**

Run:

```bash
source .venv/bin/activate && make check
```

- [x] **Step 8: Run runtime smoke and desktop build**

Run:

```bash
source .venv/bin/activate && make integration-smoke
cd desktop/OpenHer && swift build
```

- [x] **Step 9: Commit, merge to main, and push**

Commit message:

```bash
git commit -m "feat: expose provider readiness in status"
```
