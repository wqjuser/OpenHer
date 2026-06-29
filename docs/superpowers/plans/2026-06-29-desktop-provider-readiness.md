# Desktop Provider Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the macOS client read backend provider readiness and disable chat input when the LLM provider is unavailable.

**Architecture:** Extend `APIClient` with a typed `BackendStatus` response for `/api/status`. `ConnectionManager` writes that status into `AppState`, and conversation/menu UI reads `AppState.canSendChat` plus a localized reason instead of relying only on backend reachability.

**Tech Stack:** Swift 5.9 macOS client, Python source-level contract tests, SwiftPM build verification.

---

### Task 1: Add Failing Desktop Provider Readiness Tests

**Files:**
- Create: `tests/test_desktop_provider_readiness.py`

- [x] **Step 1: Add source-level contract tests**

Create tests that assert the macOS client parses provider readiness and wires it to chat UI state:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_api_client_exposes_typed_backend_provider_status():
    source = (ROOT / "desktop/OpenHer/Sources/Services/APIClient.swift").read_text(encoding="utf-8")

    assert "struct BackendStatus: Decodable" in source
    assert "struct BackendProviders: Decodable" in source
    assert "struct ProviderCapability: Decodable" in source
    assert "func fetchBackendStatus() async throws -> BackendStatus" in source
    assert "return try JSONDecoder().decode(BackendStatus.self, from: data)" in source
    assert "var isRunning: Bool" in source
    assert "missing_key_env" in source


def test_app_state_and_connection_manager_track_chat_availability():
    app_state = (ROOT / "desktop/OpenHer/Sources/AppState.swift").read_text(encoding="utf-8")
    connection = (ROOT / "desktop/OpenHer/Sources/Services/ConnectionManager.swift").read_text(encoding="utf-8")

    assert "@Published var isChatAvailable: Bool = true" in app_state
    assert "@Published var chatUnavailableReason: String? = nil" in app_state
    assert "var canSendChat: Bool" in app_state
    assert "func updateBackendStatus(_ status: BackendStatus)" in app_state
    assert "status.providers?.llm" in app_state
    assert "chatUnavailableReason =" in app_state
    assert "let status = try await appState.apiClient.fetchBackendStatus()" in connection
    assert "appState.updateBackendStatus(status)" in connection


def test_conversation_ui_disables_input_when_chat_is_unavailable():
    input_line = (ROOT / "desktop/OpenHer/Sources/Views/Conversation/InputLine.swift").read_text(encoding="utf-8")
    conversation = (ROOT / "desktop/OpenHer/Sources/Views/ConversationPanel.swift").read_text(encoding="utf-8")
    menu = (ROOT / "desktop/OpenHer/Sources/Views/MenuBar/MenuBarView.swift").read_text(encoding="utf-8")

    assert "let isEnabled: Bool" in input_line
    assert "let unavailableReason: String?" in input_line
    assert ".disabled(!isEnabled)" in input_line
    assert "unavailableReason" in input_line
    assert "isEnabled: appState.canSendChat" in conversation
    assert "unavailableReason: appState.chatUnavailableReason" in conversation
    assert "appState.canSendChat" in menu
```

- [x] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_provider_readiness.py -q
```

Expected: fail because typed backend status and chat availability state are not implemented yet.

### Task 2: Implement Typed Backend Status

**Files:**
- Modify: `desktop/OpenHer/Sources/Services/APIClient.swift`
- Modify: `desktop/OpenHer/Sources/AppState.swift`
- Modify: `desktop/OpenHer/Sources/Services/ConnectionManager.swift`

- [x] **Step 3: Add APIClient backend status models**

Add `BackendStatus`, `BackendProviders`, and `ProviderCapability` `Decodable` structs in `APIClient.swift`. Include `CodingKeys` for `missing_key_env`.

- [x] **Step 4: Add APIClient status fetch**

Add:

```swift
func fetchBackendStatus() async throws -> BackendStatus {
    let data = try await get("/api/status")
    return try JSONDecoder().decode(BackendStatus.self, from: data)
}
```

Then implement `checkStatus()` by returning `try await fetchBackendStatus().isRunning`.

- [x] **Step 5: Add AppState chat availability**

Add:

```swift
@Published var isChatAvailable: Bool = true
@Published var chatUnavailableReason: String? = nil

var canSendChat: Bool {
    isConnected && isChatAvailable
}

func updateBackendStatus(_ status: BackendStatus) {
    isConnected = status.isRunning
    guard let llm = status.providers?.llm else {
        isChatAvailable = true
        chatUnavailableReason = nil
        return
    }
    isChatAvailable = llm.available
    chatUnavailableReason = llm.available ? nil : llm.displayUnavailableReason
}
```

- [x] **Step 6: Wire ConnectionManager**

Change `checkAndConnect()` to call `fetchBackendStatus()`, call `appState.updateBackendStatus(status)`, and connect WebSocket only when `status.isRunning && !appState.isConnected`.

### Task 3: Wire UI To Chat Availability

**Files:**
- Modify: `desktop/OpenHer/Sources/Views/Conversation/InputLine.swift`
- Modify: `desktop/OpenHer/Sources/Views/ConversationPanel.swift`
- Modify: `desktop/OpenHer/Sources/Views/MenuBar/MenuBarView.swift`

- [x] **Step 7: Disable InputLine when chat is unavailable**

Add `isEnabled` and `unavailableReason` inputs. Disable `TextField`, microphone, and send button when `!isEnabled`, and show `unavailableReason` as small muted text above the controls.

- [x] **Step 8: Pass AppState readiness to conversation UI**

Pass:

```swift
isEnabled: appState.canSendChat,
unavailableReason: appState.chatUnavailableReason
```

to `InputLine`, and guard `sendMessage()` with `appState.canSendChat`.

- [x] **Step 9: Reflect chat readiness in menu bar**

Use `appState.canSendChat` for the connected indicator and show `appState.chatUnavailableReason` when backend is reachable but chat is unavailable.

- [x] **Step 10: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_provider_readiness.py -q
cd desktop/OpenHer && swift build
```

### Task 4: Verify And Ship

**Files:**
- Verify: full Python checks
- Verify: macOS Swift build
- Verify: live provider smoke

- [x] **Step 11: Run full checks and smoke**

Run:

```bash
source .venv/bin/activate && make check
cd desktop/OpenHer && swift build
source .venv/bin/activate && make integration-smoke
```

- [x] **Step 12: Commit, merge to main, and push**

Commit message:

```bash
git commit -m "fix: reflect provider readiness in desktop"
```
