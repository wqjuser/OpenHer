import Foundation

/// WebSocket manager handling the /ws/chat protocol.
/// Manages connection lifecycle, message parsing, and streaming.
@MainActor
final class WebSocketManager: ObservableObject {
    private weak var appState: AppState?
    private var webSocketTask: URLSessionWebSocketTask?
    private var sessionId: String?
    private var streamingContent: String = ""

    init(appState: AppState) {
        self.appState = appState
    }

    // MARK: - Connection

    func connect() {
        guard let appState = appState else { return }
        let wsURL = appState.serverURL
            .replacingOccurrences(of: "http://", with: "ws://")
            .replacingOccurrences(of: "https://", with: "wss://")
        guard let url = URL(string: "\(wsURL)/ws/chat") else { return }

        let session = URLSession(configuration: .default)
        var request = URLRequest(url: url)
        let apiToken = appState.apiToken.trimmingCharacters(in: .whitespacesAndNewlines)
        if !apiToken.isEmpty {
            request.setValue("Bearer \(apiToken)", forHTTPHeaderField: "Authorization")
        }
        webSocketTask = session.webSocketTask(with: request)
        webSocketTask?.resume()

        appState.isConnected = true
        
        // Send handshake with client_id so backend can route demo inject commands
        let handshake: [String: Any] = [
            "type": "handshake",
            "client_id": appState.getClientId(),
        ]
        sendJSON(handshake)
        
        listenForMessages()
        print("[WS] Connected to \(url) with client_id: \(appState.getClientId().prefix(12))...")
    }

    func disconnect() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        appState?.isConnected = false
        print("[WS] Disconnected")
    }

    // MARK: - Send

    func sendChat(content: String, personaId: String, clientId: String) {
        var payload: [String: Any] = [
            "type": "chat",
            "content": content,
            "persona_id": personaId,
            "client_id": clientId,
            "session_id": sessionId as Any,
        ]

        // Attach awakening greeting on first message so backend LLM has context
        if let appState = appState,
           let greetingMsg = appState.messages.first(where: { $0.id == "awakening-greeting" }) {
            payload["greeting"] = greetingMsg.content
        }

        // Developer mode or Demo mode: request full engine debug data
        if appState?.developerMode == true || appState?.demoMode == true {
            payload["debug"] = true
        }

        guard let data = try? JSONSerialization.data(withJSONObject: payload),
              let text = String(data: data, encoding: .utf8) else { return }

        webSocketTask?.send(.string(text)) { error in
            if let error = error {
                print("[WS] Send error: \(error)")
            }
        }
    }

    /// Notify the server whether the user is actively typing.
    /// This enables message debounce — the server buffers rapid messages
    /// and processes them as one turn once typing stops.
    func sendTypingIndicator(active: Bool) {
        let payload: [String: Any] = [
            "type": "typing",
            "active": active,
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: payload),
              let text = String(data: data, encoding: .utf8) else { return }

        webSocketTask?.send(.string(text)) { error in
            if let error = error {
                print("[WS] Typing indicator send error: \(error)")
            }
        }
    }

    // MARK: - Demo Mode

    func sendDemoTimeJump(hours: Double) {
        sendJSON(["type": "demo_time_jump", "hours": hours])
    }

    func sendDemoInject(overrides: [String: Any]) {
        sendJSON(["type": "demo_inject", "overrides": overrides])
    }

    func sendDemoScenario(scenarioId: String) {
        sendJSON(["type": "demo_scenario", "scenario_id": scenarioId])
    }

    func sendDemoPresets() {
        sendJSON(["type": "demo_presets"])
    }

    func sendDemoInjectMemory(content: String, category: String = "preference") {
        sendJSON([
            "type": "demo_inject_memory",
            "content": content,
            "category": category,
            "persona_id": appState?.selectedPersonaId ?? "",
            "client_id": appState?.getClientId() ?? "",
        ])
    }

    func sendSwitchPersona(personaId: String, clientId: String) {
        sendJSON([
            "type": "switch_persona",
            "persona_id": personaId,
            "client_id": clientId,
        ])
    }

    private func sendJSON(_ payload: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: payload),
              let text = String(data: data, encoding: .utf8) else { return }
        webSocketTask?.send(.string(text)) { error in
            if let error = error {
                print("[WS] Send error: \(error)")
            }
        }
    }

    // MARK: - Receive

    private func listenForMessages() {
        webSocketTask?.receive { [weak self] result in
            Task { @MainActor in
                switch result {
                case .success(let message):
                    switch message {
                    case .string(let text):
                        self?.handleMessage(text)
                    default:
                        break
                    }
                    // Continue listening
                    self?.listenForMessages()

                case .failure(let error):
                    print("[WS] Receive error: \(error)")
                    self?.appState?.isConnected = false
                    // Auto-reconnect after 3 seconds
                    try? await Task.sleep(for: .seconds(3))
                    self?.connect()
                }
            }
        }
    }

    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else { return }

        switch type {
        // ── Demo Remote Control ──
        case "demo_inject":
            let action = json["action"] as? String ?? ""
            print("[demo_inject] received action: \(action)")
            DispatchQueue.main.async { [weak self] in
                guard let appState = self?.appState else { return }
                switch action {
                case "send_chat":
                    let content = json["content"] as? String ?? ""
                    if !content.isEmpty {
                        appState.sendMessage(content)
                        // Immediately flush — don't wait for 8s merge buffer
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                            appState.flushMergedMessages()
                        }
                    }
                case "switch_persona":
                    let personaId = json["persona_id"] as? String ?? ""
                    if !personaId.isEmpty {
                        // Reset session so backend creates fresh agent for new persona
                        // Do NOT disconnect/reconnect WS — it causes inject to hit dead connections
                        self?.sessionId = nil
                        appState.selectPersona(personaId)
                        print("[demo_inject] switched persona to \(personaId), sessionId reset")
                    }
                case "scenario":
                    let scenarioId = json["scenario_id"] as? String ?? ""
                    if !scenarioId.isEmpty {
                        self?.sendDemoScenario(scenarioId: scenarioId)
                    }
                case "time_jump":
                    let hours = json["hours"] as? Double ?? 0
                    if hours > 0 {
                        self?.sendDemoTimeJump(hours: hours)
                    }
                case "inject_memory":
                    let content = json["content"] as? String ?? ""
                    let category = json["category"] as? String ?? "preference"
                    if !content.isEmpty {
                        self?.sendDemoInjectMemory(content: content, category: category)
                        // Push to AppState so capsules can light up
                        appState.demoInjectedMemoryKeys.append(content)
                        print("[demo_inject] memory capsule → \(content)")
                    }
                case "switch_tab":
                    let tab = json["tab"] as? Int ?? 1
                    appState.demoActMode = max(1, min(4, tab))
                    print("[demo_inject] switched tab to \(tab)")
                case "set_title":
                    let title = json["content"] as? String ?? ""
                    appState.demoTitle = title
                    print("[demo_inject] title → \(title)")
                default:
                    print("[demo_inject] unknown action: \(action)")
                }
            }

        case "chat_start":
            sessionId = json["session_id"] as? String
            streamingContent = ""
            appState?.isTyping = true

            // If this chat_start was sent by an external source (demo script),
            // add the user message bubble so it shows in the UI chat
            if let userContent = json["user_content"] as? String, !userContent.isEmpty {
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

        case "chat_chunk":
            if let chunk = json["content"] as? String {
                streamingContent += chunk
                updateStreamingMessage()
            }

        case "chat_end":
            appState?.isTyping = false
            let reply = json["reply"] as? String ?? streamingContent
            let modality = json["modality"] as? String ?? "文字"

            // Parse engine status for mood system
            if let raw = json["relationship"] {
                print("[chat_end] relationship raw: \(raw)")
            } else {
                print("[chat_end] ⚠️ no 'relationship' key in json. Keys: \(json.keys.sorted())")
            }
            if let pm = json["personal_memories"] {
                print("[chat_end] personal_memories: \(pm)")
            }
            let engineStatus = parseEngineStatus(json)
            let imageURL = json["image_url"] as? String

            // Finalize the assistant message
            finalizeMessage(reply: reply, modality: modality, imageURL: imageURL, engineStatus: engineStatus)

            // Update mood from engine status
            if let status = engineStatus {
                let newMood = MoodEngine.computeMood(from: status)
                appState?.currentMood = newMood

                // Per-turn signals for frequency indicator
                let valence = status.relationship?.valence ?? 0.0
                let reward = json["last_reward"] as? Double ?? 0.0
                let temp = status.temperature ?? 0.0
                appState?.valence = valence
                appState?.lastReward = reward
                appState?.emotionTemperature = temp

                // Crystal detection
                if let memories = json["personal_memories"] as? Int {
                    if memories > (appState?.crystalCount ?? 0) {
                        print("[crystal] ✨ new crystal! \(appState?.crystalCount ?? 0) → \(memories)")
                    }
                    appState?.crystalCount = memories
                }

                // Developer mode: update engine debug visualization
                if var debugJson = json["debug"] as? [String: Any] {
                    // Enrich debug dict with fields that live in the main json
                    if let tc = json["turn_count"] as? Int  { debugJson["turn_count"]  = tc }
                    if let rw = json["last_reward"] as? Double { debugJson["reward"]   = rw }
                    appState?.engineDebug.update(from: debugJson)
                    // ── Verify: print key values so we can compare with backend logs ──
                    let sigs = debugJson["signals"] as? [String: Any] ?? [:]
                    let drives = debugJson["drive_state"] as? [String: Any] ?? [:]
                    let mono = (debugJson["monologue"] as? String ?? "").prefix(50)
                    let age  = debugJson["age"] as? Int ?? -1
                    print("[debug] ✅ turn=\(json["turn_count"] ?? "?") age=\(age)")
                    print("[debug]  signals: dir=\(sigs["directness"] ?? "?") vul=\(sigs["vulnerability"] ?? "?") play=\(sigs["playfulness"] ?? "?") warm=\(sigs["warmth"] ?? "?")")
                    print("[debug]  drives:  conn=\(drives["connection"] ?? "?") nov=\(drives["novelty"] ?? "?") expr=\(drives["expression"] ?? "?")")
                    print("[debug]  monologue: \(mono)")

                    // ── Demo: sync demoSnapshot from chat debug data ──
                    if appState?.demoMode == true {
                        let frust = debugJson["frustration"] as? [String: Any] ?? [:]
                        let totalF = debugJson["total_frustration"]
                        print("[demo] frustration keys=\(frust.keys.sorted()) total=\(totalF ?? "nil")")
                        if let snapshot = DemoEngineSnapshot.from(debugJson) {
                            appState?.demoSnapshot = snapshot
                            print("[demo] ✅ demoSnapshot updated: temp=\(snapshot.temperature) frust=\(snapshot.totalFrustration)")
                        } else {
                            // Fallback: build minimal snapshot from main json fields
                            let driveState = json["drive_state"] as? [String: Double] ?? [:]
                            let frustScalar = json["frustration"] as? Double ?? 0
                            let tempVal = json["temperature"] as? Double ?? 0
                            if !driveState.isEmpty {
                                appState?.demoSnapshot = DemoEngineSnapshot(
                                    driveState: driveState,
                                    driveBaseline: json["drive_baseline"] as? [String: Double] ?? [:],
                                    frustration: [:],
                                    temperature: tempVal,
                                    totalFrustration: frustScalar
                                )
                                print("[demo] ⚠️ demoSnapshot fallback: temp=\(tempVal) frust=\(frustScalar)")
                            } else {
                                print("[demo] ❌ demoSnapshot parse failed, debugJson keys: \(debugJson.keys.sorted())")
                            }
                        }
                    }
                }

                print("[mood] valence=\(valence) reward=\(reward) temp=\(temp) → \(newMood)")
            }

        case "silence":
            // Persona chose not to reply — dismiss typing bubble, show nothing
            appState?.isTyping = false
            streamingContent = ""
            // Remove any streaming placeholder that was created during Express
            if let idx = appState?.messages.lastIndex(where: { $0.id == "streaming_current" }) {
                appState?.messages.remove(at: idx)
            }
            print("[silence] 🤫 persona chose silence")

        case "proactive":
            let content = json["content"] as? String ?? ""
            let modality = json["modality"] as? String ?? "文字"
            let msg = ChatMessage(
                role: .assistant,
                content: content,
                modality: modality
            )
            appState?.messages.append(msg)

            // Send native notification
            NotificationService.shared.sendNotification(
                title: appState?.selectedPersona?.name ?? "OpenHer",
                body: content
            )

        case "error":
            let errContent = json["content"] as? String ?? "Unknown error"
            print("[WS] Error: \(errContent)")
            appState?.isTyping = false

        case "tts_audio":
            // Decode base64 audio and attach to last assistant message
            if let audioBase64 = json["audio"] as? String,
               let audioData = Data(base64Encoded: audioBase64) {
                let format = json["format"] as? String ?? "wav"
                print("[WS] tts_audio received: \(audioData.count) bytes (\(format))")
                // Find the last assistant message and attach audio
                if let idx = appState?.messages.lastIndex(where: { $0.role == .assistant }) {
                    appState?.messages[idx].audioData = audioData
                }
            }

        case "persona_switched":
            let personaName = json["persona"] as? String ?? "Unknown"
            sessionId = json["session_id"] as? String
            print("[WS] Persona switched to: \(personaName)")

        case "demo_state":
            if let snapshot = DemoEngineSnapshot.from(json) {
                appState?.demoSnapshot = snapshot
                print("[demo] state updated: temp=\(snapshot.temperature), frust=\(snapshot.totalFrustration)")
            }

        case "demo_presets":
            if let presetsRaw = json["presets"] as? [[String: String]] {
                appState?.demoPresets = presetsRaw.compactMap { dict in
                    guard let label = dict["label"], let message = dict["message"] else { return nil }
                    return DemoPreset(label: label, message: message)
                }
            }
            if let scenariosRaw = json["scenarios"] as? [String: [String: Any]] {
                var scenarios: [String: DemoScenario] = [:]
                for (key, val) in scenariosRaw {
                    scenarios[key] = DemoScenario(
                        label: val["label"] as? String ?? key,
                        description: val["description"] as? String ?? "",
                        timeJumpHours: val["time_jump_hours"] as? Double,
                        inject: val["inject"] as? [String: [String: Double]]
                    )
                }
                appState?.demoScenarios = scenarios
            }
            print("[demo] loaded \(appState?.demoPresets.count ?? 0) presets, \(appState?.demoScenarios.count ?? 0) scenarios")

        default:
            break
        }
    }

    // MARK: - Streaming helpers

    private func updateStreamingMessage() {
        guard let appState = appState else { return }

        let streamingId = "streaming_current"
        if let idx = appState.messages.lastIndex(where: { $0.id == streamingId }) {
            appState.messages[idx].content = streamingContent
        } else {
            let msg = ChatMessage(
                id: streamingId,
                role: .assistant,
                content: streamingContent,
                modality: "文字"
            )
            appState.messages.append(msg)
        }
    }

    private func finalizeMessage(reply: String, modality: String, imageURL: String? = nil, engineStatus: EngineStatus?) {
        guard let appState = appState else { return }

        let streamingId = "streaming_current"
        if let idx = appState.messages.lastIndex(where: { $0.id == streamingId }) {
            appState.messages[idx] = ChatMessage(
                id: UUID().uuidString,
                role: .assistant,
                content: reply,
                modality: modality,
                imageURL: imageURL,
                engineStatus: engineStatus
            )
        } else {
            let msg = ChatMessage(
                role: .assistant,
                content: reply,
                modality: modality,
                imageURL: imageURL,
                engineStatus: engineStatus
            )
            appState.messages.append(msg)
        }
        streamingContent = ""
    }

    // MARK: - Engine status parsing

    private func parseEngineStatus(_ json: [String: Any]) -> EngineStatus? {
        let dominantDrive = json["dominant_drive"] as? String
        let temperature = json["temperature"] as? Double
        let frustration = json["frustration"] as? Double
        let modality = json["modality"] as? String
        let turnCount = json["turn_count"] as? Int
        let driveState = json["drive_state"] as? [String: Double]

        var relationship: RelationshipState? = nil
        if let rel = json["relationship"] as? [String: Any] {
            relationship = RelationshipState(
                depth: rel["depth"] as? Double,
                trust: rel["trust"] as? Double,
                valence: rel["valence"] as? Double
            )
        }

        return EngineStatus(
            dominantDrive: dominantDrive,
            temperature: temperature,
            frustration: frustration,
            modality: modality,
            turnCount: turnCount,
            relationship: relationship,
            driveState: driveState
        )
    }
}
