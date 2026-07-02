"""macOS configuration diagnostics source contracts."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backend_status_decodes_all_configuration_diagnostics():
    source = (ROOT / "desktop/OpenHer/Sources/Services/APIClient.swift").read_text(encoding="utf-8")

    assert "let memory: MemoryProviderCapability?" in source
    assert "let voice: CapabilitySummary?" in source
    assert "let image: CapabilitySummary?" in source
    assert "let memory: CapabilitySummary?" in source
    assert "struct MemoryProviderCapability: Decodable" in source
    assert "let configured: Bool" in source
    assert "let enabled: Bool" in source


def test_app_state_tracks_backend_diagnostics_for_settings_view():
    source = (ROOT / "desktop/OpenHer/Sources/AppState.swift").read_text(encoding="utf-8")

    assert "@Published var backendStatus: BackendStatus? = nil" in source
    assert "@Published var lastStatusCheckedAt: Date? = nil" in source
    assert "var configurationDiagnostics: [ConfigurationDiagnostic]" in source
    assert "struct ConfigurationDiagnostic: Identifiable" in source
    assert "func refreshBackendStatus() async" in source
    assert "backendStatus = status" in source
    assert "lastStatusCheckedAt = Date()" in source
    assert 'id: "voice"' in source
    assert 'id: "image"' in source
    assert 'id: "memory"' in source


def test_settings_view_exposes_refreshable_configuration_diagnostics():
    source = (ROOT / "desktop/OpenHer/Sources/Views/Settings/SettingsView.swift").read_text(encoding="utf-8")

    assert "Section(L10n.str(\"配置诊断\"" in source
    assert "ForEach(appState.configurationDiagnostics)" in source
    assert "DiagnosticRow" in source
    assert "appState.refreshBackendStatus()" in source
    assert "lastStatusCheckedAt" in source
    assert "xmark.circle.fill" in source
    assert "checkmark.circle.fill" in source
