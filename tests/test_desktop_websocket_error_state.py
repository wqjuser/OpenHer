"""macOS WebSocket error state source contracts."""

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
