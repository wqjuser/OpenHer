import Foundation

/// REST API client for the OpenHer backend.
actor APIClient {
    let baseURL: String
    let apiToken: String

    init(baseURL: String, apiToken: String = "") {
        self.baseURL = baseURL.hasSuffix("/") ? String(baseURL.dropLast()) : baseURL
        self.apiToken = apiToken.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - Personas

    func fetchPersonas() async throws -> [Persona] {
        let data = try await get("/api/personas")
        let response = try JSONDecoder().decode(PersonasResponse.self, from: data)
        return response.personas
    }

    // MARK: - Chat History

    func fetchChatHistoryPairs(personaId: String, clientId: String, limit: Int = 50) async throws -> [ChatMessage] {
        let path = "/api/chat/history/\(personaId)?client_id=\(clientId)&limit=\(limit)"
        let data = try await get(path)

        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard let messagesArray = json?["messages"] as? [[String: Any]] else {
            return []
        }

        var result: [ChatMessage] = []
        for dict in messagesArray {
            guard let role = dict["role"] as? String,
                  let content = dict["content"] as? String else { continue }

            let msgId = dict["id"] as? Int ?? Int.random(in: 1...999999)
            let modality = dict["modality"] as? String ?? "文字"
            let imageURL = dict["image_url"] as? String

            result.append(ChatMessage(
                id: "h_\(msgId)",
                role: role == "user" ? .user : .assistant,
                content: content,
                modality: modality,
                imageURL: role == "assistant" ? imageURL : nil
            ))
        }
        return result
    }

    // MARK: - Status

    func checkStatus() async throws -> Bool {
        let data = try await get("/api/status")
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        return json?["status"] as? String == "running"
    }

    // MARK: - Avatar

    nonisolated func avatarURL(for personaId: String) -> URL? {
        // Use real face photo from idimage as avatar
        authenticatedURL(path: "/api/persona/\(personaId)/media/face")
    }

    // MARK: - Internals

    private func get(_ path: String) async throws -> Data {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }
        var request = URLRequest(url: url)
        if !apiToken.isEmpty {
            request.setValue("Bearer \(apiToken)", forHTTPHeaderField: "Authorization")
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              200..<300 ~= httpResponse.statusCode else {
            throw APIError.serverError((response as? HTTPURLResponse)?.statusCode ?? 0)
        }
        return data
    }

    nonisolated private func authenticatedURL(path: String) -> URL? {
        guard var components = URLComponents(string: "\(baseURL)\(path)") else { return nil }
        let token = apiToken.trimmingCharacters(in: .whitespacesAndNewlines)
        if !token.isEmpty {
            var items = components.queryItems ?? []
            items.append(URLQueryItem(name: "token", value: token))
            components.queryItems = items
        }
        return components.url
    }
}

private struct PersonasResponse: Codable {
    let personas: [Persona]
}

enum APIError: Error, LocalizedError {
    case invalidURL
    case serverError(Int)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL"
        case .serverError(let code): return "Server error (\(code))"
        }
    }
}
