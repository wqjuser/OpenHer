# Image Cache Central Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make REST image generation cache directory resolution consume `providers.config.get_image_config()` instead of hardcoding `.cache/image` in server assembly and route fallbacks.

**Architecture:** Add a small resolver in `server.media_api_service` that turns `get_image_config()["cache_dir"]` into an absolute `Path` relative to the repo base when needed. Use that resolver in `server.bootstrap` and `server.routes.media` fallback service creation. Keep `MediaApiService` focused on invoking the provider and returning file metadata.

**Tech Stack:** Python 3.11+, pytest, existing provider config facade, existing media API service boundary.

---

### Task 1: Add Image Cache Resolver Contract Tests

**Files:**
- Modify: `tests/test_media_api_service.py`

- [x] **Step 1: Write the failing resolver test**

Add a test that patches `server.media_api_service.get_image_config` to return `{"cache_dir": "custom/image-cache"}` and asserts `resolve_image_cache_dir(tmp_path)` returns `tmp_path / "custom/image-cache"`. Add an absolute-path case and assert the absolute configured path is returned unchanged.

- [x] **Step 2: Write the failing route/bootstrap structural test**

Extend existing media boundary tests so `server.routes.media` and `server.bootstrap` must import/use `resolve_image_cache_dir`, and neither file may contain the old hardcoded `".cache" / "image"` image cache assembly.

- [x] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_media_api_service.py::test_resolve_image_cache_dir_uses_central_image_config tests/test_media_api_service.py::test_media_routes_delegate_tts_and_image_generation_to_service_boundary tests/test_media_api_service.py::test_app_context_and_bootstrap_expose_media_api_service_boundary -q`

Expected: FAIL because `resolve_image_cache_dir` does not exist and routes/bootstrap still hardcode `.cache/image`.

### Task 2: Implement Resolver And Wire Server Paths

**Files:**
- Modify: `server/media_api_service.py`
- Modify: `server/bootstrap.py`
- Modify: `server/routes/media.py`

- [x] **Step 4: Implement `resolve_image_cache_dir(base_dir)`**

Import `get_image_config`, read `cache_dir`, default to `.cache/image`, return absolute paths unchanged, and resolve relative paths under `base_dir`.

- [x] **Step 5: Use resolver in bootstrap**

Change `context.media_api_service = MediaApiService(... image_cache_dir=...)` to call `resolve_image_cache_dir(base_dir)`.

- [x] **Step 6: Use resolver in route fallback services**

Change both `/api/tts` and `/api/image` fallback `MediaApiService` construction sites to pass `resolve_image_cache_dir(BASE_DIR)`.

### Task 3: Verify And Ship

**Files:**
- Verify: `tests/test_media_api_service.py`
- Verify: full project quality gates

- [x] **Step 7: Run targeted media tests**

Run: `.venv/bin/python -m pytest tests/test_media_api_service.py -q`

- [x] **Step 8: Run full checks**

Run: `source .venv/bin/activate && make check`

- [x] **Step 9: Run runtime smoke and desktop build**

Run: `source .venv/bin/activate && make integration-smoke`

Run: `cd desktop/OpenHer && swift build`

- [x] **Step 10: Commit, merge to main, and push**

Commit message: `refactor: centralize image cache config resolution`
