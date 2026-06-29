# Status Capabilities Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stable `/api/status.capabilities` contract so clients can know which product features are usable without reverse-engineering provider internals.

**Architecture:** Keep the existing `providers` payload for compatibility, and add a higher-level `capabilities` payload derived on the backend. Update the macOS client to prefer `capabilities.chat` and fall back to `providers.llm` for older backends.

**Tech Stack:** FastAPI route helpers, pytest route tests, Swift `Decodable` models, source-contract tests, SwiftPM build.

---

### Task 1: Backend Status Capabilities

**Files:**
- Modify: `server/routes/health.py`
- Modify: `tests/test_server_routes.py`

- [ ] **Step 1: Write the failing backend test**

Add assertions to `test_api_status_reports_provider_readiness_without_secrets` that require a new `body["capabilities"]` object:

```python
    assert body["capabilities"] == {
        "chat": {
            "available": False,
            "reason": "LLM provider is not configured (missing DEEPSEEK_API_KEY or LLM_API_KEY)",
            "requires": ["llm"],
        },
        "voice": {
            "available": False,
            "reason": "TTS provider is not configured (missing DASHSCOPE_API_KEY or TTS_API_KEY)",
            "requires": ["tts"],
        },
        "image": {
            "available": True,
            "reason": "",
            "requires": ["image"],
        },
        "memory": {
            "available": False,
            "reason": "EverMemOS is not available",
            "requires": ["memory"],
        },
    }
```

- [ ] **Step 2: Verify the backend test fails**

Run: `.venv/bin/python -m pytest tests/test_server_routes.py::test_api_status_reports_provider_readiness_without_secrets -q`

Expected: FAIL with `KeyError: 'capabilities'`.

- [ ] **Step 3: Implement backend helpers**

Add a `_feature_status` helper that returns only `available`, `reason`, and `requires`. Add a `_missing_key_reason(label, missing_key_env)` helper that never includes secrets or base URLs. Add `_capabilities_status(ctx)` that maps `llm` to `chat`, `tts` to `voice`, `image` to `image`, and EverMemOS runtime availability to `memory`.

- [ ] **Step 4: Return capabilities from `/api/status`**

Update `api_status` to include `"capabilities": _capabilities_status(ctx)` while keeping `"providers": _providers_status(ctx)` unchanged.

- [ ] **Step 5: Verify backend test passes**

Run: `.venv/bin/python -m pytest tests/test_server_routes.py::test_api_status_reports_provider_readiness_without_secrets -q`

Expected: PASS.

### Task 2: macOS Client Consumes Capabilities

**Files:**
- Modify: `desktop/OpenHer/Sources/Services/APIClient.swift`
- Modify: `desktop/OpenHer/Sources/AppState.swift`
- Modify: `tests/test_desktop_provider_readiness.py`

- [ ] **Step 1: Write failing source-contract tests**

Extend `test_api_client_exposes_typed_backend_provider_status` to require `BackendCapabilities`, `CapabilitySummary`, and `let capabilities: BackendCapabilities?`. Extend `test_app_state_and_connection_manager_track_chat_availability` to require `status.capabilities?.chat` and the fallback `status.providers?.llm`.

- [ ] **Step 2: Verify the source-contract test fails**

Run: `.venv/bin/python -m pytest tests/test_desktop_provider_readiness.py -q`

Expected: FAIL because the Swift types and app-state preference do not exist yet.

- [ ] **Step 3: Add Swift decoding types**

Add:

```swift
struct BackendStatus: Decodable {
    let status: String
    let providers: BackendProviders?
    let capabilities: BackendCapabilities?
}

struct BackendCapabilities: Decodable {
    let chat: CapabilitySummary?
}

struct CapabilitySummary: Decodable {
    let available: Bool
    let reason: String
}
```

- [ ] **Step 4: Prefer the new capability in AppState**

Update `updateBackendStatus(_:)` so `status.capabilities?.chat` is used first. If it is absent, keep the existing fallback to `status.providers?.llm`.

- [ ] **Step 5: Verify source-contract tests pass**

Run: `.venv/bin/python -m pytest tests/test_desktop_provider_readiness.py -q`

Expected: PASS.

### Task 3: Full Verification and Integration

**Files:**
- Verify full repository behavior.
- Modify: `Makefile`
- Modify: `tests/test_quality_gates.py`

- [ ] **Step 1: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_server_routes.py tests/test_desktop_provider_readiness.py -q`

Expected: PASS.

- [ ] **Step 2: Build macOS client**

Run: `cd desktop/OpenHer && swift build`

Expected: PASS.

- [ ] **Step 3: Run full quality gate**

Run: `make check`

Expected: all tests pass and Pyright passes.

- [ ] **Step 4: Keep Makefile Python selection portable**

If `make check` fails before tests with `make: python: No such file or directory`, set `PYTHON ?= .venv/bin/python` at the top of `Makefile` and replace direct `python` invocations with `$(PYTHON)`. Update `tests/test_quality_gates.py` to assert the configurable `PYTHON` variable and `$(PYTHON)` calls. This preserves `make PYTHON=python3 check` override support while matching the project setup script.

- [ ] **Step 5: Run integration smoke**

Run: `make integration-smoke`

Expected: DeepSeek/EverMemOS configured checks pass, optional media providers may skip when keys are absent.

- [ ] **Step 6: Commit, merge, and push**

Run:

```bash
git add Makefile server/routes/health.py tests/test_server_routes.py tests/test_quality_gates.py desktop/OpenHer/Sources/Services/APIClient.swift desktop/OpenHer/Sources/AppState.swift tests/test_desktop_provider_readiness.py docs/superpowers/plans/2026-06-29-status-capabilities-contract.md
git commit -m "fix: expose status capabilities contract"
git checkout main
git merge codex/status-capabilities-contract
git push origin main
```

Expected: commit succeeds, merge is clean, push succeeds.
