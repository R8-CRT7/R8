import CoreImage
import ReplayKit
import UIKit
import Smart360Core
import UserNotifications

/// Broadcast Upload Extension: receives the screen while the user practises in 360° online.
///
/// Budget: iOS kills broadcast extensions above ~50 MB. We therefore look at ~1 frame/s,
/// downscale immediately, keep no frame history, and only run OCR + AI when a *settled*
/// screen change is detected. Frames never leave memory; nothing is written to disk except the
/// small JSON result and the history entry.
final class SampleHandler: RPBroadcastSampleHandler {
    private let ciContext = CIContext(options: [.cacheIntermediates: false])
    private var lastSample = Date.distantPast
    private var baselineHash: UInt64?
    private var candidateHash: UInt64?
    private var stableCount = 0
    private let busyLock = NSLock()
    private var _busy = false
    private var busy: Bool {
        get { busyLock.lock(); defer { busyLock.unlock() }; return _busy }
        set { busyLock.lock(); _busy = newValue; busyLock.unlock() }
    }
    private var lastQuestionID: String?
    private let queue = DispatchQueue(label: "smart360.broadcast")

    override func broadcastStarted(withSetupInfo setupInfo: [String: NSObject]?) {
        notify(title: "360 SMART is watching", body: "Open 360° online. New questions are analysed automatically.",
               historyID: nil)
    }

    override func processSampleBuffer(_ sampleBuffer: CMSampleBuffer, with sampleBufferType: RPSampleBufferType) {
        guard sampleBufferType == .video, Date().timeIntervalSince(lastSample) >= 1.0,
              let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lastSample = Date()
        autoreleasepool {
            let image = CIImage(cvPixelBuffer: pixelBuffer)
            guard let hash = self.frameHash(image) else { return }
            // settle detection: a change must stay stable for 2 samples before we analyse
            if let base = baselineHash, FrameHash.distance(base, hash) <= 4 {
                candidateHash = nil
                stableCount = 0
                return
            }
            if let cand = candidateHash, FrameHash.distance(cand, hash) <= 4 {
                stableCount += 1
            } else {
                candidateHash = hash
                stableCount = 1
            }
            guard stableCount >= 2, !busy, let cg = self.downscaledCGImage(image, maxSide: 1280) else { return }
            baselineHash = hash
            candidateHash = nil
            stableCount = 0
            busy = true
            queue.async { self.analyze(cg) }
        }
    }

    private func frameHash(_ image: CIImage) -> UInt64? {
        let sx = 9 / image.extent.width, sy = 8 / image.extent.height
        let small = image.transformed(by: CGAffineTransform(scaleX: sx, y: sy))
        var pixels = [UInt8](repeating: 0, count: 9 * 8 * 4)
        ciContext.render(small, toBitmap: &pixels, rowBytes: 9 * 4, bounds: CGRect(x: 0, y: 0, width: 9, height: 8),
                         format: .RGBA8, colorSpace: CGColorSpaceCreateDeviceRGB())
        var gray = [UInt8](repeating: 0, count: 72)
        for i in 0..<72 {
            let r = Int(pixels[i * 4]), g = Int(pixels[i * 4 + 1]), b = Int(pixels[i * 4 + 2])
            gray[i] = UInt8((r * 299 + g * 587 + b * 114) / 1000)
        }
        return FrameHash.dHash(gray)
    }

    private func downscaledCGImage(_ image: CIImage, maxSide: CGFloat) -> CGImage? {
        let longest = max(image.extent.width, image.extent.height)
        let s = min(1, maxSide / longest)
        let scaled = image.transformed(by: CGAffineTransform(scaleX: s, y: s))
        return ciContext.createCGImage(scaled, from: scaled.extent)
    }

    private func analyze(_ cg: CGImage) {
        let settings = AppSettings.load()
        defer { busy = false }
        guard let lines = try? TextRecognizer.recognize(cg), !lines.isEmpty else { return }
        // only analyse screens that look like a question, and each question once
        guard let parsed = ScreenQuestionParser.parse(lines), parsed.id != lastQuestionID else { return }
        lastQuestionID = parsed.id
        let key = KeychainStore.get(settings.keyName) ?? ""
        guard !key.isEmpty, let provider = settings.makeProvider(key: key) else {
            notify(title: "360 SMART", body: "Add your AI key in the app to get live answers.", historyID: nil)
            return
        }
        let jpeg = UIImage(cgImage: cg).jpegData(compressionQuality: 0.6)
        let analyzer = Analyzer(solver: ResilientSolver(provider: provider, maxRetries: 1),
                                cache: QuestionCache(url: AppGroup.cacheURL), threshold: settings.threshold,
                                costSaver: settings.costSaver)
        let sema = DispatchSemaphore(value: 0)
        Task {
            defer { sema.signal() }
            do {
                let o = try await analyzer.analyze(lines: lines, imageJPEG: jpeg)
                let entry = HistoryEntry(questionText: settings.storeQuestionText ? o.question.text : "",
                                         answers: o.question.answers.map(\.text), recommended: o.prediction.answers,
                                         confidence: o.prediction.confidence, decision: .skipped,
                                         topic: o.prediction.topic, source: o.prediction.source,
                                         processingMs: o.prediction.latencyMs, uncertain: o.prediction.uncertain)
                HistoryStore(url: AppGroup.historyURL).add(entry)
                if settings.notifyLive {
                    let pct = Int((o.prediction.confidence * 100).rounded())
                    let head = o.prediction.uncertain ? "Check: \(o.prediction.display) · \(pct) %"
                        : "\(o.prediction.display) · \(pct) %"
                    notify(title: head, body: o.prediction.reason, historyID: entry.id)
                }
            } catch {
                notify(title: "360 SMART", body: (error as? LocalizedError)?.errorDescription ?? "Analysis failed",
                       historyID: nil)
            }
        }
        _ = sema.wait(timeout: .now() + 45)
    }

    private func notify(title: String, body: String, historyID: UUID?) {
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        c.sound = nil
        c.interruptionLevel = .active
        if let historyID {
            c.categoryIdentifier = "SMART360_RESULT"
            c.userInfo = ["history_id": historyID.uuidString]
        }
        let req = UNNotificationRequest(identifier: "smart360.live", content: c, trigger: nil)
        UNUserNotificationCenter.current().add(req)
    }
}
