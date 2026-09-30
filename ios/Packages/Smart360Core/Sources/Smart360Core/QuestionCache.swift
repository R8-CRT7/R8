import Foundation

/// Local question cache with the same safety rules as the Windows app:
/// same type, identical numbers, >=97 % text similarity without word insertions/deletions,
/// same answer set (1:1, order may differ) and compatible images. Answers are stored as TEXT
/// and re-mapped onto the current order.
public final class QuestionCache: @unchecked Sendable {
    public struct Entry: Codable, Sendable {
        public var text: String
        public var numbers: [String]
        public var answers: [String]
        public var correct: [String]
        public var numberAnswer: String?
        public var isNumberQuestion: Bool
        public var imageHash: UInt64?
        public var confidence: Double
        public var reason: String
        public var topic: String
        public var model: String
        public var created: Date
    }

    public struct Hit: Sendable {
        public var answers: [Int]
        public var numberAnswer: String?
        public var confidence: Double
        public var reason: String
        public var topic: String
        public var model: String
        public var similarity: Double
    }

    private let lock = NSLock()
    private var entries: [String: Entry] = [:]
    private let url: URL?
    public let maxEntries: Int
    public private(set) var recoveredFromCorruption = false

    public init(url: URL?, maxEntries: Int = 5000) {
        self.url = url
        self.maxEntries = maxEntries
        load()
    }

    public var count: Int { lock.lock(); defer { lock.unlock() }; return entries.count }

    private func load() {
        guard let url, FileManager.default.fileExists(atPath: url.path) else { return }
        do {
            let data = try Data(contentsOf: url)
            entries = try JSONDecoder().decode([String: Entry].self, from: data)
        } catch {
            // corrupted cache: move aside, start fresh
            let bad = url.appendingPathExtension("corrupt-\(Int(Date().timeIntervalSince1970))")
            try? FileManager.default.moveItem(at: url, to: bad)
            entries = [:]
            recoveredFromCorruption = true
        }
    }

    private func persist() {
        guard let url else { return }
        do {
            let data = try JSONEncoder().encode(entries)
            try data.write(to: url, options: [.atomic, .completeFileProtection])
        } catch {
            // cache is an optimisation only; failures are non-fatal
        }
    }

    public func store(_ q: Question, correct: [Int], numberAnswer: String?, confidence: Double, reason: String,
                      topic: String, model: String) {
        let texts = q.normalizedAnswers
        let correctTexts = correct.compactMap { $0 >= 1 && $0 <= texts.count ? texts[$0 - 1] : nil }
        guard correctTexts.count == correct.count || numberAnswer != nil else { return }
        let e = Entry(text: q.normalizedText, numbers: TextNormalizer.numbers(q.text), answers: texts,
                      correct: correctTexts, numberAnswer: numberAnswer, isNumberQuestion: q.isNumberQuestion,
                      imageHash: q.imageHash, confidence: confidence, reason: reason, topic: topic, model: model,
                      created: Date())
        lock.lock()
        entries[q.id] = e
        if entries.count > maxEntries,
           let oldest = entries.min(by: { $0.value.created < $1.value.created })?.key {
            entries.removeValue(forKey: oldest)
        }
        lock.unlock()
        persist()
    }

    public func clear() {
        lock.lock()
        entries.removeAll()
        lock.unlock()
        persist()
    }

    public func lookup(_ q: Question) -> Hit? {
        lock.lock(); defer { lock.unlock() }
        let candidates: [Entry] = entries[q.id].map { [$0] } ?? Array(entries.values)
        var best: Hit?
        for e in candidates {
            if let hit = match(q, e), hit.similarity > (best?.similarity ?? 0) { best = hit }
        }
        return best
    }

    private func match(_ q: Question, _ e: Entry) -> Hit? {
        guard e.isNumberQuestion == q.isNumberQuestion,
              TextNormalizer.numbers(q.text) == e.numbers,
              (q.imageHash == nil) == (e.imageHash == nil) else { return nil }
        if let a = q.imageHash, let b = e.imageHash, (a ^ b).nonzeroBitCount > 6 { return nil }
        let textSim = Similarity.ratio(q.normalizedText, e.text)
        guard textSim >= 0.97, Similarity.wordsCompatible(q.normalizedText, e.text) else { return nil }
        let current = q.normalizedAnswers
        guard current.count == e.answers.count else { return nil }
        var used = Set<Int>()
        var mapping: [Int: Int] = [:]  // entry index -> current index
        var minSim = textSim
        for (ri, rtext) in e.answers.enumerated() {
            var bestJ = -1
            var bestS = 0.0
            for (j, ctext) in current.enumerated() where !used.contains(j)
                && TextNormalizer.numbers(ctext) == TextNormalizer.numbers(rtext) {
                let s = Similarity.ratio(ctext, rtext)
                if s > bestS { bestJ = j; bestS = s }
            }
            guard bestJ >= 0, bestS >= 0.95 else { return nil }
            used.insert(bestJ)
            mapping[ri] = bestJ
            minSim = min(minSim, bestS)
        }
        var answers: [Int] = []
        for c in e.correct {
            guard let ri = e.answers.firstIndex(of: c), let cj = mapping[ri] else { return nil }
            answers.append(cj + 1)
        }
        if answers.isEmpty && e.numberAnswer == nil { return nil }
        return Hit(answers: answers.sorted(), numberAnswer: e.numberAnswer, confidence: e.confidence,
                   reason: e.reason, topic: e.topic, model: e.model, similarity: minSim)
    }
}
