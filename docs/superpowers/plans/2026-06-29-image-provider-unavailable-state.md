# Image Provider Unavailable State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make REST image generation report service unavailable when the configured image provider lacks credentials, matching the TTS unavailable behavior.

**Architecture:** Extend `providers.config.get_image_config()` with `available` and `missing_key_env`, using the same shape as TTS. Wire `MediaApiService` with an explicit `image_available` state and `image_unavailable_reason`; `generate_image()` raises `MediaApiServiceUnavailable` before constructing providers when image generation is not configured. Update `/api/image` to map this to HTTP 503 and update integration smoke to reuse central availability fields.

**Tech Stack:** Python 3.11+, pytest, FastAPI TestClient, existing provider config and media service boundaries.

---

### Task 1: Add Failing Availability Tests

**Files:**
- Modify: `tests/test_provider_config.py`
- Modify: `tests/test_media_api_service.py`
- Modify: `tests/test_security_regressions.py`

- [x] **Step 1: Add image config availability tests**

Add tests asserting `get_image_config()` returns:

```python
available == False
missing_key_env == "GEMINI_API_KEY"
```

when no Gemini key is configured, and `available == True`, `missing_key_env == ""` when `GEMINI_API_KEY` is set.

- [x] **Step 2: Add media service unavailable test for image**

Add a test constructing:

```python
MediaApiService(tts_engine=None, image_cache_dir=tmp_path, image_available=False, image_unavailable_reason="GEMINI_API_KEY")
```

and assert `generate_image()` raises `MediaApiServiceUnavailable` before calling the image provider factory.

- [x] **Step 3: Add route-level 503 regression test**

Extend external endpoint tests so `/api/image` with an AppContext media service configured as image-unavailable returns HTTP 503 and JSON `detail` mentioning the missing image provider key.

- [x] **Step 4: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py::ProviderConfigBoundaryTests::test_image_config_marks_active_provider_unavailable_when_key_is_missing tests/test_provider_config.py::ProviderConfigBoundaryTests::test_image_config_marks_active_provider_available_when_key_is_set tests/test_media_api_service.py::test_media_api_service_wraps_unavailable_image_provider tests/test_security_regressions.py::ExternalEndpointErrorTests::test_image_endpoint_returns_service_unavailable_when_unconfigured -q
```

Expected: FAIL because image config does not expose availability and image REST does not yet return 503 for missing configuration.

### Task 2: Implement Image Availability Plumbing

**Files:**
- Modify: `providers/config.py`
- Modify: `server/media_api_service.py`
- Modify: `server/bootstrap.py`
- Modify: `server/routes/media.py`
- Modify: `scripts/integration/provider_smoke.py`

- [x] **Step 5: Add `available` and `missing_key_env` to `get_image_config()`**

Use the active provider preset's `no_key_required` and `api_key_env` to mirror TTS availability semantics.

- [x] **Step 6: Add image availability fields to `MediaApiService`**

Accept `image_available: bool = True` and `image_unavailable_reason: str = ""`. In `generate_image()`, raise `MediaApiServiceUnavailable` with a clear message when unavailable.

- [x] **Step 7: Wire bootstrap and route fallback**

Resolve `image_cfg = get_image_config()` during startup, pass `image_available` and `missing_key_env` to `MediaApiService`, and have route fallback do the same through a helper.

- [x] **Step 8: Map `/api/image` unavailable state to 503**

Catch `MediaApiServiceUnavailable` in `image_api()` and raise `HTTPException(status_code=503, detail=str(e))`.

- [x] **Step 9: Reuse central availability in integration smoke**

Update `smoke_image_provider()` to use `image_cfg["available"]` and `image_cfg["missing_key_env"]` instead of recomputing availability.

### Task 3: Verify And Ship

**Files:**
- Verify: target tests
- Verify: full project quality gates

- [x] **Step 10: Run target tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_config.py tests/test_media_api_service.py tests/test_security_regressions.py::ExternalEndpointErrorTests tests/test_integration_smoke_profile.py -q
```

- [x] **Step 11: Run full checks**

Run:

```bash
source .venv/bin/activate && make check
```

- [x] **Step 12: Run runtime smoke and desktop build**

Run:

```bash
source .venv/bin/activate && make integration-smoke
cd desktop/OpenHer && swift build
```

- [x] **Step 13: Commit, merge to main, and push**

Commit message: `fix: report unavailable image provider as 503`
