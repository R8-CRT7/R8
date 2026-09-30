import Smart360Core
import SwiftUI

/// Question detected · Recommended answer · Confidence · Reason · CONFIRM / RECHECK
struct QuestionView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var confirmed = false

    var body: some View {
        ZStack {
            NGBackground()
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    HStack {
                        CaptionText(title, color: accent)
                        Spacer()
                        Button { dismiss() } label: { Image(systemName: "xmark").foregroundStyle(NG.text2) }
                    }
                    switch model.phase {
                    case .analyzing:
                        analyzing
                    case .error(let msg):
                        errorCard(msg)
                    default:
                        if let q = model.question, let p = model.prediction {
                            result(q, p)
                        } else {
                            Text("No question yet.").foregroundStyle(NG.text2)
                        }
                    }
                }
                .padding(20)
            }
        }
    }

    private var title: String {
        switch model.phase {
        case .analyzing: return "Analyzing"
        case .error: return "Attention"
        default: return model.prediction?.uncertain == true ? "Check this one" : "Question detected"
        }
    }

    private var accent: Color {
        if case .error = model.phase { return NG.error }
        return model.prediction?.uncertain == true ? NG.warning : NG.primary
    }

    private var analyzing: some View {
        VStack(spacing: 18) {
            NeuralPulseView(mode: .analyzing, size: 150).frame(maxWidth: .infinity)
            Text("Reading the situation and the answers…").font(.ngBody).foregroundStyle(NG.text2)
                .frame(maxWidth: .infinity)
        }
        .padding(.top, 40)
    }

    private func errorCard(_ msg: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(msg).font(.ngBody).foregroundStyle(NG.text)
            Button("Try again") { Task { await model.recheck() } }.buttonStyle(GlowButtonStyle(kind: .ghost))
        }
        .glassCard(accent: NG.error)
    }

    @ViewBuilder
    private func result(_ q: Question, _ p: Prediction) -> some View {
        Text(q.text).font(.ngTitle).foregroundStyle(NG.text)
        VStack(alignment: .leading, spacing: 10) {
            ForEach(q.answers, id: \.index) { a in
                let chosen = p.answers.contains(a.index)
                HStack(alignment: .top, spacing: 12) {
                    Text("\(a.index)").font(.ngTelemetry).foregroundStyle(chosen ? NG.primary : NG.text3).frame(width: 18)
                    Text(a.text).font(chosen ? .system(size: 15, weight: .semibold) : .ngBody)
                        .foregroundStyle(chosen ? NG.text : NG.text2)
                    Spacer()
                    if chosen { Image(systemName: "checkmark.circle.fill").foregroundStyle(NG.success) }
                }
            }
        }
        .glassCard()

        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    CaptionText("Recommended answer")
                    Text(p.display).font(.ngHero)
                        .foregroundStyle(NG.confidenceColor(p.confidence, threshold: model.settings.threshold))
                        .contentTransition(.numericText())
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    CaptionText("Confidence")
                    Text("\(Int((p.confidence * 100).rounded())) %").font(.system(size: 22, weight: .semibold)).monospacedDigit()
                        .foregroundStyle(NG.text)
                }
            }
            ConfidenceMeter(value: p.confidence, threshold: model.settings.threshold)
            if p.uncertain { Chip(text: "Manual check", color: NG.warning) }
            CaptionText("Reason")
            Text(p.reason).font(.ngBody).foregroundStyle(NG.text)
            Text(sourceLine(p)).font(.system(size: 12)).foregroundStyle(NG.text3)
        }
        .glassCard(accent: p.uncertain ? NG.warning : NG.primary)

        HStack(spacing: 12) {
            Button {
                model.confirm()
                confirmed = true
            } label: { Label(confirmed ? "CONFIRMED" : (p.uncertain ? "CONFIRM ANYWAY" : "CONFIRM"),
                             systemImage: confirmed ? "checkmark.seal.fill" : "checkmark") }
                .buttonStyle(GlowButtonStyle(kind: p.uncertain ? .warning : .primary))
                .disabled(confirmed)
            Button { Task { confirmed = false; await model.recheck() } } label: {
                Label("RECHECK", systemImage: "arrow.clockwise")
            }
            .buttonStyle(GlowButtonStyle(kind: .ghost))
        }
        Text("Select the answer in 360° online yourself - iOS apps cannot tap inside other apps.")
            .font(.system(size: 12)).foregroundStyle(NG.text3)
    }

    private func sourceLine(_ p: Prediction) -> String {
        let src = ["ai": "AI", "cache": "Cache", "demo": "Demo"][p.source.rawValue] ?? p.source.rawValue
        let lat = p.latencyMs > 0 ? String(format: " · %.1f s", p.latencyMs / 1000) : ""
        return "\(src) · \(p.model)\(lat) · \(p.topic)"
    }
}
