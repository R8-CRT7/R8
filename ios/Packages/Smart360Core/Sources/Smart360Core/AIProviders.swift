import Foundation

public struct SolveRequest: Sendable {
    public var ocrText: String
    public var imageJPEG: Data?
    public init(ocrText: String, imageJPEG: Data?) {
        self.ocrText = ocrText
        self.imageJPEG = imageJPEG
    }
}

public struct SolveResult: Sendable {
    public var response: SolveResponse
    public var model: String
    public var provider: String
    public var latencyMs: Double
    public var inputTokens: Int
    public var outputTokens: Int
}

public enum ProviderError: Error, LocalizedError, Equatable {
    case missingKey
    case auth
    case rateLimited(retryAfter: Double?)
    case timeout
    case network(String)
    case server(Int)
    case badRequest(String)
    case refusal
    case invalid(String)

    public var retryable: Bool {
        switch self {
        case .rateLimited, .timeout, .network, .invalid: return true
        case .server(let code): return code >= 500
        default: return false
        }
    }

    public var errorDescription: String? {
        switch self {
        case .missingKey: return "API key missing - add it in Settings."
        case .auth: return "API key rejected."
        case .rateLimited: return "Rate limited - retrying."
        case .timeout: return "The AI took too long."
        case .network(let m): return "Network error: \(m)"
        case .server(let c): return "AI server error \(c)."
        case .badRequest(let m): return "Request rejected: \(m)"
        case .refusal: return "The model declined this request."
        case .invalid(let m): return m
        }
    }
}

public protocol AIProvider: Sendable {
    var id: String { get }
    var model: String { get }
    func solve(_ req: SolveRequest) async throws -> SolveResult
}

public let systemPrompt = """
Du bist Fachlehrer für die deutsche Führerschein-Theorieprüfung (Klasse B). Du erhältst ein Bildschirmfoto \
einer Lernsoftware und den per OCR erkannten Text. Lies Frage und Antwortmöglichkeiten (von oben nach unten) \
aus dem Bild ab. Es können eine oder mehrere Antworten richtig sein: gib ALLE richtigen als 1-basierte Nummern \
an. Bei Zahlenfragen: number_answer setzen, answers leer. Nutze das Situationsbild aktiv. reason: höchstens zwei \
kurze Sätze auf Deutsch, die die Regel erklären. uncertain=true, wenn Frage/Antworten unvollständig oder \
unleserlich sind oder du unsicher bist. Antworte nur im vorgegebenen JSON-Format.
"""

func userText(_ req: SolveRequest) -> String {
    "OCR-Text des Bildschirms (kann Fehler enthalten):\n\(req.ocrText.prefix(4000))"
}

/// Shared HTTP helper with status-code mapping.
enum HTTP {
    static func post(_ url: URL, headers: [String: String], body: [String: Any], timeout: TimeInterval,
                     session: URLSession) async throws -> (Data, HTTPURLResponse) {
        var r = URLRequest(url: url, timeoutInterval: timeout)
        r.httpMethod = "POST"
        r.setValue("application/json", forHTTPHeaderField: "content-type")
        headers.forEach { r.setValue($1, forHTTPHeaderField: $0) }
        r.httpBody = try JSONSerialization.data(withJSONObject: body)
        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await session.data(for: r)
        } catch let e as URLError where e.code == .timedOut {
            throw ProviderError.timeout
        } catch {
            throw ProviderError.network(error.localizedDescription)
        }
        guard let http = resp as? HTTPURLResponse else { throw ProviderError.network("no HTTP response") }
        switch http.statusCode {
        case 200..<300: return (data, http)
        case 401, 403: throw ProviderError.auth
        case 429: throw ProviderError.rateLimited(retryAfter: http.value(forHTTPHeaderField: "retry-after").flatMap { Double($0) })
        case 400, 404, 413, 422:
            throw ProviderError.badRequest(String(data: data.prefix(300), encoding: .utf8) ?? "\(http.statusCode)")
        default: throw ProviderError.server(http.statusCode)
        }
    }

    static func json(_ data: Data) throws -> [String: Any] {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw ProviderError.invalid("response is not JSON")
        }
        return obj
    }
}

/// Anthropic Messages API (raw HTTP; there is no official Swift SDK) with structured outputs.
public struct AnthropicProvider: AIProvider {
    public let id = "anthropic"
    public let model: String
    let apiKey: String
    let timeout: TimeInterval
    let session: URLSession

    public init(apiKey: String, model: String = "claude-opus-5-5", timeout: TimeInterval = 30,
                session: URLSession = .shared) {
        self.apiKey = apiKey
        self.model = model
        self.timeout = timeout
        self.session = session
    }

    public func requestBody(_ req: SolveRequest) -> [String: Any] {
        var content: [[String: Any]] = []
        if let img = req.imageJPEG {
            content.append(["type": "image", "source": ["type": "base64", "media_type": "image/jpeg",
                                                        "data": img.base64EncodedString()]])
        }
        content.append(["type": "text", "text": userText(req)])
        var outputConfig: [String: Any] = ["format": ["type": "json_schema", "schema": SolveSchema.jsonSchema]]
        if model != "claude-haiku-4-5" { outputConfig["effort"] = "low" }
        var body: [String: Any] = [
            "model": model, "max_tokens": 4000, "system": systemPrompt,
            "messages": [["role": "user", "content": content]], "output_config": outputConfig,
        ]
        if model == "claude-opus-5-5" || model == "claude-sonnet-5-5" { body["fallbacks"] = "default" }
        return body
    }

    public func solve(_ req: SolveRequest) async throws -> SolveResult {
        guard !apiKey.isEmpty else { throw ProviderError.missingKey }
        var headers = ["x-api-key": apiKey, "anthropic-version": "2023-06-01"]
        if model == "claude-opus-5-5" || model == "claude-sonnet-5-5" {
            headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
        }
        let t0 = Date()
        let (data, _) = try await HTTP.post(URL(string: "https://api.anthropic.com/v1/messages")!, headers: headers,
                                            body: requestBody(req), timeout: timeout, session: session)
        let obj = try HTTP.json(data)
        if (obj["stop_reason"] as? String) == "refusal" { throw ProviderError.refusal }
        let blocks = obj["content"] as? [[String: Any]] ?? []
        guard let text = blocks.first(where: { $0["type"] as? String == "text" })?["text"] as? String else {
            throw ProviderError.invalid("no text block")
        }
        let parsed = try parseOrThrow(text)
        let usage = obj["usage"] as? [String: Any]
        return SolveResult(response: parsed, model: (obj["model"] as? String) ?? model, provider: id,
                           latencyMs: Date().timeIntervalSince(t0) * 1000,
                           inputTokens: (usage?["input_tokens"] as? Int) ?? 0,
                           outputTokens: (usage?["output_tokens"] as? Int) ?? 0)
    }
}

/// OpenAI Chat Completions with strict json_schema (not live-tested - see FINAL_STATUS).
public struct OpenAIProvider: AIProvider {
    public let id = "openai"
    public let model: String
    let apiKey: String
    let timeout: TimeInterval
    let session: URLSession

    public init(apiKey: String, model: String = "gpt-6-luna", timeout: TimeInterval = 30,
                session: URLSession = .shared) {
        self.apiKey = apiKey
        self.model = model
        self.timeout = timeout
        self.session = session
    }

    public func solve(_ req: SolveRequest) async throws -> SolveResult {
        guard !apiKey.isEmpty else { throw ProviderError.missingKey }
        var content: [[String: Any]] = [["type": "text", "text": userText(req)]]
        if let img = req.imageJPEG {
            content.append(["type": "image_url",
                            "image_url": ["url": "data:image/jpeg;base64," + img.base64EncodedString()]])
        }
        let body: [String: Any] = [
            "model": model,
            "messages": [["role": "system", "content": systemPrompt], ["role": "user", "content": content]],
            "response_format": ["type": "json_schema",
                                "json_schema": ["name": "solve_question", "schema": SolveSchema.jsonSchema,
                                                "strict": true]],
        ]
        let t0 = Date()
        let (data, _) = try await HTTP.post(URL(string: "https://api.openai.com/v1/chat/completions")!,
                                            headers: ["authorization": "Bearer \(apiKey)"], body: body,
                                            timeout: timeout, session: session)
        let obj = try HTTP.json(data)
        let msg = ((obj["choices"] as? [[String: Any]])?.first?["message"] as? [String: Any]) ?? [:]
        if msg["refusal"] is String { throw ProviderError.refusal }
        guard let text = msg["content"] as? String else { throw ProviderError.invalid("no content") }
        let usage = obj["usage"] as? [String: Any]
        return SolveResult(response: try parseOrThrow(text), model: model, provider: id,
                           latencyMs: Date().timeIntervalSince(t0) * 1000,
                           inputTokens: (usage?["prompt_tokens"] as? Int) ?? 0,
                           outputTokens: (usage?["completion_tokens"] as? Int) ?? 0)
    }
}

/// Google Gemini generateContent REST with a JSON response schema (not live-tested).
public struct GeminiProvider: AIProvider {
    public let id = "gemini"
    public let model: String
    let apiKey: String
    let timeout: TimeInterval
    let session: URLSession

    public init(apiKey: String, model: String = "gemini-3.8-flash", timeout: TimeInterval = 30,
                session: URLSession = .shared) {
        self.apiKey = apiKey
        self.model = model
        self.timeout = timeout
        self.session = session
    }

    public func solve(_ req: SolveRequest) async throws -> SolveResult {
        guard !apiKey.isEmpty else { throw ProviderError.missingKey }
        var parts: [[String: Any]] = []
        if let img = req.imageJPEG {
            parts.append(["inline_data": ["mime_type": "image/jpeg", "data": img.base64EncodedString()]])
        }
        parts.append(["text": userText(req)])
        let body: [String: Any] = [
            "contents": [["role": "user", "parts": parts]],
            "systemInstruction": ["parts": [["text": systemPrompt]]],
            "generationConfig": ["responseMimeType": "application/json",
                                 "responseJsonSchema": SolveSchema.jsonSchema],
        ]
        let url = URL(string: "https://generativelanguage.googleapis.com/v1beta/models/\(model):generateContent")!
        let t0 = Date()
        let (data, _) = try await HTTP.post(url, headers: ["x-goog-api-key": apiKey], body: body, timeout: timeout,
                                            session: session)
        let obj = try HTTP.json(data)
        let cand = (obj["candidates"] as? [[String: Any]])?.first
        let partsOut = (cand?["content"] as? [String: Any])?["parts"] as? [[String: Any]]
        guard let text = partsOut?.first?["text"] as? String else { throw ProviderError.invalid("no candidate") }
        let usage = obj["usageMetadata"] as? [String: Any]
        return SolveResult(response: try parseOrThrow(text), model: model, provider: id,
                           latencyMs: Date().timeIntervalSince(t0) * 1000,
                           inputTokens: (usage?["promptTokenCount"] as? Int) ?? 0,
                           outputTokens: (usage?["candidatesTokenCount"] as? Int) ?? 0)
    }
}

func parseOrThrow(_ text: String) throws -> SolveResponse {
    do {
        return try SolveSchema.parse(Data(text.utf8))
    } catch let e as SchemaError {
        throw ProviderError.invalid(e.localizedDescription)
    }
}

/// Retry with exponential backoff + jitter for retryable errors.
public struct ResilientSolver: Sendable {
    public let provider: any AIProvider
    public let maxRetries: Int
    public let baseDelay: Double

    public init(provider: any AIProvider, maxRetries: Int = 2, baseDelay: Double = 0.8) {
        self.provider = provider
        self.maxRetries = maxRetries
        self.baseDelay = baseDelay
    }

    public func solve(_ req: SolveRequest) async throws -> SolveResult {
        var attempt = 0
        while true {
            do {
                return try await provider.solve(req)
            } catch let e as ProviderError where e.retryable && attempt < maxRetries {
                var delay = baseDelay * pow(2, Double(attempt))
                if case .rateLimited(let ra?) = e { delay = ra }
                delay = min(delay, 20) * Double.random(in: 0.8...1.2)
                attempt += 1
                try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            }
        }
    }
}
