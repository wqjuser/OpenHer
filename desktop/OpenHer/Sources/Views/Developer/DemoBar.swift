import SwiftUI

/// Floating Demo Bar HUD — overlays the conversation for presentation mode.
/// ⌘D toggles visibility. Contains persona switch, time jumps, preset messages, and live status.
struct DemoBar: View {
    @EnvironmentObject var appState: AppState

    // Drive emoji labels (matches backend DRIVE_LABELS)
    private let driveIcons: [(key: String, icon: String)] = [
        ("connection", "🔗"),
        ("novelty", "✨"),
        ("expression", "💬"),
        ("safety", "🛡️"),
        ("play", "🎭"),
    ]

    // Demo personas (3 contrasting)
    private let demoPersonas: [(id: String, label: String)] = [
        ("luna", "🌸 Luna"),
        ("vivian", "💼 Vivian"),
        ("kai", "🔧 Kai"),
    ]

    // Time jump options
    private let timeJumps: [(hours: Double, label: String)] = [
        (1, "+1h"),
        (4, "+4h"),
        (8, "+8h"),
        (24, "+24h"),
    ]

    var body: some View {
        VStack(spacing: 10) {
            // Header
            HStack {
                Text("DEMO")
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Paper.coral)
                    )

                Spacer()

                // Scenario picker
                Menu {
                    ForEach(Array(appState.demoScenarios), id: \.key) { key, scenario in
                        Button("\(scenario.label)  \(scenario.description)") {
                            appState.demoApplyScenario(key)
                        }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Text("🎚️")
                        Text(L10n.str("场景", en: "Scenarios"))
                            .font(.system(size: 11))
                            .foregroundStyle(Paper.herText)
                        Image(systemName: "chevron.down")
                            .font(.system(size: 8))
                            .foregroundStyle(Paper.faint)
                    }
                }
                .menuStyle(.borderlessButton)
            }

            // Row 1: Persona switch
            HStack(spacing: 8) {
                ForEach(demoPersonas, id: \.id) { persona in
                    let isSelected = appState.selectedPersonaId == persona.id
                    Button(persona.label) {
                        appState.demoSwitchPersona(persona.id)
                    }
                    .font(.system(size: 12, weight: isSelected ? .semibold : .regular))
                    .foregroundStyle(isSelected ? .white : Paper.herText)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(isSelected ? Paper.coral : Paper.coral.opacity(0.12))
                    )
                    .buttonStyle(.plain)
                }
                Spacer()
            }

            // Row 2: Time jumps
            HStack(spacing: 8) {
                Text("⏩")
                    .font(.system(size: 12))
                ForEach(timeJumps, id: \.hours) { jump in
                    Button(jump.label) {
                        appState.demoTimeJump(hours: jump.hours)
                    }
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                    .foregroundStyle(Paper.coral)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(Paper.coral.opacity(0.1))
                    )
                    .buttonStyle(.plain)
                }
                Spacer()
            }

            // Row 3: Preset messages
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(appState.demoPresets) { preset in
                        Button(preset.label) {
                            appState.demoSendPreset(preset)
                        }
                        .font(.system(size: 11))
                        .foregroundStyle(Paper.herText)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(
                            RoundedRectangle(cornerRadius: 8)
                                .fill(Paper.ink.opacity(0.06))
                        )
                        .buttonStyle(.plain)
                    }
                }
            }

            // Row 4: Live drive status
            HStack(spacing: 12) {
                ForEach(driveIcons, id: \.key) { drive in
                    let value = appState.demoSnapshot?.driveState[drive.key] ?? 0
                    HStack(spacing: 2) {
                        Text(drive.icon)
                            .font(.system(size: 10))
                        Text(String(format: "%.2f", value))
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(Paper.faint)
                    }
                }
                Divider()
                    .frame(height: 12)
                HStack(spacing: 2) {
                    Text("🌡️")
                        .font(.system(size: 10))
                    Text(String(format: "%.3f", appState.demoSnapshot?.temperature ?? 0))
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Paper.faint)
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Paper.background.opacity(0.6))
                )
                .shadow(color: Paper.faint.opacity(0.2), radius: 8, y: 2)
        )
        .padding(.horizontal, 12)
        .onAppear {
            appState.demoLoadPresets()
        }
    }
}
