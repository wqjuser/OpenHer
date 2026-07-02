import SwiftUI

/// Settings — paper aesthetic, server URL config.
struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @AppStorage("serverURL") private var serverURL = "http://localhost:8000"
    @AppStorage("apiToken") private var apiToken = ""
    @State private var isRefreshingDiagnostics = false

    var body: some View {
        Form {
            Section(L10n.str("后端服务器", en: "Backend Server")) {
                TextField("URL", text: $serverURL)
                    .textFieldStyle(.roundedBorder)

                SecureField(L10n.str("访问令牌（可选）", en: "API token (optional)"), text: $apiToken)
                    .textFieldStyle(.roundedBorder)

                Button(L10n.str("保存并重连", en: "Save & Reconnect")) {
                    appState.updateServerConfig(url: serverURL, apiToken: apiToken)
                }
                .foregroundStyle(Paper.coral)
            }

            Section(L10n.str("配置诊断", en: "Configuration Diagnostics")) {
                ForEach(appState.configurationDiagnostics) { diagnostic in
                    DiagnosticRow(diagnostic: diagnostic)
                }

                HStack {
                    Button {
                        refreshDiagnostics()
                    } label: {
                        Label(
                            L10n.str("刷新诊断", en: "Refresh Diagnostics"),
                            systemImage: "arrow.clockwise"
                        )
                    }
                    .disabled(isRefreshingDiagnostics)

                    Spacer()

                    if let checkedAt = appState.lastStatusCheckedAt {
                        Text(checkedAt, style: .time)
                            .font(Paper.tinyFont)
                            .foregroundStyle(Paper.faint)
                    }
                }
            }

            Section(L10n.str("展示", en: "Display")) {
                Toggle(L10n.str("仅显示已就绪角色", en: "Show ready personas only"), isOn: $appState.showOnlyReadyPersonas)
                    .help(L10n.str("开启后，仅展示有待唤醒展柜图片的角色", en: "When enabled, only personas with a cabinet image are shown"))
            }

            Section(L10n.str("开发者", en: "Developer")) {
                Toggle(L10n.str("开发者模式", en: "Developer Mode"), isOn: $appState.developerMode)
                    .help(L10n.str("开启后，每次启动从发现页开始，并打开引擎可视化窗口",
                                      en: "Start from Discovery on launch; open engine visualization"))
                    .onChange(of: appState.developerMode) { _, newValue in
                        if newValue {
                            NSApp.sendAction(Selector(("showEngineDebugWindow:")), to: nil, from: nil)
                        }
                    }

                if appState.developerMode {
                    Text(L10n.str("从菜单 Window → Persona Engine 打开可视化窗口",
                                  en: "Open via Window → Persona Engine menu"))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 440, height: 520)
        .task {
            if appState.lastStatusCheckedAt == nil {
                await appState.refreshBackendStatus()
            }
        }
    }

    private func refreshDiagnostics() {
        isRefreshingDiagnostics = true
        Task {
            await appState.refreshBackendStatus()
            isRefreshingDiagnostics = false
        }
    }
}

private struct DiagnosticRow: View {
    let diagnostic: ConfigurationDiagnostic

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: diagnostic.available ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundStyle(diagnostic.available ? Paper.ink : Paper.coral)
                .font(.system(size: 14, weight: .medium))
                .frame(width: 18)

            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(diagnostic.title)
                        .font(Paper.freqFont)
                        .foregroundStyle(Paper.herText)

                    Text(diagnostic.provider)
                        .font(Paper.tinyFont)
                        .foregroundStyle(Paper.faint)
                        .lineLimit(1)
                }

                Text(diagnostic.detail)
                    .font(Paper.tinyFont)
                    .foregroundStyle(Paper.faint)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
