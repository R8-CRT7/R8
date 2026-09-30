import Smart360Core
import SwiftUI

struct HistoryView: View {
    @Environment(AppModel.self) private var model
    @State private var search = ""
    @State private var filter = "all"

    private var rows: [HistoryEntry] {
        _ = model.historyTick
        return model.history.entries.filter { e in
            (search.isEmpty || e.questionText.localizedCaseInsensitiveContains(search)) &&
                (filter == "all" || (filter == "uncertain" ? e.uncertain : e.decision.rawValue == filter))
        }
    }

    var body: some View {
        let _ = model.historyTick
        ZStack {
            NGBackground()
            if model.history.entries.isEmpty {
                EmptyStateView(icon: "clock", title: "Your analyzed questions will appear here.",
                               text: "Analyse a screenshot or start a live session.")
            } else {
                List {
                    Picker("Filter", selection: $filter) {
                        Text("All").tag("all")
                        Text("Accepted").tag("accepted")
                        Text("Rejected").tag("rejected")
                        Text("Uncertain").tag("uncertain")
                    }
                    .pickerStyle(.segmented)
                    .listRowBackground(Color.clear)
                    ForEach(rows) { e in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Chip(text: e.topic, color: NG.secondary)
                                Spacer()
                                Text("\(Int(e.confidence * 100)) %").font(.ngTelemetry)
                                    .foregroundStyle(NG.confidenceColor(e.confidence))
                            }
                            Text(e.questionText.isEmpty ? "(text not stored)" : e.questionText)
                                .font(.ngBody).foregroundStyle(NG.text).lineLimit(2)
                            HStack {
                                Text("Recommended " + e.recommended.map(String.init).joined(separator: " + "))
                                Spacer()
                                Text(e.decision.rawValue.capitalized)
                                Text(e.date, style: .time)
                            }
                            .font(.system(size: 12)).foregroundStyle(NG.text2)
                        }
                        .padding(.vertical, 6)
                        .listRowBackground(Color.white.opacity(0.04))
                    }
                }
                .scrollContentBackground(.hidden)
                .searchable(text: $search, prompt: "Search questions")
            }
        }
        .navigationTitle("History")
    }
}

struct InsightsView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        let _ = model.historyTick
        ZStack {
            NGBackground()
            let topics = model.history.topics()
            if topics.isEmpty {
                EmptyStateView(icon: "chart.bar", title: "Insights need a little history",
                               text: "After a few questions you will see difficult topics and your progress here.")
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        HStack(spacing: 12) {
                            stat("Analyzed", "\(model.history.entries.count)")
                            stat("Avg conf.", "\(avgConfidence) %")
                            stat("Uncertain", "\(model.history.entries.filter(\.uncertain).count)")
                        }
                        VStack(alignment: .leading, spacing: 12) {
                            CaptionText("Topics")
                            let mx = Double(topics.map(\.count).max() ?? 1)
                            ForEach(topics, id: \.topic) { t in
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        Text(t.topic).foregroundStyle(NG.text)
                                        Spacer()
                                        Text("\(t.count) · Ø \(Int(t.avgConfidence * 100)) % · \(t.rejected) rejected")
                                            .font(.system(size: 12)).foregroundStyle(NG.text2)
                                    }
                                    GeometryReader { g in
                                        Capsule().fill(Color.white.opacity(0.07))
                                            .overlay(alignment: .leading) {
                                                Capsule().fill(LinearGradient(colors: [NG.secondary, NG.primary],
                                                                              startPoint: .leading, endPoint: .trailing))
                                                    .frame(width: g.size.width * Double(t.count) / mx)
                                            }
                                    }
                                    .frame(height: 6)
                                }
                            }
                        }
                        .glassCard()
                    }
                    .padding(20)
                }
            }
        }
        .navigationTitle("Insights")
    }

    private var avgConfidence: Int {
        let e = model.history.entries
        return e.isEmpty ? 0 : Int(e.map(\.confidence).reduce(0, +) / Double(e.count) * 100)
    }

    private func stat(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            CaptionText(title)
            Text(value).font(.system(size: 24, weight: .semibold)).monospacedDigit().foregroundStyle(NG.text)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard()
    }
}

struct SettingsView: View {
    @Environment(AppModel.self) private var model
    @State private var key = ""
    @State private var saved = false

    var body: some View {
        @Bindable var m = model
        Form {
            Section("AI") {
                Picker("Provider", selection: $m.settings.provider) {
                    Text("Anthropic Claude").tag("anthropic")
                    Text("OpenAI").tag("openai")
                    Text("Google Gemini").tag("gemini")
                }
                TextField("Model (empty = default)", text: $m.settings.model)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                SecureField(model.hasKey ? "API key saved in Keychain" : "API key", text: $key)
                Button(saved ? "Saved ✓" : "Save key to Keychain") {
                    guard !key.isEmpty else { return }
                    saved = KeychainStore.set(key.trimmingCharacters(in: .whitespacesAndNewlines),
                                              for: model.settings.keyName)
                    key = ""
                }
                .disabled(key.isEmpty)
            }
            Section("Behaviour") {
                VStack(alignment: .leading) {
                    Text("Confidence threshold: \(Int(model.settings.threshold * 100)) %")
                    Slider(value: $m.settings.threshold, in: 0.5...0.95, step: 0.05)
                }
                Toggle("Cost saver (cache first)", isOn: $m.settings.costSaver)
                Toggle("Live notifications", isOn: $m.settings.notifyLive)
            }
            Section("Privacy") {
                Toggle("Store question text in history", isOn: $m.settings.storeQuestionText)
                Button("Clear history", role: .destructive) { model.clearHistory() }
                Button("Clear question cache", role: .destructive) { model.cache.clear() }
                Text("Screenshots and broadcast frames are processed in memory and deleted after analysis.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Section("About") {
                Text("360 SMART · AI Driving Theory Assistant")
                Text("A study companion: it explains its recommendations so you learn the rule. It cannot be used in "
                     + "the official exam and is not affiliated with DEGENER Verlag.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
        .scrollContentBackground(.hidden)
        .background(NGBackground())
        .navigationTitle("Settings")
        .onChange(of: model.settings) { _, s in s.save() }
    }
}

struct EmptyStateView: View {
    let icon: String
    let title: String
    let text: String

    var body: some View {
        VStack(spacing: 14) {
            ZStack {
                Circle().fill(RadialGradient(colors: [NG.primary.opacity(0.25), .clear], center: .center,
                                             startRadius: 0, endRadius: 60)).frame(width: 110, height: 110)
                Image(systemName: icon).font(.system(size: 28)).foregroundStyle(NG.primary)
            }
            Text(title).font(.ngTitle).foregroundStyle(NG.text).multilineTextAlignment(.center)
            Text(text).font(.ngBody).foregroundStyle(NG.text2).multilineTextAlignment(.center)
        }
        .padding(40)
    }
}
