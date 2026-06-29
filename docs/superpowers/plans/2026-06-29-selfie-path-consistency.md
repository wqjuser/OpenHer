# Selfie Path Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure selfie generation writes under the same repo-root `.cache/selfie` tree that `/api/selfie/...` serves, and make REST/WebSocket image URL generation preserve persona subdirectories consistently.

**Architecture:** Add a shared `selfie_url_for_path()` helper in `server.media` for converting generated image paths to `/api/selfie/...` URLs. Use it from REST chat and WebSocket delivery. Fix `skills.modality.selfie_gen.handler` to resolve the project root correctly (`parents[3]`) and expose helper functions for idimage and cache paths.

**Tech Stack:** Python 3.11+, pytest, existing media helpers, existing modality selfie handler.

---

### Task 1: Add Failing Path Contract Tests

**Files:**
- Modify: `tests/test_security_regressions.py`
- Modify: `tests/test_chat_api_service.py`
- Modify: `tests/test_websocket_delivery.py`

- [x] **Step 1: Write selfie handler root path regression tests**

Add tests that import `skills.modality.selfie_gen.handler` and assert:

```python
self.assertEqual(handler.get_idimage_dir("luna"), ROOT / "persona" / "personas" / "luna" / "idimage")
self.assertEqual(handler.get_selfie_cache_dir("luna"), ROOT / ".cache" / "selfie" / "luna")
```

- [x] **Step 2: Write REST chat image URL regression test**

Update the REST chat fake image path to `ROOT / ".cache" / "selfie" / "luna" / "portrait.png"` and assert the API response image URL is `/api/selfie/luna/portrait.png`.

- [x] **Step 3: Write WebSocket image URL shared helper regression test**

Add a WebSocket delivery test that passes a status image path under `ROOT/.cache/selfie/luna/portrait.png` and asserts delivered `image_url` is `/api/selfie/luna/portrait.png`. Add a structural assertion that `server.websocket_delivery` imports `selfie_url_for_path` and no longer defines its own `_image_url`.

- [x] **Step 4: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_security_regressions.py::PathSecurityRegressionTests::test_selfie_handler_uses_repo_root_media_paths tests/test_chat_api_service.py::test_chat_api_service_processes_turn_persists_agent_and_saves_display_log tests/test_websocket_delivery.py -q
```

Expected: FAIL because handler currently resolves repo root as `skills/`, REST loses the persona path, and WebSocket still owns a private `_image_url` method.

### Task 2: Implement Shared URL And Correct Handler Paths

**Files:**
- Modify: `server/media.py`
- Modify: `server/chat_api_service.py`
- Modify: `server/websocket_delivery.py`
- Modify: `skills/modality/selfie_gen/handler.py`

- [x] **Step 5: Add `selfie_url_for_path()`**

Implement URL mapping:

```python
def selfie_url_for_path(image_path: Optional[str]) -> Optional[str]:
    if not image_path:
        return None
    parts = image_path.replace("\\", "/").split("/")
    selfie_idx = parts.index("selfie") if "selfie" in parts else -1
    if selfie_idx >= 0:
        return "/api/selfie/" + "/".join(parts[selfie_idx + 1:])
    return f"/api/selfie/{os.path.basename(image_path)}"
```

- [x] **Step 6: Use helper from REST and WebSocket services**

Import `selfie_url_for_path` in `server.chat_api_service` and `server.websocket_delivery`. Remove private `_image_url` methods and call the shared helper.

- [x] **Step 7: Fix selfie handler project root**

Add `_repo_root()` returning `Path(__file__).resolve().parents[3]`, add `get_selfie_cache_dir(persona_id)`, and use those helpers in `get_idimage_dir()` and `generate_selfie()`.

### Task 3: Verify And Ship

**Files:**
- Verify: targeted tests
- Verify: full project quality gates

- [x] **Step 8: Run targeted tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_security_regressions.py::PathSecurityRegressionTests tests/test_chat_api_service.py tests/test_websocket_delivery.py -q
```

- [x] **Step 9: Run full checks**

Run:

```bash
source .venv/bin/activate && make check
```

- [x] **Step 10: Run runtime smoke and desktop build**

Run:

```bash
source .venv/bin/activate && make integration-smoke
cd desktop/OpenHer && swift build
```

- [x] **Step 11: Commit, merge to main, and push**

Commit message: `fix: align selfie media paths`
