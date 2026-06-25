# Media API Service Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `/api/tts` and `/api/image` provider orchestration out of FastAPI routes into a focused service.

**Architecture:** Add `server/media_api_service.py` with `MediaApiService`, a file-response dataclass, and small domain exceptions. `server/routes/media.py` will keep query validation, HTTP exception mapping, and `FileResponse` construction while delegating TTS synthesis, image provider lookup, provider calls, failure-result interpretation, and response-file metadata assembly to the service. `AppContext` and bootstrap will expose a configured service, while tests can still construct a fallback service from context dependencies.

**Tech Stack:** Python 3.11+, FastAPI, pytest, existing TTS engine and image provider registry interfaces.

---

### Task 1: Lock Media API Service Behavior With Failing Tests

**Files:**
- Create: `tests/test_media_api_service.py`
- Verify: `server/routes/media.py`
- Verify: `server/context.py`
- Verify: `server/bootstrap.py`

- [x] **Step 1: Write successful TTS service test**

Create a fake TTS engine returning:

```python
SimpleNamespace(
    success=True,
    audio_path="/tmp/speech.wav",
    audio_format="wav",
    mime_type="audio/wav",
    error="",
)
```

Call:

```python
result = await service.synthesize_tts(
    text="hello",
    voice="sweet_female",
    emotion="happy",
)
```

Assert:
- fake engine receives `text`, `voice_preset`, and `emotion_instruction`;
- `result.path == "/tmp/speech.wav"`;
- `result.media_type == "audio/wav"`;
- `result.filename == "speech.wav"`.

- [x] **Step 2: Write successful image service test**

Create a fake image provider factory that records `cache_dir` and returns a provider whose `generate()` returns:

```python
SimpleNamespace(
    success=True,
    image_path="/tmp/generated.webp",
    mime_type="image/webp",
    error="",
)
```

Call:

```python
result = await service.generate_image(
    prompt="portrait",
    aspect_ratio="1:1",
    image_size="1K",
)
```

Assert:
- factory receives the configured image cache dir;
- provider receives `prompt`, `aspect_ratio`, and `image_size`;
- `result.path == "/tmp/generated.webp"`;
- `result.media_type == "image/webp"`;
- `result.filename == "generated.webp"`.

- [x] **Step 3: Write failure and route delegation tests**

Assert:
- missing TTS engine raises `MediaApiServiceUnavailable`;
- failed provider result raises `MediaApiFailedResult` with a redacted detail;
- provider exceptions raise `MediaApiProviderError` carrying the original exception;
- `server/routes/media.py` imports `MediaApiService`, calls `service.synthesize_tts(...)` and `service.generate_image(...)`, and no longer directly calls `ctx.tts_engine.synthesize`, `provider.generate`, `get_image_gen`, or `redact_known_secrets`;
- `server/context.py` has a typed `media_api_service` field;
- `server/bootstrap.py` constructs `MediaApiService`.

- [x] **Step 4: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/test_media_api_service.py -q`

Expected: FAIL because `server.media_api_service` does not exist and the route still owns media provider behavior.

### Task 2: Add MediaApiService

**Files:**
- Create: `server/media_api_service.py`
- Test: `tests/test_media_api_service.py`

- [x] **Step 1: Implement result dataclass**

Create:

```python
@dataclass(frozen=True)
class MediaFileResult:
    path: str
    media_type: str
    filename: str
```

- [x] **Step 2: Implement service exceptions**

Create:

```python
class MediaApiServiceUnavailable(RuntimeError): ...
class MediaApiProviderConfigError(RuntimeError): ...
class MediaApiProviderError(RuntimeError):
    def __init__(self, action: str, original: Exception) -> None: ...
class MediaApiFailedResult(RuntimeError):
    def __init__(self, detail: str) -> None: ...
```

- [x] **Step 3: Implement TTS synthesis**

`MediaApiService.synthesize_tts()` should:
- raise `MediaApiServiceUnavailable("TTS engine is not initialized")` when no TTS engine is configured;
- call `tts_engine.synthesize(text=text, voice_preset=voice, emotion_instruction=emotion or None)`;
- wrap provider exceptions in `MediaApiProviderError("TTS provider failed", exc)`;
- when result succeeds with `audio_path`, return `MediaFileResult` with media type and filename using `audio_format` or `audio_format_for_path()`;
- otherwise raise `MediaApiFailedResult(redact_known_secrets(result.error or "TTS provider failed"))`.

- [x] **Step 4: Implement image generation**

`MediaApiService.generate_image()` should:
- call the injected image provider factory with `cache_dir=str(image_cache_dir)`;
- convert factory `ValueError` to `MediaApiProviderConfigError`;
- call provider `generate(prompt=..., aspect_ratio=..., image_size=...)`;
- wrap provider exceptions in `MediaApiProviderError("Image provider failed", exc)`;
- when result succeeds with `image_path`, return `MediaFileResult` with `mime_type or "image/png"` and `generated{ext or ".png"}`;
- otherwise raise `MediaApiFailedResult(redact_known_secrets(result.error or "Image generation failed"))`.

- [x] **Step 5: Run service tests**

Run: `.venv/bin/python -m pytest tests/test_media_api_service.py -q`

Expected: service behavior tests pass; route/context/bootstrap structural tests may still fail until Task 3.

### Task 3: Delegate Routes And Bootstrap Service

**Files:**
- Modify: `server/routes/media.py`
- Modify: `server/context.py`
- Modify: `server/bootstrap.py`
- Test: `tests/test_media_api_service.py`
- Test: `tests/test_security_regressions.py::ExternalEndpointErrorTests`
- Test: `tests/test_server_context.py`
- Test: `tests/test_server_routes.py`

- [x] **Step 1: Add service to app context**

Import `MediaApiService` in `server/context.py` and add:

```python
media_api_service: MediaApiService | None = None
```

- [x] **Step 2: Build service during startup**

Import `MediaApiService` in `server/bootstrap.py` and after TTS/image cache context is available, set:

```python
context.media_api_service = MediaApiService(
    tts_engine=context.tts_engine,
    image_cache_dir=base_dir / ".cache" / "image",
)
```

Also expose it through `sync_legacy_globals()`.

- [x] **Step 3: Thin `tts_api()` and `image_api()`**

In `server/routes/media.py`, construct fallback service with:

```python
service = ctx.media_api_service or MediaApiService(
    tts_engine=ctx.tts_engine,
    image_cache_dir=BASE_DIR / ".cache" / "image",
)
```

Map:
- `MediaApiServiceUnavailable` to HTTP 503;
- `MediaApiProviderConfigError` to HTTP 500;
- `MediaApiProviderError` to HTTP 502 using `external_error_detail(error.action, error.original)`;
- `MediaApiFailedResult` to HTTP 502 with `str(error)`.

Return:

```python
return FileResponse(result.path, media_type=result.media_type, filename=result.filename)
```

- [x] **Step 4: Run targeted tests**

Run: `.venv/bin/python -m pytest tests/test_media_api_service.py tests/test_security_regressions.py::ExternalEndpointErrorTests tests/test_server_context.py tests/test_server_routes.py -q`

Expected: all selected tests pass.

### Task 4: Full Verification And Release

**Files:**
- Verify: `server/media_api_service.py`
- Verify: `server/routes/media.py`
- Verify: `server/context.py`
- Verify: `server/bootstrap.py`
- Verify: `tests/test_media_api_service.py`

- [x] **Step 1: Run static and compile checks**

Run: `.venv/bin/pyright`

Expected: `0 errors, 0 warnings, 0 informations`.

Run: `.venv/bin/python -m py_compile server/media_api_service.py server/routes/media.py server/context.py server/bootstrap.py tests/test_media_api_service.py`

Expected: exit code 0.

- [x] **Step 2: Run full tests**

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: full suite passes with the known skipped WebSocket integration test unchanged.

- [x] **Step 3: Run repository hygiene checks**

Run: `.venv/bin/python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0.

- [x] **Step 4: Run service smoke**

Start: `PORT=8783 ./run.sh`

Check:
- `GET /api/status`;
- WebSocket `demo_presets`;
- `POST /api/chat`.

Expected: backend starts and existing chat paths still run normally.

- [x] **Step 5: Commit, merge, and push**

Run:

```bash
git add server/media_api_service.py server/routes/media.py server/context.py server/bootstrap.py tests/test_media_api_service.py docs/superpowers/plans/2026-06-25-media-api-service-boundary.md
git commit -m "refactor: extract media api service boundary"
git switch main
git pull --ff-only
git merge --no-ff codex/media-api-service-boundary -m "merge: media api service boundary"
git push origin main
```

### Self-Review

- Spec coverage: The plan extracts provider behavior for `/api/tts` and `/api/image` while leaving secure selfie file serving in the route.
- Placeholder scan: No deferred implementation placeholders are present.
- Type consistency: `MediaApiService`, `MediaFileResult`, and exception names are consistent across service, route, context, bootstrap, and tests.
