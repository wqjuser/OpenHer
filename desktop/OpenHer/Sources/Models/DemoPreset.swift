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

    /// Convert [String: Any] (with NSNumber values) to [String: Double]
    private static func toDoubles(_ dict: Any?) -> [String: Double]? {
        guard let raw = dict as? [String: Any] else { return nil }
        var result: [String: Double] = [:]
        for (key, val) in raw {
            if let n = val as? NSNumber {
                result[key] = n.doubleValue
            } else if let d = val as? Double {
                result[key] = d
            }
        }
        return result.isEmpty ? nil : result
    }

    static func from(_ json: [String: Any]) -> DemoEngineSnapshot? {
        guard let driveState = toDoubles(json["drive_state"]),
              let frustration = toDoubles(json["frustration"]) else {
            return nil
        }
        let temp: Double
        if let n = json["temperature"] as? NSNumber { temp = n.doubleValue }
        else if let d = json["temperature"] as? Double { temp = d }
        else { temp = 0 }

        let totalFrust: Double
        if let n = json["total_frustration"] as? NSNumber { totalFrust = n.doubleValue }
        else if let d = json["total_frustration"] as? Double { totalFrust = d }
        else { totalFrust = 0 }

        return DemoEngineSnapshot(
            driveState: driveState,
            driveBaseline: toDoubles(json["drive_baseline"]) ?? [:],
            frustration: frustration,
            temperature: temp,
            totalFrustration: totalFrust
        )
    }
}
