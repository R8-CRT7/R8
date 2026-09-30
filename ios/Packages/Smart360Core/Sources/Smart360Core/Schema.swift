import Foundation

public let topics = ["Vorfahrt", "Verkehrszeichen", "Geschwindigkeit", "Abstand", "Überholen", "Verhalten",
                     "Gefahrenlehre", "Technik", "Umwelt", "Recht", "Sonstiges"]

/// Structured model output. On iOS the model also extracts question + answer texts from the
/// screenshot, because the layout of the phone app is not calibrated.
public struct SolveResponse: Codable, Equatable, Sendable {
    public var question: String
    public var answerTexts: [String]
    public var answers: [Int]
    public var numberAnswer: String?
    public var confidence: Double
    public var reason: String
    public var uncertain: Bool
    public var topic: String

    enum CodingKeys: String, CodingKey {
        case question, answers, confidence, reason, uncertain, topic
        case answerTexts = "answer_texts"
        case numberAnswer = "number_answer"
    }

    public init(question: String, answerTexts: [String], answers: [Int], numberAnswer: String?, confidence: Double,
                reason: String, uncertain: Bool, topic: String) {
        self.question = question
        self.answerTexts = answerTexts
        self.answers = answers
        self.numberAnswer = numberAnswer
        self.confidence = confidence
        self.reason = reason
        self.uncertain = uncertain
        self.topic = topic
    }
}

public enum SchemaError: Error, Equatable, LocalizedError {
    case invalidJSON(String)
    case violation(String)

    public var errorDescription: String? {
        switch self {
        case .invalidJSON(let m): return "Invalid JSON from AI: \(m)"
        case .violation(let m): return "AI response rejected: \(m)"
        }
    }
}

public enum SolveSchema {
    /// JSON Schema used for provider-native structured outputs.
    public static var jsonSchema: [String: Any] {
        [
        "type": "object",
        "properties": [
            "question": ["type": "string", "description": "The question text as shown"],
            "answer_texts": ["type": "array", "items": ["type": "string"],
                             "description": "Answer options top to bottom (empty for number questions)"],
            "answers": ["type": "array", "items": ["type": "integer"],
                        "description": "1-based indices of ALL correct answers"],
            "number_answer": ["anyOf": [["type": "string"], ["type": "null"]]],
            "confidence": ["type": "number"],
            "reason": ["type": "string"],
            "uncertain": ["type": "boolean"],
            "topic": ["type": "string", "enum": topics],
        ],
        "required": ["question", "answer_texts", "answers", "number_answer", "confidence", "reason", "uncertain",
                     "topic"],
        "additionalProperties": false,
        ]
    }

    /// Decode + validate. Never trusts free text.
    public static func parse(_ data: Data) throws -> SolveResponse {
        let r: SolveResponse
        do {
            r = try JSONDecoder().decode(SolveResponse.self, from: data)
        } catch {
            throw SchemaError.invalidJSON(String(describing: error).prefix(160).description)
        }
        return try validate(r)
    }

    public static func validate(_ input: SolveResponse) throws -> SolveResponse {
        var r = input
        guard (0...1).contains(r.confidence) else { throw SchemaError.violation("confidence out of range") }
        guard !r.reason.isEmpty, r.reason.count <= 600 else { throw SchemaError.violation("reason length") }
        guard r.answers.allSatisfy({ $0 >= 1 }), Set(r.answers).count == r.answers.count else {
            throw SchemaError.violation("invalid answer indices")
        }
        if !r.answerTexts.isEmpty, r.answers.contains(where: { $0 > r.answerTexts.count }) {
            throw SchemaError.violation("answer index out of range")
        }
        if let n = r.numberAnswer?.replacingOccurrences(of: " ", with: ""), !n.isEmpty {
            guard n.count <= 12, n.allSatisfy({ $0.isNumber || $0 == "," || $0 == "." }) else {
                throw SchemaError.violation("number_answer must be numeric")
            }
            r.numberAnswer = n
        } else {
            r.numberAnswer = nil
        }
        if r.answers.isEmpty && r.numberAnswer == nil && !r.uncertain {
            throw SchemaError.violation("no answer selected")
        }
        if !topics.contains(r.topic) { r.topic = "Sonstiges" }
        r.answers.sort()
        return r
    }
}
