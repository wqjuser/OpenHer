"""macOS provider readiness source contracts."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_api_client_exposes_typed_backend_provider_status():
    source = (ROOT / "desktop/OpenHer/Sources/Services/APIClient.swift").read_text(encoding="utf-8")

    assert "struct BackendStatus: Decodable" in source
    assert "struct BackendProviders: Decodable" in source
    assert "struct ProviderCapability: Decodable" in source
    assert "struct BackendCapabilities: Decodable" in source
    assert "struct CapabilitySummary: Decodable" in source
    assert "let capabilities: BackendCapabilities?" in source
    assert "func fetchBackendStatus() async throws -> BackendStatus" in source
    assert "return try JSONDecoder().decode(BackendStatus.self, from: data)" in source
    assert "var isRunning: Bool" in source
    assert "let reason: String" in source
    assert "missing_key_env" in source


def test_app_state_and_connection_manager_track_chat_availability():
    app_state = (ROOT / "desktop/OpenHer/Sources/AppState.swift").read_text(encoding="utf-8")
    connection = (ROOT / "desktop/OpenHer/Sources/Services/ConnectionManager.swift").read_text(encoding="utf-8")

    assert "@Published var isChatAvailable: Bool = true" in app_state
    assert "@Published var chatUnavailableReason: String? = nil" in app_state
    assert "var canSendChat: Bool" in app_state
    assert "func updateBackendStatus(_ status: BackendStatus)" in app_state
    assert "status.capabilities?.chat" in app_state
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
