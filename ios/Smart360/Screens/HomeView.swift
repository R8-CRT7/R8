import PhotosUI
import ReplayKit
import Smart360Core
import SwiftUI

struct RootView: View {
    @Environment(AppModel.self) private var model
    @State private var tab = 0

    var body: some View {
        TabView(selection: $tab) {
            NavigationStack { HomeView() }
                .tabItem { Label("Home", systemImage: "circle.hexagongrid") }.tag(0)
            NavigationStack { HistoryView() }
                .tabItem { Label("History", systemImage: "clock") }.tag(1)
            NavigationStack { InsightsView() }
                .tabItem { Label("Insights", systemImage: "chart.bar") }.tag(2)
            NavigationStack { SettingsView() }
                .tabItem { Label("Settings", systemImage: "gearshape") }.tag(3)
        }
        .tint(NG.primary)
        .preferredColorScheme(.dark)
    }
}

struct HomeView: View {
    @Environment(AppModel.self) private var model
    @State private var pickerItem: PhotosPickerItem?
    @State private var showQuestion = false
    @State private var showLive = false

    private var pulseMode: NeuralPulseView.Mode {
        switch model.phase {
        case .ready: return .idle
        case .analyzing: return .analyzing
        case .result: return model.prediction?.uncertain == true ? .uncertain : .ready
        case .error: return .error
        case .paused: return .paused
        }
    }

    private var statusText: String {
        switch model.phase {
        case .ready: return "READY"
        case .analyzing: return "ANALYZING"
        case .result: return "ANSWER READY"
        case .error: return "ATTENTION"
        case .paused: return "PAUSED"
        }
    }

    var body: some View {
        ZStack {
            NGBackground()
            ScrollView {
                VStack(spacing: 28) {
                    VStack(spacing: 14) {
                        NeuralPulseView(mode: pulseMode, size: 180)
                        Text("360 SMART").font(.system(size: 34, weight: .bold)).tracking(2).foregroundStyle(NG.text)
                        Text("AI Driving Theory Assistant").font(.ngBody).foregroundStyle(NG.text2)
                        Chip(text: statusText, color: model.phase == .paused ? NG.text2 : NG.primary)
                    }
                    .padding(.top, 24)

                    VStack(spacing: 12) {
                        PhotosPicker(selection: $pickerItem, matching: .screenshots) {
                            Label("START ANALYSIS", systemImage: "viewfinder")
                        }
                        .buttonStyle(GlowButtonStyle())
                        Button { showLive = true } label: { Label("Live analysis", systemImage: "dot.radiowaves.left.and.right") }
                            .buttonStyle(GlowButtonStyle(kind: .ghost))
                        if model.phase == .result {
                            Button { showQuestion = true } label: { Label("Show last result", systemImage: "sparkles") }
                                .buttonStyle(GlowButtonStyle(kind: .ghost))
                        }
                    }

                    if case .error(let msg) = model.phase {
                        Text(msg).font(.ngBody).foregroundStyle(NG.error).glassCard(accent: NG.error)
                    }
                    if !model.hasKey {
                        VStack(alignment: .leading, spacing: 8) {
                            CaptionText("Setup", color: NG.warning)
                            Text("Add your AI key in Settings to start. It is stored in the iOS Keychain.")
                                .font(.ngBody).foregroundStyle(NG.text2)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .glassCard(accent: NG.warning)
                    }
                    HowItWorks()
                }
                .padding(20)
            }
        }
        .navigationBarHidden(true)
        .onChange(of: pickerItem) { _, item in
            guard let item else { return }
            Task {
                if let data = try? await item.loadTransferable(type: Data.self), let img = UIImage(data: data) {
                    showQuestion = true
                    await model.analyze(img)
                }
                pickerItem = nil
            }
        }
        .sheet(isPresented: $showQuestion) { QuestionView().presentationDetents([.large]) }
        .sheet(isPresented: $showLive) { LiveAnalysisView().presentationDetents([.large]) }
    }
}

private struct HowItWorks: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CaptionText("Three ways to analyse")
            row("camera.viewfinder", "Screenshot", "Take a screenshot in 360° online, then tap START ANALYSIS.")
            row("dot.radiowaves.left.and.right", "Live", "Start a screen broadcast - results arrive as notifications.")
            row("square.and.arrow.up", "Share & Shortcuts", "Share a screenshot to 360 SMART or use the Shortcut / Back Tap.")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard()
    }

    func row(_ icon: String, _ title: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: icon).font(.system(size: 18)).foregroundStyle(NG.primary).frame(width: 26)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.ngTitle).foregroundStyle(NG.text)
                Text(text).font(.system(size: 13)).foregroundStyle(NG.text2)
            }
        }
    }
}

/// Live analysis via a ReplayKit screen broadcast (system picker - no private APIs).
struct LiveAnalysisView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            NGBackground()
            VStack(spacing: 24) {
                NeuralPulseView(mode: .capture, size: 140).padding(.top, 30)
                Text("Live analysis").font(.ngDisplay).foregroundStyle(NG.text)
                Text("Tap the button, choose **360 SMART** and start the broadcast. Then switch to 360° online. "
                     + "Every new question is read on-device and the recommendation appears as a notification.")
                    .font(.ngBody).foregroundStyle(NG.text2).multilineTextAlignment(.center)
                BroadcastPicker()
                    .frame(width: 72, height: 72)
                    .background(Circle().fill(NG.primary.opacity(0.18)))
                    .overlay(Circle().strokeBorder(NG.primary.opacity(0.6), lineWidth: 1))
                VStack(alignment: .leading, spacing: 8) {
                    CaptionText("Good to know")
                    Text("• iOS does not allow any app to tap inside another app - you answer in 360° online yourself.")
                    Text("• The red status bar shows that the broadcast is running. Stop it in Control Center.")
                    Text("• Frames are processed in memory and never stored.")
                }
                .font(.system(size: 13)).foregroundStyle(NG.text2)
                .frame(maxWidth: .infinity, alignment: .leading)
                .glassCard()
                Spacer()
                Button("Close") { dismiss() }.buttonStyle(GlowButtonStyle(kind: .ghost))
            }
            .padding(20)
        }
    }
}

struct BroadcastPicker: UIViewRepresentable {
    func makeUIView(context: Context) -> RPSystemBroadcastPickerView {
        let v = RPSystemBroadcastPickerView(frame: CGRect(x: 0, y: 0, width: 72, height: 72))
        v.preferredExtension = "com.smart360.app.broadcast"
        v.showsMicrophoneButton = false
        return v
    }

    func updateUIView(_ uiView: RPSystemBroadcastPickerView, context: Context) {}
}
