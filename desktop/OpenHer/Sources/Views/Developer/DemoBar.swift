import SwiftUI

/// Operator control panel for demo recording.
/// Clean, organized — controls only, no state display (see DemoShowcasePanel).
/// ⌘D toggles visibility.
struct DemoBar: View {
    @EnvironmentObject var appState: AppState

    @State private var lastAction: String = ""
    @State private var actionOpacity: Double = 0

    private let personas: [(id: String, name: String, mbti: String)] = [
        ("luna",   "Luna",   "INFP"),
        ("vivian", "Vivian", "ENTJ"),
        ("kai",    "Kai",    "ISTP"),
    ]

    private let timeJumps: [(hours: Double, label: String)] = [
        (1, "+1h"), (4, "+4h"), (8, "+8h"), (24, "+24h"),
    ]

    private let scriptMessages: [(label: String, msg: String)] = [
        ("项目被毙了",    "今天项目被毙了，心情很差"),
        ("没睡好",        "今天没睡好，感觉很累"),
        ("团子闯祸",      "团子今天把我耳机线咬断了"),
        ("团子可爱",      "对啊，上次咬完跑得飞快，超可爱的"),
        ("方案被否",      "方案又被否了"),
        ("有点烦",        "今天有点烦"),
    ]

    private let memories: [(icon: String, label: String, content: String, category: String)] = [
        ("☕", "美式不加糖", "用户喜欢喝美式咖啡，不加糖不加奶", "preference"),
        ("🐱", "猫叫团子",   "用户养了一只橘猫，名叫团子，3岁了", "fact"),
        ("🏃", "跑步爱好",   "用户每天早上跑5公里，最近在备战马拉松", "fact"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            divider
            personaSection
            divider
            timeSection
            divider
            testSection
            divider
            memorySection
        }
        .background(Paper.background)
        .onAppear {
            appState.demoMode = true
            appState.demoLoadPresets()
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 8) {
            Text("DEMO")
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(RoundedRectangle(cornerRadius: 5).fill(Paper.coral))

            if !lastAction.isEmpty {
                Text("→ \(lastAction)")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(Paper.coral.opacity(0.8))
                    .opacity(actionOpacity)
                    .animation(.easeInOut(duration: 0.2), value: actionOpacity)
            }

            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }

    // MARK: - Persona

    private var personaSection: some View {
        sectionRow(label: "人格") {
            HStack(spacing: 6) {
                ForEach(personas, id: \.id) { p in
                    let selected = appState.selectedPersonaId == p.id
                    Button {
                        appState.demoSwitchPersona(p.id)
                        flash(p.name)
                    } label: {
                        VStack(spacing: 2) {
                            Text(p.name).font(.system(size: 12, weight: selected ? .semibold : .regular))
                            Text(p.mbti)
                                .font(.system(size: 9, weight: .medium, design: .monospaced))
                                .opacity(0.7)
                        }
                        .foregroundStyle(selected ? .white : Paper.herText)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(
                            RoundedRectangle(cornerRadius: 10)
                                .fill(selected ? Paper.coral : Paper.faint.opacity(0.18))
                        )
                    }
                    .buttonStyle(.plain)
                    .animation(.spring(duration: 0.25), value: selected)
                }
                Spacer()
            }
        }
    }

    // MARK: - Time Jump

    private var timeSection: some View {
        sectionRow(label: "时间") {
            HStack(spacing: 6) {
                ForEach(timeJumps, id: \.hours) { t in
                    Button(t.label) {
                        appState.demoTimeJump(hours: t.hours)
                        flash("⏩ \(t.label)")
                    }
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                    .foregroundStyle(Paper.ink)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(Paper.ink.opacity(0.08))
                    )
                    .buttonStyle(.plain)
                }
                Spacer()
            }
        }
    }

    // MARK: - Unified Test Section

    private var testSection: some View {
        sectionRow(label: "测试") {
            VStack(alignment: .leading, spacing: 6) {
                // Row 1: Pressure tests
                HStack(spacing: 6) {
                    testButton("💥", "压力测试", Color.red.opacity(0.65)) {
                        appState.demoApplyScenario("about_to_snap")
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                            appState.sendMessage("今天项目被毙了，心情很差")
                        }
                        flash("💥 压力测试")
                    }
                    testButton("😑", "敷衍刺激", Color.orange.opacity(0.65)) {
                        flash("😑 连发敷衍…")
                        let msgs = ["嗯", "哦", "嗯嗯", "哦"]
                        for (i, msg) in msgs.enumerated() {
                            DispatchQueue.main.asyncAfter(deadline: .now() + Double(i) * 11.0) {
                                appState.sendMessage(msg)
                            }
                        }
                    }
                    testButton("😢", "孤独测试", Color.blue.opacity(0.50)) {
                        appState.demoApplyScenario("lonely")
                        flash("😢 孤独测试")
                    }
                    Spacer()
                }
                // Row 2: Positive / normal
                HStack(spacing: 6) {
                    testButton("💕", "亲密对话", Color.pink.opacity(0.60)) {
                        appState.demoApplyScenario("deeply_bonded")
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                            appState.sendMessage("团子今天把我耳机线咬断了")
                        }
                        flash("💕 亲密对话")
                    }
                    testButton("💬", "正常对话", Paper.faint.opacity(0.35)) {
                        appState.demoApplyScenario("calm_reset")
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                            appState.sendMessage("今天没睡好，感觉很累")
                        }
                        flash("💬 正常对话")
                    }
                    testButton("🧠", "记忆测试", Color.purple.opacity(0.55)) {
                        appState.sendMessage("今天没睡好，感觉很累")
                        flash("🧠 记忆测试")
                    }
                    Spacer()
                }
            }
        }
        .padding(.bottom, 4)
    }

    private func testButton(_ icon: String, _ label: String, _ color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 3) {
                Text(icon).font(.system(size: 12))
                Text(label).font(.system(size: 11, weight: .medium))
            }
            .foregroundStyle(color == Paper.faint.opacity(0.35) ? Paper.herText : .white)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(RoundedRectangle(cornerRadius: 8).fill(color))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Memory

    private var memorySection: some View {
        sectionRow(label: "记忆") {
            HStack(spacing: 6) {
                ForEach(memories, id: \.label) { m in
                    Button {
                        appState.demoInjectMemory(content: m.content, category: m.category)
                        flash("注入: \(m.label)")
                    } label: {
                        HStack(spacing: 4) {
                            Text(m.icon).font(.system(size: 12))
                            Text(m.label).font(.system(size: 11))
                        }
                        .foregroundStyle(.white)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(
                            RoundedRectangle(cornerRadius: 8)
                                .fill(Color(red: 0.48, green: 0.32, blue: 0.72).opacity(0.75))
                        )
                    }
                    .buttonStyle(.plain)
                }
                Spacer()
            }
        }
    }

    // MARK: - Layout Helpers

    private var divider: some View {
        Divider()
            .opacity(0.2)
            .padding(.horizontal, 12)
    }

    private func sectionRow<Content: View>(label: String, @ViewBuilder content: () -> Content) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(label)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(Paper.faint)
                .frame(width: 44, alignment: .trailing)
                .padding(.top, 6)

            content()
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    // MARK: - Flash Feedback

    private func flash(_ text: String) {
        lastAction = text
        withAnimation { actionOpacity = 1 }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            withAnimation(.easeOut(duration: 0.4)) { actionOpacity = 0 }
        }
    }
}
