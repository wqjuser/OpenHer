import Foundation

/// A preset message for demo quick-fire sending.
struct DemoPreset: Identifiable, Codable {
    var id: String { label }
    let label: String
    let message: String
}

/// A demo scenario that injects engine state.
struct DemoScenario: Identifiable, Codable {
    var id: String { label }
    let label: String
    let description: String
    let timeJumpHours: Double?
    let inject: [String: [String: Double]]?

    enum CodingKeys: String, CodingKey {
        case label, description
        case timeJumpHours = "time_jump_hours"
        case inject
    }
}

/// Snapshot of engine state returned by demo commands.
struct DemoEngineSnapshot {
    let driveState: [String: Double]
    let driveBaseline: [String: Double]
    let frustration: [String: Double]
    let temperature: Double
    let totalFrustration: Double

    static func from(_ json: [String: Any]) -> DemoEngineSnapshot? {
        guard let driveState = json["drive_state"] as? [String: Double],
              let frustration = json["frustration"] as? [String: Double] else {
            return nil
        }
        return DemoEngineSnapshot(
            driveState: driveState,
            driveBaseline: json["drive_baseline"] as? [String: Double] ?? [:],
            frustration: frustration,
            temperature: json["temperature"] as? Double ?? 0,
            totalFrustration: json["total_frustration"] as? Double ?? 0
        )
    }
}
