import Smart360Core
import SwiftUI
import UIKit
import UniformTypeIdentifiers

/// Share extension: share a screenshot (Photos, screenshot editor, Safari) to 360 SMART and see
/// the recommendation right inside the share sheet.
final class ShareViewController: UIViewController {
    private let state = ShareState()

    override func viewDidLoad() {
        super.viewDidLoad()
        let host = UIHostingController(rootView: ShareResultView(state: state) { [weak self] in
            self?.extensionContext?.completeRequest(returningItems: nil)
        })
        addChild(host)
        host.view.frame = view.bounds
        host.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(host.view)
        host.didMove(toParent: self)
        Task { await load() }
    }

    private func load() async {
        guard let item = (extensionContext?.inputItems as? [NSExtensionItem])?.first,
              let provider = item.attachments?.first(where: { $0.hasItemConformingToTypeIdentifier(UTType.image.identifier) })
        else { await state.fail("No image found."); return }
        do {
            let loaded = try await provider.loadItem(forTypeIdentifier: UTType.image.identifier)
            var image: UIImage?
            if let url = loaded as? URL { image = UIImage(contentsOfFile: url.path) }
            else if let data = loaded as? Data { image = UIImage(data: data) }
            else if let img = loaded as? UIImage { image = img }
            guard let image, let cg = image.cgImage else { await state.fail("Unsupported image."); return }
            let settings = AppSettings.load()
            let key = KeychainStore.get(settings.keyName) ?? ""
            guard !key.isEmpty, let ai = settings.makeProvider(key: key) else {
                await state.fail("Open 360 SMART and add your AI key first.")
                return
            }
            let lines = try TextRecognizer.recognize(cg)
            let analyzer = Analyzer(solver: ResilientSolver(provider: ai), cache: QuestionCache(url: AppGroup.cacheURL),
                                    threshold: settings.threshold, costSaver: settings.costSaver)
            let o = try await analyzer.analyze(lines: lines, imageJPEG: image.jpegData(compressionQuality: 0.72))
            HistoryStore(url: AppGroup.historyURL).add(HistoryEntry(
                questionText: settings.storeQuestionText ? o.question.text : "", answers: o.question.answers.map(\.text),
                recommended: o.prediction.answers, confidence: o.prediction.confidence, decision: .skipped,
                topic: o.prediction.topic, source: o.prediction.source, processingMs: o.prediction.latencyMs,
                uncertain: o.prediction.uncertain))
            await state.done(o)
        } catch {
            await state.fail((error as? LocalizedError)?.errorDescription ?? error.localizedDescription)
        }
    }
}

@MainActor
final class ShareState: ObservableObject {
    @Published var outcome: AnalysisOutcome?
    @Published var error: String?

    func done(_ o: AnalysisOutcome) { outcome = o }
    func fail(_ m: String) { error = m }
}

struct ShareResultView: View {
    @ObservedObject var state: ShareState
    var close: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("360 SMART").font(.headline)
                Spacer()
                Button("Done", action: close)
            }
            if let o = state.outcome {
                Text(o.question.text).font(.subheadline).foregroundStyle(.secondary)
                Text(o.prediction.display).font(.system(size: 44, weight: .semibold, design: .rounded)).monospacedDigit()
                    .foregroundStyle(o.prediction.uncertain ? .orange : .cyan)
                Text("\(Int(o.prediction.confidence * 100)) % confidence" + (o.prediction.uncertain ? " · check manually" : ""))
                Text(o.prediction.reason)
            } else if let e = state.error {
                Text(e).foregroundStyle(.red)
            } else {
                ProgressView("Analyzing…")
            }
            Spacer()
        }
        .padding(24)
        .preferredColorScheme(.dark)
    }
}
