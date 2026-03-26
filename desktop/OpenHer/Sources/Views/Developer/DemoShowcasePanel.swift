import SwiftUI

// MARK: - Act Mode

enum DemoActMode: String, CaseIterable {
    case personas = "人格对比"
    case memory   = "记忆注入"
    case emotion  = "压力来源"
    case time     = "时间关系"
}

// MARK: - DemoShowcasePanel

/// Audience-facing showcase panel for video recording.
/// Clean, cinematic — no operator controls, only live state visualization.
/// ⌘S toggles visibility. Mode switches with ⌘1–4 or via DemoBar.
struct DemoShowcasePanel: View {
    @EnvironmentObject var appState: AppState

    private var actMode: DemoActMode {
        switch appState.demoActMode {
        case 1: return .personas
        case 2: return .memory
        case 3: return .emotion
        case 4: return .time
        default: return .personas
        }
    }

    // Memory pill flash state (key = memory content keyword)
    @State private var flashedMemories: Set<String> = []

    // Previous monologue for transition animation
    @State private var displayedMonologue: String = ""

    // Injected memories tracking
    @State private var injectedMemories: [(icon: String, label: String, key: String)] = []

    private let allMemories: [(icon: String, label: String, key: String)] = [
        ("☕", "美式不加糖", "美式"),
        ("🐱", "团子", "团子"),
        ("🏃", "跑步", "跑步"),
    ]

    // Signal display config
    private let signalConfig: [(key: String, label: String, color: Color)] = [
        ("warmth",        "温暖",  Color(red: 0.92, green: 0.45, blue: 0.35)),
        ("vulnerability", "脆弱",  Color(red: 0.65, green: 0.45, blue: 0.82)),
        ("depth",         "深度",  Color(red: 0.28, green: 0.56, blue: 0.72)),
        ("playfulness",   "活泼",  Color(red: 0.95, green: 0.70, blue: 0.20)),
        ("directness",    "直接",  Color(red: 0.35, green: 0.72, blue: 0.55)),
        ("curiosity",     "好奇",  Color(red: 0.55, green: 0.75, blue: 0.90)),
        ("defiance",      "张力",  Color(red: 0.85, green: 0.38, blue: 0.25)),
        ("initiative",    "主动",  Color(red: 0.72, green: 0.60, blue: 0.45)),
    ]

    private let driveConfig: [(key: String, icon: String, label: String)] = [
        ("connection",  "🔗", "联结"),
        ("novelty",     "✨", "新奇"),
        ("expression",  "💬", "表达"),
        ("safety",      "🛡", "安全"),
        ("play",        "🎭", "玩乐"),
    ]

    var body: some View {
        VStack(spacing: 0) {
            headerSection
            Divider().opacity(0.2).padding(.horizontal, 20)
            monologueSection
            Divider().opacity(0.2).padding(.horizontal, 20)
            modeSection
                .frame(height: 360)
            Divider().opacity(0.2).padding(.horizontal, 20)
            temperatureSection
        }
        .frame(width: 420)
        .background(Paper.background.ignoresSafeArea())
        .onAppear {
            displayedMonologue = appState.engineDebug.monologue
            appState.developerMode = true
            appState.demoMode = true
            // Fetch current drive state immediately (no conversation needed)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                appState.demoFetchState()
            }
        }
        .onChange(of: appState.engineDebug.monologue) { _, newVal in
            withAnimation(.easeInOut(duration: 0.4)) {
                displayedMonologue = newVal
            }
            // Flash memory pills if monologue mentions them
            checkMemoryFlash(in: newVal)
        }
        .onChange(of: appState.demoSnapshot?.temperature) { _, _ in
            syncInjectedMemories()
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(spacing: 8) {
            HStack(alignment: .center, spacing: 10) {
                // Persona indicator
                personaIndicator

                Spacer()

                // Mode switcher
                modePicker
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)

            // Big demo title banner (set by script)
            if !appState.demoTitle.isEmpty {
                Text(appState.demoTitle)
                    .font(.system(size: 20, weight: .bold, design: .rounded))
                    .foregroundStyle(Paper.herText)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(Paper.coral.opacity(0.08))
                    )
                    .padding(.horizontal, 16)
                    .transition(.opacity.combined(with: .scale(scale: 0.95)))
                    .animation(.spring(duration: 0.4), value: appState.demoTitle)
            }

            // Relationship depth bar
            relationshipRow
                .padding(.horizontal, 16)
                .padding(.bottom, 10)
        }
    }

    private var personaIndicator: some View {
        HStack(spacing: 7) {
            let persona = appState.selectedPersona
            Text(personaEmoji)
                .font(.system(size: 18))
            VStack(alignment: .leading, spacing: 1) {
                Text(persona?.name ?? "—")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(Paper.herText)
                Text(actMode.rawValue)
                    .font(.system(size: 11))
                    .foregroundStyle(Paper.faint)
            }
        }
    }

    private var personaEmoji: String {
        switch appState.selectedPersonaId {
        case "luna":   return "🌸"
        case "vivian": return "💼"
        case "kai":    return "🔧"
        default:       return "✦"
        }
    }

    private var modePicker: some View {
        HStack(spacing: 4) {
            ForEach(Array(DemoActMode.allCases.enumerated()), id: \.offset) { idx, mode in
                Button {
                    withAnimation(.spring(duration: 0.3)) { appState.demoActMode = idx + 1 }
                } label: {
                    Text("\(idx + 1)")
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundStyle(actMode == mode ? .white : Paper.faint)
                        .frame(width: 20, height: 20)
                        .background(
                            Circle()
                                .fill(actMode == mode ? Paper.coral : Paper.faint.opacity(0.2))
                        )
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var relationshipRow: some View {
        let depth = appState.engineDebug.relationship["depth"] ?? 0

        return HStack(spacing: 8) {
            Text("💕 亲密度")
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(Paper.faint)

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Paper.faint.opacity(0.2))
                    RoundedRectangle(cornerRadius: 4)
                        .fill(
                            LinearGradient(
                                colors: [Paper.coral.opacity(0.6), Paper.coral],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: geo.size.width * min(depth, 1.0))
                        .animation(.spring(duration: 0.8), value: depth)
                }
            }
            .frame(height: 8)

            Text(String(format: "%.2f", depth))
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundStyle(Paper.herText)
        }
    }

    // MARK: - Monologue

    private var monologueSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("内心独白")
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(Paper.faint)
                .padding(.horizontal, 20)
                .padding(.top, 12)

            if displayedMonologue.isEmpty {
                Text("…")
                    .font(.system(size: 14, design: .serif))
                    .italic()
                    .foregroundStyle(Paper.faint.opacity(0.5))
                    .padding(.horizontal, 20)
                    .padding(.bottom, 14)
            } else {
                Text("「\(displayedMonologue)」")
                    .font(.system(size: 14, weight: .regular, design: .serif))
                    .italic()
                    .foregroundStyle(Paper.herText.opacity(0.85))
                    .lineSpacing(6)
                    .lineLimit(5)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 14)
                    .transition(.opacity.combined(with: .move(edge: .bottom)))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.orange.opacity(0.05))
    }

    // MARK: - Mode Section

    @ViewBuilder
    private var modeSection: some View {
        switch actMode {
        case .personas: signalsSection
        case .memory:   memoriesSection
        case .emotion:  emotionSection
        case .time:     timeSection
        }
    }

    // MARK: Mode 1: Behavioral Signals

    private var signalsSection: some View {
        VStack(spacing: 16) {
            VStack(spacing: 4) {
                Text("行为信号")
                    .font(.system(size: 16, weight: .bold, design: .rounded))
                    .foregroundStyle(Paper.herText)
                Text("她从你的话里读出了什么")
                    .font(.system(size: 11))
                    .foregroundStyle(Paper.faint)
            }
            .frame(maxWidth: .infinity)

            VStack(spacing: 9) {
                ForEach(signalConfig, id: \.key) { cfg in
                    let value = appState.engineDebug.signals[cfg.key] ?? 0
                    HStack(spacing: 10) {
                        Text(cfg.label)
                            .font(.system(size: 13))
                            .foregroundStyle(Paper.herText.opacity(0.75))
                            .frame(width: 36, alignment: .leading)

                        GeometryReader { geo in
                            ZStack(alignment: .leading) {
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Paper.faint.opacity(0.15))
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(cfg.color.opacity(0.80))
                                    .frame(width: geo.size.width * min(value, 1.0))
                                    .animation(.spring(duration: 0.6), value: value)
                            }
                        }
                        .frame(height: 10)

                        Text(String(format: "%.2f", value))
                            .font(.system(size: 12, weight: .medium, design: .monospaced))
                            .foregroundStyle(Paper.herText.opacity(0.6))
                            .frame(width: 36, alignment: .trailing)
                    }
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
    }

    // MARK: Mode 2: Memory Pills

    private var memoriesSection: some View {
        VStack(spacing: 20) {
            VStack(spacing: 4) {
                Text("EverMemOS · 记忆")
                    .font(.system(size: 16, weight: .bold, design: .rounded))
                    .foregroundStyle(Paper.herText)
                Text("注入的记忆会融入她的回复")
                    .font(.system(size: 11))
                    .foregroundStyle(Paper.faint)
            }
            .frame(maxWidth: .infinity)

            HStack(spacing: 0) {
                ForEach(allMemories, id: \.key) { mem in
                    let isInjected = appState.demoInjectedMemoryKeys.contains { $0.contains(mem.key) }

                    memoryPill(
                        icon: mem.icon,
                        label: mem.label,
                        injected: isInjected,
                        flashing: isInjected
                    )
                    .frame(maxWidth: .infinity)
                }
            }

            // Hint
            if appState.demoInjectedMemoryKeys.isEmpty {
                Text("注入记忆后，她会在对话中自然提及")
                    .font(.system(size: 12))
                    .foregroundStyle(Paper.faint.opacity(0.7))
                    .italic()
            } else {
                Text("记忆已注入 EverMemOS · 下次对话生效")
                    .font(.system(size: 12))
                    .foregroundStyle(Paper.coral.opacity(0.8))
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
    }

    private func memoryPill(icon: String, label: String, injected: Bool, flashing: Bool) -> some View {
        VStack(spacing: 10) {
            ZStack {
                Circle()
                    .fill(injected
                          ? (flashing ? Paper.coral : Color.purple.opacity(0.55))
                          : Paper.faint.opacity(0.15))
                    .frame(width: 88, height: 88)

                if flashing {
                    Circle()
                        .stroke(Paper.coral, lineWidth: 3)
                        .frame(width: 88, height: 88)
                        .opacity(0.8)
                        .scaleEffect(flashing ? 1.2 : 1.0)
                        .animation(.easeOut(duration: 0.5), value: flashing)
                }

                Text(icon)
                    .font(.system(size: 36))
                    .opacity(injected ? 1.0 : 0.35)
            }

            Text(label)
                .font(.system(size: 13, weight: injected ? .semibold : .regular))
                .foregroundStyle(injected ? Paper.herText : Paper.faint)
                .lineLimit(1)
        }
        .animation(.spring(duration: 0.4), value: injected)
        .animation(.spring(duration: 0.3), value: flashing)
    }

    // MARK: Mode 3: Emotion / Frustration

    private var emotionSection: some View {
        let _ = driveConfig // suppress unused warning
        let temp = appState.demoSnapshot?.temperature ?? appState.engineDebug.temperature

        return VStack(spacing: 16) {
            // Big prominent title
            VStack(spacing: 4) {
                Text("压力来源")
                    .font(.system(size: 16, weight: .bold, design: .rounded))
                    .foregroundStyle(Paper.herText)
                Text("各维度不满值，越高越容易爆发")
                    .font(.system(size: 11))
                    .foregroundStyle(Paper.faint)
            }
            .frame(maxWidth: .infinity)

            // Bar rows: icon + label → bar → value
            VStack(spacing: 14) {
                ForEach(driveConfig, id: \.key) { drv in
                    let frust = appState.demoSnapshot?.frustration[drv.key] ?? 0
                    let isHot = frust > 1.2
                    let ratio = min(frust / 3.0, 1.0)

                    HStack(spacing: 10) {
                        // Icon + label
                        HStack(spacing: 6) {
                            Text(drv.icon)
                                .font(.system(size: 16))
                            Text(drv.label)
                                .font(.system(size: 14, weight: .medium))
                                .foregroundStyle(isHot ? Paper.coral : Paper.herText.opacity(0.7))
                        }
                        .frame(width: 60, alignment: .leading)
                        .animation(.easeInOut, value: isHot)

                        // Bar
                        GeometryReader { geo in
                            ZStack(alignment: .leading) {
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Paper.faint.opacity(0.15))
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(frustColor(frust))
                                    .frame(width: geo.size.width * ratio)
                                    .animation(.spring(duration: 0.5), value: frust)
                            }
                        }
                        .frame(height: 10)

                        // Value
                        Text(String(format: "%.1f", frust))
                            .font(.system(size: 14, weight: .semibold, design: .monospaced))
                            .foregroundStyle(isHot ? Paper.coral : Paper.faint)
                            .frame(width: 32, alignment: .trailing)
                            .contentTransition(.numericText())
                            .animation(.easeInOut, value: frust)
                    }
                }
            }

            // Status label
            HStack(spacing: 8) {
                Circle()
                    .fill(temp > 0.22 ? Color.red : (temp > 0.12 ? Color.orange : Color.green))
                    .frame(width: 8, height: 8)
                    .animation(.easeInOut, value: temp)
                Text(statusLabel(temp))
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(Paper.herText.opacity(0.7))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }

    private func statusLabel(_ temp: Double) -> String {
        if temp > 0.25 { return "临界爆发" }
        if temp > 0.18 { return "挫败积累中" }
        if temp > 0.08 { return "轻微烦躁" }
        return "情绪稳定"
    }

    // MARK: Mode 4: Time / Relationship

    private var timeSection: some View {
        let connection = appState.demoSnapshot?.driveState["connection"] ?? 0
        let isHungry   = connection < 0.2

        return VStack(spacing: 16) {
            VStack(spacing: 4) {
                Text("想念指数")
                    .font(.system(size: 16, weight: .bold, design: .rounded))
                    .foregroundStyle(Paper.herText)
                Text("越高越想主动找你说话")
                    .font(.system(size: 11))
                    .foregroundStyle(Paper.faint)
            }
            .frame(maxWidth: .infinity)

            // Connection drive bar
            VStack(alignment: .leading, spacing: 6) {

                HStack(spacing: 8) {
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Paper.faint.opacity(0.15))
                            RoundedRectangle(cornerRadius: 4)
                                .fill(isHungry ? Paper.coral : Paper.ink.opacity(0.5))
                                .frame(width: geo.size.width * min(connection, 1.0))
                                .animation(.spring(duration: 0.6), value: connection)
                        }
                    }
                    .frame(height: 10)

                    Text(String(format: "%.2f", connection))
                        .font(.system(size: 14, weight: .medium, design: .monospaced))
                        .foregroundStyle(isHungry ? Paper.coral : Paper.herText)
                        .contentTransition(.numericText())
                        .animation(.spring(duration: 0.6), value: connection)
                        .frame(width: 40, alignment: .trailing)
                }
            }

            if isHungry {
                HStack(spacing: 6) {
                    Image(systemName: "bubble.left.fill")
                        .font(.system(size: 10))
                        .foregroundStyle(Paper.coral.opacity(0.7))
                    Text("她即将主动发消息…")
                        .font(.system(size: 11))
                        .italic()
                        .foregroundStyle(Paper.herText.opacity(0.7))
                }
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .animation(.spring(duration: 0.5), value: isHungry)
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
    }

    // MARK: - Temperature Bar (always visible)

    private var temperatureSection: some View {
        let temp = appState.demoSnapshot?.temperature ?? appState.engineDebug.temperature

        return HStack(spacing: 10) {
            Text("🌡")
                .font(.system(size: 13))
            Text("情绪压力")
                .font(.system(size: 11))
                .foregroundStyle(Paper.faint)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Paper.faint.opacity(0.15))
                    RoundedRectangle(cornerRadius: 4)
                        .fill(tempGradient(temp))
                        .frame(width: geo.size.width * min(temp, 1.0))
                        .animation(.spring(duration: 0.5), value: temp)
                }
            }
            .frame(height: 8)
            Text(String(format: "%.3f", temp))
                .font(.system(size: 12, weight: .medium, design: .monospaced))
                .foregroundStyle(Paper.herText.opacity(0.6))
                .frame(width: 46, alignment: .trailing)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }

    // MARK: - Helpers

    private func frustColor(_ value: Double) -> Color {
        if value > 1.5 { return Color.red.opacity(0.75) }
        if value > 0.8 { return Color.orange.opacity(0.65) }
        return Paper.coral.opacity(0.45)
    }

    private func tempGradient(_ value: Double) -> Color {
        if value > 0.3 { return Color.red.opacity(0.7) }
        if value > 0.15 { return Color.orange.opacity(0.6) }
        return Paper.coral.opacity(0.4)
    }

    private func syncInjectedMemories() {
        // Sync injected pills from DemoBar actions
        // DemoBar calls demoInjectMemory which sends WebSocket — we read from AppState presets
        // For now track via monologue keyword mentions as proxy
    }

    private func checkMemoryFlash(in text: String) {
        let lowered = text.lowercased()
        var toFlash: Set<String> = []
        for mem in allMemories {
            if lowered.contains(mem.key) { toFlash.insert(mem.key) }
        }
        guard !toFlash.isEmpty else { return }
        withAnimation(.spring(duration: 0.3)) {
            flashedMemories = flashedMemories.union(toFlash)
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
            withAnimation(.easeOut(duration: 0.5)) {
                flashedMemories = flashedMemories.subtracting(toFlash)
            }
        }
    }
}
