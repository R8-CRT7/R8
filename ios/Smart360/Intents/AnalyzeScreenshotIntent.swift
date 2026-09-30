import AppIntents
import Smart360Core
import UIKit

/// Shortcuts / Back Tap workflow: "Take Screenshot" → "Analyze with 360 SMART".
/// Runs fully in the background and speaks/shows the recommendation.
struct AnalyzeScreenshotIntent: AppIntent {
    static var title: LocalizedStringResource = "Analyze Screenshot"
    static var description = IntentDescription("Reads a driving-theory question from a screenshot and recommends an answer.")

    // `supportedContentTypes:` is iOS 18+; the deployment target is iOS 17, so the type is checked in perform().
    @Parameter(title: "Screenshot")
    var screenshot: IntentFile

    func perform() async throws -> some IntentResult & ProvidesDialog & ReturnsValue<String> {
        guard let image = UIImage(data: screenshot.data), let cg = image.cgImage else {
            throw $screenshot.needsValueError("Please provide a screenshot.")
        }
        let settings = AppSettings.load()
        let key = KeychainStore.get(settings.keyName) ?? ""
        guard !key.isEmpty, let provider = settings.makeProvider(key: key) else {
            return .result(value: "", dialog: "Open 360 SMART and add your AI key first.")
        }
        let lines = try TextRecognizer.recognize(cg)
        let jpeg = image.jpegData(compressionQuality: 0.72)
        let analyzer = Analyzer(solver: ResilientSolver(provider: provider), cache: QuestionCache(url: AppGroup.cacheURL),
                                threshold: settings.threshold, costSaver: settings.costSaver)
        let o = try await analyzer.analyze(lines: lines, imageJPEG: jpeg)
        HistoryStore(url: AppGroup.historyURL).add(HistoryEntry(
            questionText: settings.storeQuestionText ? o.question.text : "", answers: o.question.answers.map(\.text),
            recommended: o.prediction.answers, confidence: o.prediction.confidence, decision: .skipped,
            topic: o.prediction.topic, source: o.prediction.source, processingMs: o.prediction.latencyMs,
            uncertain: o.prediction.uncertain))
        let pct = Int((o.prediction.confidence * 100).rounded())
        let check = o.prediction.uncertain ? " – please check manually" : ""
        let text = "\(o.prediction.display) · \(pct) %\(check). \(o.prediction.reason)"
        return .result(value: text, dialog: IntentDialog(stringLiteral: text))
    }
}

struct Smart360Shortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: AnalyzeScreenshotIntent(),
                    phrases: ["Analyze screenshot with \(.applicationName)", "Frage prüfen mit \(.applicationName)"],
                    shortTitle: "Analyze Screenshot", systemImageName: "viewfinder")
    }
}
