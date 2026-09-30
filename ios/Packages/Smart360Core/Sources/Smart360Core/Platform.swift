import Foundation
#if canImport(Security)
import Security
#endif
#if canImport(Vision)
import CoreGraphics
import Vision
#endif

/// Shared container between the app and its extensions (requires the App Group capability).
public enum AppGroup {
    public static let identifier = "group.com.smart360.app"

    public static var containerURL: URL {
        if let u = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: identifier) { return u }
        // Fallback (unit tests / missing entitlement): app-private documents
        return FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSTemporaryDirectory())
    }

    public static var defaults: UserDefaults { UserDefaults(suiteName: identifier) ?? .standard }
    public static var cacheURL: URL { containerURL.appendingPathComponent("question_cache.json") }
    public static var historyURL: URL { containerURL.appendingPathComponent("history.json") }
    public static var inboxURL: URL { containerURL.appendingPathComponent("inbox", isDirectory: true) }
    public static var liveResultURL: URL { containerURL.appendingPathComponent("live_result.json") }
}

/// Settings shared by app and extensions.
public struct AppSettings: Codable, Sendable, Equatable {
    public var provider: String = "anthropic"
    public var model: String = ""
    public var threshold: Double = 0.75
    public var costSaver: Bool = true
    public var notifyLive: Bool = true
    public var storeQuestionText: Bool = true

    public init() {}

    public static func load() -> AppSettings {
        guard let data = AppGroup.defaults.data(forKey: "settings"),
              let s = try? JSONDecoder().decode(AppSettings.self, from: data) else { return AppSettings() }
        return s
    }

    public func save() {
        if let data = try? JSONEncoder().encode(self) { AppGroup.defaults.set(data, forKey: "settings") }
    }

    public var keyName: String {
        ["anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"][provider] ?? ""
    }

    public func makeProvider(key: String) -> (any AIProvider)? {
        switch provider {
        case "anthropic": return AnthropicProvider(apiKey: key, model: model.isEmpty ? "claude-opus-5-5" : model)
        case "openai": return OpenAIProvider(apiKey: key, model: model.isEmpty ? "gpt-6-luna" : model)
        case "gemini": return GeminiProvider(apiKey: key, model: model.isEmpty ? "gemini-3.8-flash" : model)
        default: return nil
        }
    }
}

#if canImport(Security)
/// API keys live in the Keychain, shared with the extensions via a keychain access group.
public enum KeychainStore {
    public static let service = "com.smart360.app"
    /// "$(AppIdentifierPrefix)com.smart360.shared" - expanded by Xcode into Info.plist of app + extensions.
    public static var accessGroup: String? {
        guard let g = Bundle.main.object(forInfoDictionaryKey: "KeychainAccessGroup") as? String,
              !g.hasPrefix("$(") else { return nil }
        return g
    }

    static func base(_ name: String) -> [String: Any] {
        var q: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                kSecAttrService as String: service,
                                kSecAttrAccount as String: name]
        if let g = accessGroup { q[kSecAttrAccessGroup as String] = g }
        return q
    }

    @discardableResult
    public static func set(_ value: String, for name: String) -> Bool {
        SecItemDelete(base(name) as CFDictionary)
        var q = base(name)
        q[kSecValueData as String] = Data(value.utf8)
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }

    public static func get(_ name: String) -> String? {
        var q = base(name)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }

    public static func delete(_ name: String) {
        SecItemDelete(base(name) as CFDictionary)
    }
}
#endif

/// History persisted as JSON in the App Group container (local only).
public final class HistoryStore: @unchecked Sendable {
    private let lock = NSLock()
    private let url: URL?
    public private(set) var entries: [HistoryEntry] = []
    public let limit: Int

    public init(url: URL?, limit: Int = 2000) {
        self.url = url
        self.limit = limit
        if let url, let data = try? Data(contentsOf: url),
           let e = try? JSONDecoder().decode([HistoryEntry].self, from: data) {
            entries = e
        }
    }

    public func reload() {
        guard let url, let data = try? Data(contentsOf: url),
              let e = try? JSONDecoder().decode([HistoryEntry].self, from: data) else { return }
        lock.lock()
        entries = e
        lock.unlock()
    }

    public func add(_ e: HistoryEntry) {
        lock.lock()
        entries.insert(e, at: 0)
        if entries.count > limit { entries.removeLast(entries.count - limit) }
        let snapshot = entries
        lock.unlock()
        save(snapshot)
    }

    public func setDecision(_ id: UUID, _ d: Decision) {
        lock.lock()
        if let i = entries.firstIndex(where: { $0.id == id }) { entries[i].decision = d }
        let snapshot = entries
        lock.unlock()
        save(snapshot)
    }

    public func clear() {
        lock.lock()
        entries = []
        lock.unlock()
        save([])
    }

    private func save(_ snapshot: [HistoryEntry]) {
        guard let url else { return }
        if let data = try? JSONEncoder().encode(snapshot) {
            try? data.write(to: url, options: [.atomic, .completeFileProtection])
        }
    }

    public func topics() -> [TopicStat] {
        lock.lock(); defer { lock.unlock() }
        let groups = Dictionary(grouping: entries, by: { $0.topic.isEmpty ? "Sonstiges" : $0.topic })
        return groups.map { pair in
            TopicStat(topic: pair.key, count: pair.value.count,
                      avgConfidence: pair.value.map(\.confidence).reduce(0, +) / Double(pair.value.count),
                      rejected: pair.value.filter { $0.decision == .rejected }.count)
        }.sorted { $0.count > $1.count }
    }
}

public struct TopicStat: Hashable, Sendable {
    public var topic: String
    public var count: Int
    public var avgConfidence: Double
    public var rejected: Int
}

#if canImport(Vision)
/// On-device OCR with Vision (German first). Works in the app and in the extensions.
public enum TextRecognizer {
    public static func recognize(_ image: CGImage, fast: Bool = false) throws -> [OCRLine] {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = fast ? .fast : .accurate
        request.recognitionLanguages = ["de-DE", "en-US"]
        request.usesLanguageCorrection = !fast
        let handler = VNImageRequestHandler(cgImage: image, options: [:])
        try handler.perform([request])
        let obs = request.results ?? []
        return obs.compactMap { o in
            guard let c = o.topCandidates(1).first else { return nil }
            let b = o.boundingBox  // normalized, origin bottom-left
            return OCRLine(text: c.string, x: b.minX, y: 1 - b.maxY, w: b.width, h: b.height,
                           confidence: Double(c.confidence))
        }
    }
}
#endif

/// Tiny perceptual difference hash on a grayscale buffer (used for change detection).
public enum FrameHash {
    /// `pixels` = 9x8 grayscale values (row-major).
    public static func dHash(_ pixels: [UInt8]) -> UInt64 {
        precondition(pixels.count == 72)
        var h: UInt64 = 0
        for y in 0..<8 {
            for x in 0..<8 {
                h <<= 1
                if pixels[y * 9 + x + 1] > pixels[y * 9 + x] { h |= 1 }
            }
        }
        return h
    }

    public static func distance(_ a: UInt64, _ b: UInt64) -> Int { (a ^ b).nonzeroBitCount }
}
