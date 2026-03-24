import SwiftUI

/// Floating Demo Bar HUD — standalone window for presentation mode.
/// ⌘D toggles visibility. Contains persona switch, time jumps, preset messages, and live status.
struct DemoBar: View {
    @EnvironmentObject var appState: AppState

    // Last action feedback
    @State private var lastAction: String = ""
    @State private var actionOpacity: Double = 0

    // Delta tracking
    @State private var prevSnapshot: DemoEngineSnapshot? = nil
    @State private var flashDrives: Set<String> = []

    // Drive emoji labels
    private let driveIcons: [(key: String, icon: String, label: String)] = [
        ("connection", "🔗", "联结"),
        ("novelty", "✨", "新奇"),
        ("expression", "💬", "表达"),
        ("safety", "🛡️", "安全"),
        ("play", "🎭", "玩乐"),
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
        VStack(spacing: 8) {
            // Header + action feedback
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

                // Action feedback toast
                if !lastAction.isEmpty {
                    Text(lastAction)
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Paper.coral)
                        .opacity(actionOpacity)
                        .transition(.opacity)
                }

                Spacer()

                // Scenario picker
                Menu {
                    ForEach(Array(appState.demoScenarios), id: \.key) { key, scenario in
                        Button("\(scenario.label)  \(scenario.description)") {
                            appState.demoApplyScenario(key)
                            showAction("🎚️ \(scenario.label)")
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

            Divider().opacity(0.3)

            // Row 1: Persona switch
            HStack(spacing: 8) {
                ForEach(demoPersonas, id: \.id) { persona in
                    let isSelected = appState.selectedPersonaId == persona.id
                    Button(persona.label) {
                        appState.demoSwitchPersona(persona.id)
                        showAction("👤 → \(persona.label)")
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
                        showAction("⏩ \(jump.label)")
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

            // Row 3: Preset quick messages
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    Text("💬")
                        .font(.system(size: 12))
                    ForEach([
                        ("在干嘛呢？", "在干嘛呢？"),
                        ("帮我买杯咖啡呗", "帮我买杯咖啡呗"),
                        ("今天好累啊", "今天好累啊"),
                        ("想你了", "想你了"),
                        ("晚上吃什么", "晚上吃什么"),
                    ], id: \.0) { (label, msg) in
                        Button(label) {
                            appState.sendMessage(msg)
                            showAction("💬 \(label)")
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

            // Row 4: Memory injection
            HStack(spacing: 6) {
                Text("🧠")
                    .font(.system(size: 12))
                Button("☕ 美式不加糖") {
                    appState.demoInjectMemory(content: "用户喜欢喝美式咖啡,不加糖不加奶", category: "preference")
                    showAction("🧠 记忆已注入: 美式不加糖")
                }
                .font(.system(size: 11))
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.purple.opacity(0.6))
                )
                .buttonStyle(.plain)

                Button("🐱 养了猫叫团子") {
                    appState.demoInjectMemory(content: "用户养了一只橘猫,名叫团子,3岁了", category: "fact")
                    showAction("🧠 记忆已注入: 猫叫团子")
                }
                .font(.system(size: 11))
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.purple.opacity(0.6))
                )
                .buttonStyle(.plain)

                Button("🏃 跑步爱好") {
                    appState.demoInjectMemory(content: "用户每天早上跑5公里,最近在备战马拉松", category: "fact")
                    showAction("🧠 记忆已注入: 跑步爱好")
                }
                .font(.system(size: 11))
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.purple.opacity(0.6))
                )
                .buttonStyle(.plain)

                Spacer()
            }

            // Row 5: Dismissive spam (emotion accumulation demo)
            HStack(spacing: 6) {
                Text("😑")
                    .font(.system(size: 12))
                Button("连发敷衍 (嗯→哦→嗯嗯)") {
                    showAction("😑 连发敷衍中...")
                    // Send 3 dismissive messages with delays
                    let msgs = ["嗯", "哦", "嗯嗯"]
                    for (i, msg) in msgs.enumerated() {
                        DispatchQueue.main.asyncAfter(deadline: .now() + Double(i) * 12.0) {
                            appState.sendMessage(msg)
                            showAction("😑 [\(i+1)/3] \(msg)")
                        }
                    }
                }
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(.white)
                .padding(.horizontal, 10)
                .padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.orange.opacity(0.7))
                )
                .buttonStyle(.plain)

                Spacer()
            }

            // Row 6: Scenario injection
            HStack(spacing: 6) {
                Text("🎚️")
                    .font(.system(size: 12))
                Button("💥 爆发") {
                    appState.demoApplyScenario("about_to_snap")
                    showAction("🎚️ 场景: 即将爆发")
                }
                .font(.system(size: 11))
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(RoundedRectangle(cornerRadius: 8).fill(Color.red.opacity(0.6)))
                .buttonStyle(.plain)

                Button("😢 孤独") {
                    appState.demoApplyScenario("lonely")
                    showAction("🎚️ 场景: 孤独8h")
                }
                .font(.system(size: 11))
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(RoundedRectangle(cornerRadius: 8).fill(Color.blue.opacity(0.5)))
                .buttonStyle(.plain)

                Button("💕 深度") {
                    appState.demoApplyScenario("deeply_bonded")
                    showAction("🎚️ 场景: 深度关系")
                }
                .font(.system(size: 11))
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(RoundedRectangle(cornerRadius: 8).fill(Color.pink.opacity(0.6)))
                .buttonStyle(.plain)

                Button("🧘 重置") {
                    appState.demoApplyScenario("calm_reset")
                    showAction("🎚️ 场景: 冷静重置")
                }
                .font(.system(size: 11))
                .foregroundStyle(Paper.herText)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(RoundedRectangle(cornerRadius: 8).fill(Paper.faint.opacity(0.2)))
                .buttonStyle(.plain)

                Spacer()
            }

            Divider().opacity(0.3)

            // Monologue display — show AI's inner thoughts
            if !appState.engineDebug.monologue.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    Text("💭 内心独白")
                        .font(.system(size: 9, weight: .medium))
                        .foregroundStyle(Paper.faint)
                    Text("「\(appState.engineDebug.monologue)」")
                        .font(.system(size: 11, weight: .regular, design: .serif))
                        .italic()
                        .foregroundStyle(Paper.herText.opacity(0.8))
                        .lineLimit(3)
                        .lineSpacing(3)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 6)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.orange.opacity(0.06))
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .strokeBorder(Color.orange.opacity(0.15))
                        )
                )
            }

            Divider().opacity(0.3)

            // Row 4: Live drive status with deltas
            VStack(spacing: 4) {
                // Drive values
                HStack(spacing: 10) {
                    ForEach(driveIcons, id: \.key) { drive in
                        let value = appState.demoSnapshot?.driveState[drive.key] ?? 0
                        let frust = appState.demoSnapshot?.frustration[drive.key] ?? 0
                        let isFlashing = flashDrives.contains(drive.key)

                        VStack(spacing: 1) {
                            // Chinese label
                            Text(drive.label)
                                .font(.system(size: 9, weight: .medium))
                                .foregroundStyle(Paper.faint)
                            // Drive value
                            HStack(spacing: 2) {
                                Text(drive.icon)
                                    .font(.system(size: 9))
                                Text(String(format: "%.2f", value))
                                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                                    .foregroundStyle(isFlashing ? Paper.coral : Paper.herText)
                            }
                            // Frustration bar
                            GeometryReader { geo in
                                ZStack(alignment: .leading) {
                                    RoundedRectangle(cornerRadius: 2)
                                        .fill(Paper.faint.opacity(0.15))
                                    RoundedRectangle(cornerRadius: 2)
                                        .fill(frustColor(frust))
                                        .frame(width: geo.size.width * min(frust / 2.0, 1.0))
                                }
                            }
                            .frame(height: 3)
                            // Frustration value
                            Text(String(format: "挫败 %.1f", frust))
                                .font(.system(size: 8, design: .monospaced))
                                .foregroundStyle(Paper.faint)
                        }
                        .frame(width: 60)
                    }
                }

                // Temperature bar
                HStack(spacing: 6) {
                    Text("🌡️ 情绪温度")
                        .font(.system(size: 10))
                        .foregroundStyle(Paper.faint)
                    let temp = appState.demoSnapshot?.temperature ?? 0
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 3)
                                .fill(Paper.faint.opacity(0.15))
                            RoundedRectangle(cornerRadius: 3)
                                .fill(tempGradient(temp))
                                .frame(width: geo.size.width * min(temp, 1.0))
                        }
                    }
                    .frame(height: 6)
                    Text(String(format: "%.3f", temp))
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundStyle(Paper.herText)
                        .frame(width: 40, alignment: .trailing)
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Paper.background)
        .onAppear {
            appState.demoMode = true
            appState.demoLoadPresets()
        }
        .onChange(of: appState.demoSnapshot?.temperature) { _, _ in
            detectChanges()
        }
    }

    // MARK: - Helpers

    private func showAction(_ text: String) {
        lastAction = text
        withAnimation(.easeIn(duration: 0.1)) {
            actionOpacity = 1.0
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
            withAnimation(.easeOut(duration: 0.5)) {
                actionOpacity = 0
            }
        }
    }

    private func detectChanges() {
        guard let snap = appState.demoSnapshot else { return }
        if let prev = prevSnapshot {
            var changed: Set<String> = []
            for (key, val) in snap.driveState {
                if abs(val - (prev.driveState[key] ?? 0)) > 0.001 {
                    changed.insert(key)
                }
            }
            for (key, val) in snap.frustration {
                if abs(val - (prev.frustration[key] ?? 0)) > 0.001 {
                    changed.insert(key)
                }
            }
            if !changed.isEmpty {
                withAnimation(.easeIn(duration: 0.1)) {
                    flashDrives = changed
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                    withAnimation(.easeOut(duration: 0.3)) {
                        flashDrives = []
                    }
                }
            }
        }
        prevSnapshot = snap
    }

    private func frustColor(_ value: Double) -> Color {
        if value > 1.5 { return Color.red.opacity(0.8) }
        if value > 0.8 { return Color.orange.opacity(0.7) }
        return Paper.coral.opacity(0.5)
    }

    private func tempGradient(_ value: Double) -> Color {
        if value > 0.3 { return Color.red.opacity(0.7) }
        if value > 0.15 { return Color.orange.opacity(0.6) }
        return Paper.coral.opacity(0.4)
    }
}
