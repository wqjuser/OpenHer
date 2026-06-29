import SwiftUI

/// Menu bar dropdown — paper aesthetic, shows persona + quick actions.
struct MenuBarView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Connection status
            HStack(spacing: 6) {
                Circle()
                    .fill(appState.canSendChat ? Paper.coral : Paper.faint)
                    .frame(width: 6, height: 6)
                VStack(alignment: .leading, spacing: 2) {
                    Text(connectionLabel)
                        .font(Paper.freqFont)
                        .foregroundStyle(Paper.herText)
                    if appState.isConnected, let reason = appState.chatUnavailableReason {
                        Text(reason)
                            .font(Paper.tinyFont)
                            .foregroundStyle(Paper.faint)
                    }
                }
            }

            Divider()

            // Current persona
            if let persona = appState.selectedPersona {
                HStack(spacing: 8) {
                    Circle()
                        .fill(Paper.ink.opacity(0.2))
                        .frame(width: 24, height: 24)
                        .overlay(
                            Text(String(persona.displayName.prefix(1)))
                                .font(.system(size: 12))
                                .foregroundStyle(Paper.ink)
                        )
                    VStack(alignment: .leading, spacing: 2) {
                        Text(persona.displayName)
                            .font(Paper.nameFont)
                            .foregroundStyle(Paper.herText)
                        Text(L10n.str("FREQ. 调频中 ∿", en: "FREQ. tuning ∿"))
                            .font(Paper.tinyFont)
                            .foregroundStyle(Paper.coral)
                    }
                }
            }

            Divider()

            // Persona list for switching
            if appState.personas.count > 1 {
                Text(L10n.str("切换角色", en: "Switch Persona"))
                    .font(Paper.tinyFont)
                    .foregroundStyle(Paper.faint)

                ForEach(appState.personas) { persona in
                    Button {
                        appState.selectPersona(persona.personaId)
                    } label: {
                        Text(persona.displayName)
                            .font(Paper.freqFont)
                            .foregroundStyle(Paper.herText)
                    }
                    .buttonStyle(.plain)
                }

                Divider()
            }

            // Actions
            Button(L10n.str("打开对话 ⌘⇧O", en: "Open Chat ⌘⇧O")) {}
                .buttonStyle(.plain)
                .font(Paper.freqFont)

            Button(L10n.str("设置...", en: "Settings...")) {
                NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
            }
            .buttonStyle(.plain)
            .font(Paper.freqFont)

            Button(L10n.str("退出", en: "Quit")) {
                NSApp.terminate(nil)
            }
            .buttonStyle(.plain)
            .font(Paper.freqFont)
            .foregroundStyle(Paper.coral)
        }
        .padding(16)
        .frame(width: 200)
    }

    private var connectionLabel: String {
        if !appState.isConnected {
            return L10n.str("未连接", en: "Disconnected")
        }
        if !appState.canSendChat {
            return L10n.str("聊天不可用", en: "Chat unavailable")
        }
        return L10n.str("已连接", en: "Connected")
    }
}
