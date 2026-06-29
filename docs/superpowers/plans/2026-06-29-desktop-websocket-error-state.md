# Desktop WebSocket Error State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the macOS client visibly handle WebSocket service-unavailable errors instead of leaving user messages stuck in a sending state.

**Architecture:** Keep WebSocket protocol parsing in `WebSocketManager`, but move user-visible state changes into focused `AppState` methods. `chat_start.user_content` confirms outbound user messages as sent, while `error.code == "service_unavailable"` marks pending user messages failed, clears typing/streaming placeholders, and appends a system notice.

**Tech Stack:** Swift 5.9 macOS client, Python source-level contract tests, SwiftPM build verification.

---

### Task 1: Add Failing Desktop Contract Tests

**Files:**
- Create: `tests/test_desktop_websocket_error_state.py`

- [x] **Step 1: Add source-level contract tests**

Create tests that assert the macOS client exposes stateful WebSocket error handling through `AppState` and delegates error parsing from `WebSocketManager`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_app_state_exposes_websocket_outbound_status_helpers():
    source = (ROOT / "desktop/OpenHer/Sources/AppState.swift").read_text(encoding="utf-8")

    assert "func markOutboundMessagesSent(matching mergedContent: String) -> Bool" in source
    assert "func handleWebSocketError(content: String, code: String?)" in source
    assert "sendStatus == .sending" in source
    assert "sendStatus = .sent" in source
    assert "sendStatus = .failed" in source
    assert "streaming_current" in source
    assert "role: .system" in source


def test_websocket_manager_delegates_chat_start_and_error_state_to_app_state():
    source = (ROOT / "desktop/OpenHer/Sources/Services/WebSocketManager.swift").read_text(encoding="utf-8")
    chat_start_body = source.split('case "chat_start":', 1)[1].split('case "chat_chunk":', 1)[0]
    error_body = source.split('case "error":', 1)[1].split('case "tts_audio":', 1)[0]

    assert "markOutboundMessagesSent(matching: userContent)" in chat_start_body
    assert "sendStatus: .sent" in chat_start_body
    assert 'let errCode = json["code"] as? String' in error_body
    assert "handleWebSocketError(content: errContent, code: errCode)" in error_body
    assert "appState?.isTyping = false" not in error_body
```

- [x] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_websocket_error_state.py -q
```

Expected: fail because the AppState helpers and WebSocket delegation do not exist yet.

### Task 2: Implement Desktop Error State

**Files:**
- Modify: `desktop/OpenHer/Sources/AppState.swift`
- Modify: `desktop/OpenHer/Sources/Services/WebSocketManager.swift`

- [x] **Step 3: Add AppState sent matching helper**

Add this method near the chat actions in `AppState.swift`:

```swift
@discardableResult
func markOutboundMessagesSent(matching mergedContent: String) -> Bool {
    let parts = mergedContent
        .split(separator: "\n", omittingEmptySubsequences: false)
        .map(String.init)
    guard !parts.isEmpty else { return false }

    let sendingIndices = messages.indices
        .filter { messages[$0].role == .user && messages[$0].sendStatus == .sending }
        .suffix(parts.count)
    guard sendingIndices.count == parts.count else { return false }

    for (index, part) in zip(sendingIndices, parts) {
        guard messages[index].content == part else { return false }
    }

    for index in sendingIndices {
        messages[index].sendStatus = .sent
    }
    return true
}
```

- [x] **Step 4: Add AppState WebSocket error helper**

Add this method near the chat actions in `AppState.swift`:

```swift
func handleWebSocketError(content: String, code: String?) {
    isTyping = false
    if let idx = messages.lastIndex(where: { $0.id == "streaming_current" }) {
        messages.remove(at: idx)
    }
    if let idx = messages.lastIndex(where: { $0.role == .user && $0.sendStatus == .sending }) {
        messages[idx].sendStatus = .failed
    }
    if code == "service_unavailable" {
        messages.append(ChatMessage(
            role: .system,
            content: content,
            modality: "系统"
        ))
    }
}
```

- [x] **Step 5: Delegate chat_start sent confirmation**

In `WebSocketManager.handleMessage`, update the `chat_start` user-content block:

```swift
if let userContent = json["user_content"] as? String, !userContent.isEmpty {
    let didMarkExisting = appState?.markOutboundMessagesSent(matching: userContent) ?? false
    if !didMarkExisting {
        let alreadyHas = appState?.messages.last(where: { $0.role == .user })?.content == userContent
        if !alreadyHas {
            let msg = ChatMessage(
                id: UUID().uuidString,
                role: .user,
                content: userContent,
                modality: "文字",
                timestamp: Date(),
                sendStatus: .sent
            )
            DispatchQueue.main.async { [weak self] in
                self?.appState?.messages.append(msg)
            }
        }
    }
}
```

- [x] **Step 6: Delegate error handling**

In `WebSocketManager.handleMessage`, update the `error` case:

```swift
case "error":
    let errContent = json["content"] as? String ?? "Unknown error"
    let errCode = json["code"] as? String
    print("[WS] Error: \(errContent)")
    appState?.handleWebSocketError(content: errContent, code: errCode)
```

- [x] **Step 7: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_desktop_websocket_error_state.py -q
```

Expected: source contract tests pass.

### Task 3: Verify And Ship

**Files:**
- Verify: desktop Swift build
- Verify: full backend checks
- Verify: live provider smoke

- [x] **Step 8: Run desktop build and focused tests**

Run:

```bash
cd desktop/OpenHer && swift build
.venv/bin/python -m pytest tests/test_desktop_websocket_error_state.py tests/test_websocket_route_service.py -q
```

- [x] **Step 9: Run full checks and smoke**

Run:

```bash
source .venv/bin/activate && make check
source .venv/bin/activate && make integration-smoke
```

- [x] **Step 10: Commit, merge to main, and push**

Commit message:

```bash
git commit -m "fix: surface websocket unavailable state in desktop"
```
