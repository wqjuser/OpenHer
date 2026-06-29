# REST TTS Unavailable State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/api/tts` report service unavailable when the configured TTS provider is not available, matching startup's voice-tool and WebSocket TTS disablement.

**Architecture:** Keep `TTSEngine` construction unchanged so future configured TTS can still be initialized consistently. Change only `MediaApiService` wiring in `server.bootstrap`: when `tts_available` is false, pass `tts_engine=None` into the REST media service. The existing `MediaApiService.synthesize_tts()` behavior already turns `None` into `MediaApiServiceUnavailable`, which the route maps to HTTP 503.

**Tech Stack:** Python 3.11+, pytest, existing server bootstrap and media service boundaries.

---

### Task 1: Add Bootstrap Wiring Contract Test

**Files:**
- Modify: `tests/test_media_api_service.py`

- [x] **Step 1: Write the failing structural test**

Extend `test_app_context_and_bootstrap_expose_media_api_service_boundary()` so it asserts bootstrap wires REST TTS like this:

```python
assert "tts_engine=context.tts_engine if tts_available else None" in bootstrap_source
```

and no longer wires `tts_engine=context.tts_engine,` unconditionally inside `MediaApiService`.

- [x] **Step 2: Run the target test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_media_api_service.py::test_app_context_and_bootstrap_expose_media_api_service_boundary -q
```

Expected: FAIL because bootstrap currently passes `context.tts_engine` even when TTS is unavailable.

### Task 2: Wire REST TTS Availability Correctly

**Files:**
- Modify: `server/bootstrap.py`

- [x] **Step 3: Pass `None` to REST media service when TTS is unavailable**

Change `context.media_api_service = MediaApiService(...)` so the TTS dependency is:

```python
tts_engine=context.tts_engine if tts_available else None
```

Keep `context.tts_engine`, `context.ws_tts_service`, and voice-tool registration behavior unchanged.

- [x] **Step 4: Run target tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_media_api_service.py -q
```

Expected: PASS.

### Task 3: Verify And Ship

**Files:**
- Verify: full project quality gates

- [x] **Step 5: Run full checks**

Run:

```bash
source .venv/bin/activate && make check
```

- [x] **Step 6: Run runtime smoke and desktop build**

Run:

```bash
source .venv/bin/activate && make integration-smoke
cd desktop/OpenHer && swift build
```

- [x] **Step 7: Commit, merge to main, and push**

Commit message: `fix: disable rest tts when provider unavailable`
