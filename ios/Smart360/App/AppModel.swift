import Observation
import Smart360Core
import SwiftUI
import UIKit
import UserNotifications

/// Central app state. Analysis runs off the main actor; UI state is updated on the main actor.
@MainActor
@Observable
final class AppModel {
    enum Phase: Equatable { case ready, analyzing, result, error(String), paused }

    var settings = AppSettings.load()
    var phase: Phase = .ready
    var question: Question?
    var prediction: Prediction?
    var liveActive = false
    var lastHistoryID: UUID?
    /// HistoryStore is a plain class; this counter makes SwiftUI re-render history-based views.
    var historyTick = 0
    var stats = (analyzed: 0, accepted: 0, rejected: 0, uncertain: 0, cacheHits: 0)

    let machine = AnalysisStateMachine()
    let cache = QuestionCache(url: AppGroup.cacheURL)
    let history = HistoryStore(url: AppGroup.historyURL)
    private var lastImage: UIImage?

    var hasKey: Bool { !(KeychainStore.get(settings.keyName) ?? "").isEmpty }

    func makeAnalyzer() -> Analyzer {
        let key = KeychainStore.get(settings.keyName) ?? ""
        let solver = settings.makeProvider(key: key).map { ResilientSolver(provider: $0) }
        return Analyzer(solver: key.isEmpty ? nil : solver, cache: cache, threshold: settings.threshold,
                        costSaver: settings.costSaver)
    }

    // ------------------------------------------------------------------ analysis
    func analyze(_ image: UIImage, forceFresh: Bool = false) async {
        guard phase != .paused else { return }
        lastImage = image
        phase = .analyzing
        question = nil
        prediction = nil
        do {
            let gen = try machine.beginCapture()
            guard let cg = image.downscaled(maxSide: 1600).cgImage else { throw ProviderError.invalid("image") }
            let jpeg = image.downscaled(maxSide: 1280).jpegData(compressionQuality: 0.72)
            let lines = try await Task.detached(priority: .userInitiated) { try TextRecognizer.recognize(cg) }.value
            let engine = makeAnalyzer()
            let outcome = try await engine.analyze(lines: lines, imageJPEG: jpeg, forceFresh: forceFresh)
            try machine.questionDetected(outcome.question.id, generation: gen)
            try machine.predictionReady(for: outcome.question.id, generation: gen)
            question = outcome.question
            prediction = outcome.prediction
            record(outcome, decision: .skipped)
            phase = .result
            UINotificationFeedbackGenerator().notificationOccurred(outcome.prediction.uncertain ? .warning : .success)
        } catch {
            machine.fail()
            phase = .error((error as? LocalizedError)?.errorDescription ?? error.localizedDescription)
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }

    func recheck() async {
        guard let img = lastImage else { return }
        await analyze(img, forceFresh: true)
    }

    /// iOS cannot tap inside other apps: confirming records YOUR decision (and teaches the history).
    func confirm() {
        guard let q = question else { return }
        do {
            try machine.confirm(q.id)
            if let id = lastHistoryID { history.setDecision(id, .accepted); historyTick += 1 }
            stats.accepted += 1
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        } catch {
            phase = .error("This recommendation is no longer current.")
        }
    }

    func reject() {
        guard let q = question else { return }
        if (try? machine.reject(q.id)) != nil, let id = lastHistoryID {
            history.setDecision(id, .rejected)
            historyTick += 1
            stats.rejected += 1
        }
    }

    func clearHistory() {
        history.clear()
        historyTick += 1
    }

    /// Re-read files written by the extensions (broadcast / share / intents).
    func reloadHistory() {
        history.reload()
        historyTick += 1
    }

    func togglePause() {
        if phase == .paused {
            machine.resume()
            phase = .ready
        } else {
            machine.pause()
            phase = .paused
        }
    }

    private func record(_ o: AnalysisOutcome, decision: Decision) {
        let e = HistoryEntry(questionText: settings.storeQuestionText ? o.question.text : "",
                             answers: settings.storeQuestionText ? o.question.answers.map(\.text) : [],
                             recommended: o.prediction.answers, confidence: o.prediction.confidence,
                             decision: decision, topic: o.prediction.topic, source: o.prediction.source,
                             processingMs: o.prediction.latencyMs, uncertain: o.prediction.uncertain)
        history.add(e)
        historyTick += 1
        lastHistoryID = e.id
        stats.analyzed += 1
        if o.prediction.uncertain { stats.uncertain += 1 }
        if o.prediction.source == .cache { stats.cacheHits += 1 }
    }

    // ------------------------------------------------------------------ inbox (share extension)
    func processInbox() async {
        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(at: AppGroup.inboxURL, includingPropertiesForKeys: nil)
            .sorted(by: { $0.lastPathComponent < $1.lastPathComponent }),
            let newest = files.last else { return }
        defer { files.forEach { try? fm.removeItem(at: $0) } }  // screenshots are ephemeral
        if let data = try? Data(contentsOf: newest), let img = UIImage(data: data) {
            await analyze(img)
        }
    }

    // ------------------------------------------------------------------ notifications
    static let categoryID = "SMART360_RESULT"

    static func registerNotificationCategories() {
        let confirm = UNNotificationAction(identifier: "CONFIRM", title: "Confirm", options: [])
        let reject = UNNotificationAction(identifier: "REJECT", title: "Reject", options: [.destructive])
        let cat = UNNotificationCategory(identifier: categoryID, actions: [confirm, reject], intentIdentifiers: [])
        UNUserNotificationCenter.current().setNotificationCategories([cat])
    }
}

extension UIImage {
    func downscaled(maxSide: CGFloat) -> UIImage {
        let longest = max(size.width, size.height)
        guard longest > maxSide else { return self }
        let scale = maxSide / longest
        let target = CGSize(width: size.width * scale, height: size.height * scale)
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        return UIGraphicsImageRenderer(size: target, format: format).image { _ in draw(in: CGRect(origin: .zero, size: target)) }
    }
}
