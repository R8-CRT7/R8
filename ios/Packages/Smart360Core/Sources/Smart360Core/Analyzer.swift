import Foundation

/// One OCR line with a normalized bounding box (0...1, origin top-left).
public struct OCRLine: Codable, Sendable, Hashable {
    public var text: String
    public var x: Double
    public var y: Double
    public var w: Double
    public var h: Double
    public var confidence: Double

    public init(text: String, x: Double, y: Double, w: Double, h: Double, confidence: Double) {
        self.text = text
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.confidence = confidence
    }
}

/// Best-effort question parser for phone screenshots. Used for cache lookups and change
/// detection; the AI extraction stays authoritative for display.
public enum ScreenQuestionParser {
    static let stopWords = ["weiter", "zurück", "abgeben", "prüfen", "auswerten", "nächste", "überspringen"]

    public static func parse(_ lines: [OCRLine]) -> Question? {
        let body = lines
            .filter { $0.y > 0.06 && $0.y < 0.95 }  // drop status bar / home indicator zone
            .filter { !isNoise($0.text) }
            .sorted { $0.y < $1.y }
        guard let qEnd = body.firstIndex(where: { $0.text.trimmingCharacters(in: .whitespaces).hasSuffix("?") })
        else { return nil }
        // question = contiguous block ending at the "?" line
        var start = qEnd
        while start > 0, body[start].y - (body[start - 1].y + body[start - 1].h) < body[start].h * 0.9 { start -= 1 }
        let qText = body[start...qEnd].map(\.text).joined(separator: " ")
        // answers = following blocks separated by vertical gaps, until a button-like word
        var answers: [String] = []
        var current: [OCRLine] = []
        for line in body[(qEnd + 1)...] {
            let lower = line.text.lowercased()
            if stopWords.contains(where: { lower.hasPrefix($0) }) && line.text.count < 20 { break }
            if let last = current.last, line.y - (last.y + last.h) > last.h * 0.9 {
                answers.append(current.map(\.text).joined(separator: " "))
                current = []
            }
            current.append(line)
        }
        if !current.isEmpty { answers.append(current.map(\.text).joined(separator: " ")) }
        answers = answers.map(cleanAnswer).filter { !$0.isEmpty }
        let conf = body[start...qEnd].map(\.confidence).reduce(0, +) / Double(qEnd - start + 1)
        let isNumber = answers.count < 2 && qText.lowercased().contains("zahl")
        guard isNumber || (2...5).contains(answers.count) else { return nil }
        return Question(text: qText, answers: answers.enumerated().map { AnswerOption(index: $0.offset + 1, text: $0.element) },
                        isNumberQuestion: isNumber, ocrConfidence: conf)
    }

    static func isNoise(_ s: String) -> Bool {
        let t = s.trimmingCharacters(in: .whitespaces)
        if t.count <= 2 { return true }
        if t.range(of: #"^\d{1,2}:\d{2}$"#, options: .regularExpression) != nil { return true }  // clock
        if t.range(of: #"^\d{1,3}\s?%$"#, options: .regularExpression) != nil { return true }  // battery
        return false
    }

    static func cleanAnswer(_ s: String) -> String {
        s.replacingOccurrences(of: #"^[\[\]\(\)□☐☑✓✔|_ ]+"#, with: "", options: .regularExpression)
            .trimmingCharacters(in: .whitespaces)
    }
}

public struct AnalysisOutcome: Sendable {
    public var question: Question
    public var prediction: Prediction
}

/// Cache first, AI second; composite confidence; stores confident answers.
public final class Analyzer: @unchecked Sendable {
    public let solver: ResilientSolver?
    public let cache: QuestionCache
    public var threshold: Double
    public var costSaver: Bool

    public init(solver: ResilientSolver?, cache: QuestionCache, threshold: Double = 0.75, costSaver: Bool = true) {
        self.solver = solver
        self.cache = cache
        self.threshold = threshold
        self.costSaver = costSaver
    }

    public func analyze(lines: [OCRLine], imageJPEG: Data?, forceFresh: Bool = false) async throws -> AnalysisOutcome {
        let parsed = ScreenQuestionParser.parse(lines)
        let ocrConf = lines.isEmpty ? 0 : lines.map(\.confidence).reduce(0, +) / Double(lines.count)
        if !forceFresh, costSaver, let q = parsed, let hit = cache.lookup(q) {
            let c = ConfidenceEngine.composite(
                ConfidenceInputs(model: hit.confidence, ocr: q.ocrConfidence, cacheSimilarity: hit.similarity),
                manualThreshold: threshold)
            let p = Prediction(questionID: q.id, answers: hit.answers, numberAnswer: hit.numberAnswer,
                               modelConfidence: hit.confidence, confidence: c.value, reason: hit.reason,
                               uncertain: c.value < threshold, topic: hit.topic, source: .cache, model: hit.model)
            return AnalysisOutcome(question: q, prediction: p)
        }
        guard let solver else { throw ProviderError.missingKey }
        let ocrText = lines.sorted { $0.y < $1.y }.map(\.text).joined(separator: "\n")
        let result = try await solver.solve(SolveRequest(ocrText: ocrText, imageJPEG: imageJPEG))
        let r = result.response
        let q = Question(text: r.question.isEmpty ? (parsed?.text ?? "") : r.question,
                         answers: r.answerTexts.enumerated().map { AnswerOption(index: $0.offset + 1, text: $0.element) },
                         isNumberQuestion: r.numberAnswer != nil && r.answers.isEmpty,
                         ocrConfidence: parsed?.ocrConfidence ?? ocrConf)
        let layout = (2...5).contains(q.answers.count) || q.isNumberQuestion ? 1.0 : 0.4
        let c = ConfidenceEngine.composite(
            ConfidenceInputs(model: r.confidence, ocr: max(0.6, q.ocrConfidence), layout: layout,
                             modelUncertain: r.uncertain),
            manualThreshold: threshold)
        let p = Prediction(questionID: q.id, answers: r.answers, numberAnswer: r.numberAnswer,
                           modelConfidence: r.confidence, confidence: c.value, reason: r.reason,
                           uncertain: r.uncertain || c.value < threshold, topic: r.topic, source: .ai,
                           model: result.model, latencyMs: result.latencyMs)
        if !p.uncertain, !q.text.isEmpty {
            cache.store(q, correct: r.answers, numberAnswer: r.numberAnswer, confidence: r.confidence,
                        reason: r.reason, topic: r.topic, model: result.model)
        }
        return AnalysisOutcome(question: q, prediction: p)
    }
}
