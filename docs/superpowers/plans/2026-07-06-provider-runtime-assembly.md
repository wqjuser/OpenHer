# Provider Runtime Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move LLM/TTS/Image runtime service construction out of `server/bootstrap.py` into a focused provider runtime module.

**Architecture:** Add `server/provider_runtime.py` with `ProviderRuntimeServices` and `build_provider_runtime_services()`. Bootstrap will call the builder, assign returned services to `AppContext`, print returned warnings, and continue owning persona/data/memory/session/proactive orchestration.

**Tech Stack:** Python 3.11+, dataclasses, pytest, pyright, existing FastAPI runtime and Makefile gates.

---

### Task 1: Add Provider Runtime Boundary Tests

**Files:**
- Create: `tests/test_provider_runtime.py`
- Modify: `tests/test_server_bootstrap.py`
- Modify: `tests/test_media_api_service.py`

- [x] **Step 1: Add provider runtime unit tests**

Create `tests/test_provider_runtime.py`:

```python
"""Provider runtime assembly boundary tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FakeService:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_provider_runtime_builds_available_services_with_injected_factories(tmp_path):
    from server.provider_runtime import build_provider_runtime_services

    llm_calls: list[dict[str, Any]] = []
    tts_calls: list[dict[str, Any]] = []
    ws_calls: list[dict[str, Any]] = []
    media_calls: list[dict[str, Any]] = []

    def llm_factory(**kwargs: Any) -> FakeService:
        llm_calls.append(kwargs)
        return FakeService(**kwargs)

    def tts_factory(**kwargs: Any) -> FakeService:
        tts_calls.append(kwargs)
        return FakeService(**kwargs)

    def ws_factory(**kwargs: Any) -> FakeService:
        ws_calls.append(kwargs)
        return FakeService(**kwargs)

    def media_factory(**kwargs: Any) -> FakeService:
        media_calls.append(kwargs)
        return FakeService(**kwargs)

    runtime = build_provider_runtime_services(
        tmp_path,
        llm_config={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "available": True,
            "temperature": 0.2,
            "max_tokens": 256,
        },
        tts_config={
            "provider": "dashscope",
            "cache_dir": ".cache/tts",
            "available": True,
            "missing_key_env": "",
        },
        image_config={
            "available": True,
            "missing_key_env": "",
        },
        llm_client_factory=llm_factory,
        tts_engine_factory=tts_factory,
        ws_tts_service_factory=ws_factory,
        media_api_service_factory=media_factory,
        image_cache_dir_resolver=lambda base_dir: Path(base_dir) / ".cache/image",
    )

    assert llm_calls == [{
        "provider": "deepseek",
        "model": "deepseek-chat",
        "temperature": 0.2,
        "max_tokens": 256,
    }]
    assert tts_calls[0]["provider"].value == "dashscope"
    assert tts_calls[0]["cache_dir"] == str(tmp_path / ".cache/tts")
    assert ws_calls == [{"tts_engine": runtime.tts_engine}]
    assert media_calls == [{
        "tts_engine": runtime.tts_engine,
        "image_cache_dir": tmp_path / ".cache/image",
        "image_available": True,
        "image_unavailable_reason": "",
    }]
    assert runtime.llm_client is not None
    assert runtime.tts_available is True
    assert runtime.ws_tts_service is not None
    assert runtime.media_api_service is not None
    assert runtime.warnings == ()
```

- [x] **Step 2: Add unavailable provider degradation test**

Append:

```python
def test_provider_runtime_degrades_unavailable_llm_tts_and_image(tmp_path):
    from server.provider_runtime import build_provider_runtime_services

    llm_calls: list[dict[str, Any]] = []
    ws_calls: list[dict[str, Any]] = []
    media_calls: list[dict[str, Any]] = []

    def tts_factory(**kwargs: Any) -> FakeService:
        return FakeService(**kwargs)

    def media_factory(**kwargs: Any) -> FakeService:
        media_calls.append(kwargs)
        return FakeService(**kwargs)

    runtime = build_provider_runtime_services(
        tmp_path,
        llm_config={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "available": False,
            "missing_key_env": "DEEPSEEK_API_KEY or LLM_API_KEY",
        },
        tts_config={
            "provider": "dashscope",
            "cache_dir": ".cache/tts",
            "available": False,
            "missing_key_env": "DASHSCOPE_API_KEY or TTS_API_KEY",
        },
        image_config={
            "available": False,
            "missing_key_env": "GEMINI_API_KEY or IMAGE_API_KEY",
        },
        llm_client_factory=lambda **kwargs: llm_calls.append(kwargs),
        tts_engine_factory=tts_factory,
        ws_tts_service_factory=lambda **kwargs: ws_calls.append(kwargs),
        media_api_service_factory=media_factory,
        image_cache_dir_resolver=lambda base_dir: Path(base_dir) / ".cache/image",
    )

    assert llm_calls == []
    assert ws_calls == []
    assert runtime.llm_client is None
    assert runtime.tts_engine is not None
    assert runtime.tts_available is False
    assert runtime.ws_tts_service is None
    assert media_calls[0]["tts_engine"] is None
    assert media_calls[0]["image_available"] is False
    assert media_calls[0]["image_unavailable_reason"] == "GEMINI_API_KEY or IMAGE_API_KEY"
    assert runtime.warnings == (
        "⚠ LLM provider 'deepseek' 未配置 DEEPSEEK_API_KEY or LLM_API_KEY，已禁用聊天会话、WebSocket 聊天和主动消息",
        "⚠ TTS provider 'dashscope' 未配置 DASHSCOPE_API_KEY or TTS_API_KEY，已禁用语音技能和 WebSocket TTS",
    )
```

- [x] **Step 3: Add bootstrap source boundary tests**

Update `test_bootstrap_module_exports_runtime_hooks()`:

```python
assert hasattr(bootstrap, "startup")
assert hasattr(bootstrap, "shutdown")
assert hasattr(bootstrap, "sync_legacy_globals")
```

Update `test_bootstrap_degrades_when_llm_provider_is_unavailable()` to assert:

```python
assert "from server.provider_runtime import build_provider_runtime_services" in bootstrap_source
assert "provider_runtime = build_provider_runtime_services(base_dir)" in bootstrap_source
assert "context.llm_client = provider_runtime.llm_client" in bootstrap_source
assert "context.tts_engine = provider_runtime.tts_engine" in bootstrap_source
assert "context.ws_tts_service = provider_runtime.ws_tts_service" in bootstrap_source
assert "context.media_api_service = provider_runtime.media_api_service" in bootstrap_source
assert "if provider_runtime.tts_available:" in bootstrap_source
assert "get_llm_config" not in bootstrap_source
assert "get_tts_config" not in bootstrap_source
assert "get_image_config" not in bootstrap_source
assert "LLMClient(" not in bootstrap_source
assert "TTSEngine(" not in bootstrap_source
```

Keep existing assertions for chat degradation that still belong to bootstrap:

```python
assert "ChatApiService(" in bootstrap_source
assert "session_manager=None" in bootstrap_source
assert "context.session_agent_factory = None" in bootstrap_source
assert "context.session_manager = None" in bootstrap_source
assert "if context.llm_client and context.session_manager:" in bootstrap_source
assert "context.proactive_service = None" in bootstrap_source
assert "context.proactive_task = None" in bootstrap_source
```

- [x] **Step 4: Update media boundary source test**

Update `test_app_context_and_bootstrap_expose_media_api_service_boundary()` to assert:

```python
assert "from server.media_api_service import MediaApiService" in context_source
assert "media_api_service: MediaApiService | None = None" in context_source
assert "from server.provider_runtime import build_provider_runtime_services" in bootstrap_source
assert "context.media_api_service = provider_runtime.media_api_service" in bootstrap_source
assert '"media_api_service": context.media_api_service' in bootstrap_source
assert "context.media_api_service = MediaApiService(" not in bootstrap_source
assert 'base_dir / ".cache" / "image"' not in bootstrap_source
```

- [x] **Step 5: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_runtime.py tests/test_server_bootstrap.py::test_bootstrap_degrades_when_llm_provider_is_unavailable tests/test_media_api_service.py::test_app_context_and_bootstrap_expose_media_api_service_boundary -v
```

Expected: FAIL because `server.provider_runtime` does not exist and bootstrap still constructs providers inline.

### Task 2: Implement Provider Runtime Module

**Files:**
- Create: `server/provider_runtime.py`
- Modify: `server/bootstrap.py`

- [x] **Step 1: Add provider runtime module**

Create `server/provider_runtime.py`:

```python
"""Provider runtime service assembly for OpenHer startup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from providers.api_config import get_image_config, get_llm_config, get_tts_config
from providers.llm import LLMClient
from providers.media.tts_engine import TTSEngine, TTSProvider
from server.media_api_service import MediaApiService, resolve_image_cache_dir
from server.ws_tts import WebSocketTTSService


@dataclass(frozen=True)
class ProviderRuntimeServices:
    llm_client: Any | None
    tts_engine: Any
    tts_available: bool
    ws_tts_service: Any | None
    media_api_service: Any
    warnings: tuple[str, ...]


ProviderFactory = Callable[..., Any]
ImageCacheDirResolver = Callable[[Path], Path]


def build_provider_runtime_services(
    base_dir: Path,
    *,
    llm_config: Mapping[str, Any] | None = None,
    tts_config: Mapping[str, Any] | None = None,
    image_config: Mapping[str, Any] | None = None,
    llm_client_factory: ProviderFactory = LLMClient,
    tts_engine_factory: ProviderFactory = TTSEngine,
    ws_tts_service_factory: ProviderFactory = WebSocketTTSService,
    media_api_service_factory: ProviderFactory = MediaApiService,
    image_cache_dir_resolver: ImageCacheDirResolver = resolve_image_cache_dir,
) -> ProviderRuntimeServices:
    llm_cfg = llm_config or get_llm_config()
    tts_cfg = tts_config or get_tts_config()
    image_cfg = image_config or get_image_config()
    warnings: list[str] = []

    llm_client = None
    if bool(llm_cfg.get("available", True)):
        llm_client = llm_client_factory(
            provider=llm_cfg["provider"],
            model=llm_cfg["model"],
            temperature=llm_cfg.get("temperature", 0.92),
            max_tokens=llm_cfg.get("max_tokens", 1024),
        )
    else:
        warnings.append(_provider_unavailable_warning(
            "LLM",
            llm_cfg,
            "已禁用聊天会话、WebSocket 聊天和主动消息",
        ))

    tts_engine = tts_engine_factory(
        provider=TTSProvider(str(tts_cfg["provider"])),
        cache_dir=str(Path(base_dir) / str(tts_cfg["cache_dir"])),
    )
    tts_available = bool(tts_cfg.get("available", False))
    ws_tts_service = None
    if tts_available:
        ws_tts_service = ws_tts_service_factory(tts_engine=tts_engine)
    else:
        warnings.append(_provider_unavailable_warning(
            "TTS",
            tts_cfg,
            "已禁用语音技能和 WebSocket TTS",
        ))

    media_api_service = media_api_service_factory(
        tts_engine=tts_engine if tts_available else None,
        image_cache_dir=image_cache_dir_resolver(Path(base_dir)),
        image_available=bool(image_cfg.get("available", False)),
        image_unavailable_reason=str(image_cfg.get("missing_key_env") or ""),
    )

    return ProviderRuntimeServices(
        llm_client=llm_client,
        tts_engine=tts_engine,
        tts_available=tts_available,
        ws_tts_service=ws_tts_service,
        media_api_service=media_api_service,
        warnings=tuple(warnings),
    )


def _provider_unavailable_warning(label: str, cfg: Mapping[str, Any], consequence: str) -> str:
    provider = str(cfg.get("provider") or "")
    missing_key = str(cfg.get("missing_key_env") or f"{provider.upper()}_API_KEY")
    return f"⚠ {label} provider '{provider}' 未配置 {missing_key}，{consequence}"
```

- [x] **Step 2: Refactor bootstrap imports**

In `server/bootstrap.py`, remove these imports:

```python
from providers.api_config import get_image_config, get_llm_config, get_memory_config, get_tts_config
from providers.llm import LLMClient
from providers.media.tts_engine import TTSEngine, TTSProvider
from server.media_api_service import MediaApiService, resolve_image_cache_dir
from server.ws_tts import WebSocketTTSService
```

Replace with:

```python
from providers.api_config import get_memory_config
from server.provider_runtime import build_provider_runtime_services
```

- [x] **Step 3: Refactor startup provider assembly**

Replace the inline LLM/TTS/Image block in `startup()` with:

```python
    provider_runtime = build_provider_runtime_services(base_dir)
    context.llm_client = provider_runtime.llm_client
    context.tts_engine = provider_runtime.tts_engine
    context.ws_tts_service = provider_runtime.ws_tts_service
    context.media_api_service = provider_runtime.media_api_service
    for warning in provider_runtime.warnings:
        print(warning)
```

Then replace:

```python
if tts_available:
```

with:

```python
if provider_runtime.tts_available:
```

- [x] **Step 4: Run provider runtime tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_runtime.py tests/test_server_bootstrap.py tests/test_media_api_service.py::test_app_context_and_bootstrap_expose_media_api_service_boundary -v
```

Expected: PASS.

### Task 3: Verify The Phase

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-provider-runtime-assembly.md`

- [x] **Step 1: Mark completed plan checkboxes**

Update this plan so every executed step is checked.

- [x] **Step 2: Run focused server bootstrap/provider tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_runtime.py tests/test_server_bootstrap.py tests/test_media_api_service.py tests/test_server_routes.py -v
```

Expected: all focused server bootstrap, media, and status tests pass.

- [x] **Step 3: Run repository checks**

Run: `make check`

Expected: pyright reports 0 errors and the full pytest suite passes.

- [x] **Step 4: Run runtime/smoke/build gates**

Run:

```bash
make doctor
make backend-acceptance-smoke
make backend-runtime-smoke
make backend-chat-smoke
make desktop-acceptance-smoke
make desktop-build
```

Expected: each command exits 0. `make doctor` may report optional warnings for unconfigured optional providers or missing local backups.

- [x] **Step 5: Commit and push**

```bash
git add docs/superpowers/specs/2026-07-06-provider-runtime-assembly-design.md docs/superpowers/plans/2026-07-06-provider-runtime-assembly.md server/provider_runtime.py server/bootstrap.py tests/test_provider_runtime.py tests/test_server_bootstrap.py tests/test_media_api_service.py
git commit -m "refactor: extract provider runtime assembly"
git push origin main
```
