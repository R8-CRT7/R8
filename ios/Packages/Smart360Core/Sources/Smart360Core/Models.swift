import Foundation

/// Canonical text form for hashing and similarity (mirrors the Windows implementation).
public enum TextNormalizer {
    public static func normalize(_ text: String) -> String {
        var t = text.precomposedStringWithCompatibilityMapping.lowercased()
        t = t.replacingOccurrences(of: "ß", with: "ss")
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "%/.,+-"))
        t = String(t.unicodeScalars.map { allowed.contains($0) ? Character($0) : " " })
        return t.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
    }

    /// All numbers in order ("50 km/h" vs "70 km/h" must never be confused).
    public static func numbers(_ text: String) -> [String] {
        var out: [String] = []
        var current = ""
        for ch in text {
            if ch.isNumber || ((ch == "," || ch == ".") && !current.isEmpty) {
                current.append(ch == "," ? "." : ch)
            } else if !current.isEmpty {
                out.append(current.trimmingCharacters(in: CharacterSet(charactersIn: ".")))
                current = ""
            }
        }
        if !current.isEmpty { out.append(current.trimmingCharacters(in: CharacterSet(charactersIn: "."))) }
        return out
    }
}

public struct AnswerOption: Codable, Hashable, Sendable {
    public var index: Int
    public var text: String
    public init(index: Int, text: String) {
        self.index = index
        self.text = text
    }
}

public struct Question: Codable, Hashable, Sendable, Identifiable {
    public var text: String
    public var answers: [AnswerOption]
    public var isNumberQuestion: Bool
    public var ocrConfidence: Double
    public var imageHash: UInt64?

    public init(text: String, answers: [AnswerOption], isNumberQuestion: Bool = false,
                ocrConfidence: Double = 1, imageHash: UInt64? = nil) {
        self.text = text
        self.answers = answers
        self.isNumberQuestion = isNumberQuestion
        self.ocrConfidence = ocrConfidence
        self.imageHash = imageHash
    }

    public var normalizedText: String { TextNormalizer.normalize(text) }
    public var normalizedAnswers: [String] { answers.map { TextNormalizer.normalize($0.text) } }

    /// Stable identity of the visible question (FNV-1a over normalized content).
    public var id: String {
        var h: UInt64 = 0xcbf29ce484222325
        func feed(_ s: String) {
            for b in s.utf8 { h = (h ^ UInt64(b)) &* 0x100000001b3 }
            h = (h ^ 0x1f) &* 0x100000001b3
        }
        feed(normalizedText)
        normalizedAnswers.forEach(feed)
        feed(isNumberQuestion ? "number" : "choice")
        return String(h, radix: 16)
    }
}

public enum PredictionSource: String, Codable, Sendable { case ai, cache, demo }

public struct Prediction: Codable, Hashable, Sendable {
    public var questionID: String
    public var answers: [Int]
    public var numberAnswer: String?
    public var modelConfidence: Double
    public var confidence: Double
    public var reason: String
    public var uncertain: Bool
    public var topic: String
    public var source: PredictionSource
    public var model: String
    public var latencyMs: Double

    public init(questionID: String, answers: [Int], numberAnswer: String? = nil, modelConfidence: Double,
                confidence: Double, reason: String, uncertain: Bool, topic: String, source: PredictionSource,
                model: String, latencyMs: Double = 0) {
        self.questionID = questionID
        self.answers = answers
        self.numberAnswer = numberAnswer
        self.modelConfidence = modelConfidence
        self.confidence = confidence
        self.reason = reason
        self.uncertain = uncertain
        self.topic = topic
        self.source = source
        self.model = model
        self.latencyMs = latencyMs
    }

    public var display: String {
        if let n = numberAnswer, answers.isEmpty { return n }
        return answers.isEmpty ? "?" : answers.map(String.init).joined(separator: " + ")
    }
}

public enum Decision: String, Codable, Sendable { case accepted, rejected, skipped }

public struct HistoryEntry: Codable, Hashable, Sendable, Identifiable {
    public var id: UUID
    public var questionText: String
    public var answers: [String]
    public var recommended: [Int]
    public var confidence: Double
    public var decision: Decision
    public var topic: String
    public var source: PredictionSource
    public var processingMs: Double
    public var date: Date
    public var uncertain: Bool

    public init(id: UUID = UUID(), questionText: String, answers: [String], recommended: [Int], confidence: Double,
                decision: Decision, topic: String, source: PredictionSource, processingMs: Double,
                date: Date = Date(), uncertain: Bool) {
        self.id = id
        self.questionText = questionText
        self.answers = answers
        self.recommended = recommended
        self.confidence = confidence
        self.decision = decision
        self.topic = topic
        self.source = source
        self.processingMs = processingMs
        self.date = date
        self.uncertain = uncertain
    }
}
