import SwiftUI

/// NEURAL GLASS design tokens for iOS (same palette as Windows, SF Pro typography).
enum NG {
    static let background = Color(hex: 0x070B10)
    static let surface = Color(hex: 0x0E151D)
    static let surfaceElevated = Color(hex: 0x121C26)
    static let primary = Color(hex: 0x30D5FF)
    static let secondary = Color(hex: 0x7C6CFF)
    static let success = Color(hex: 0x36E58A)
    static let warning = Color(hex: 0xFFB547)
    static let error = Color(hex: 0xFF5C72)
    static let text = Color(hex: 0xF5F8FA)
    static let text2 = Color(hex: 0x8E9BA8)
    static let text3 = Color(hex: 0x5B6875)

    static func confidenceColor(_ v: Double, threshold: Double = 0.75) -> Color {
        if v >= 0.9 { return success }
        if v >= threshold { return primary }
        if v >= threshold - 0.2 { return warning }
        return error
    }
}

extension Color {
    init(hex: UInt32, alpha: Double = 1) {
        self.init(.sRGB, red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255, opacity: alpha)
    }
}

extension Font {
    static let ngHero = Font.system(size: 52, weight: .semibold, design: .rounded).monospacedDigit()
    static let ngDisplay = Font.system(size: 30, weight: .bold)
    static let ngTitle = Font.system(size: 17, weight: .semibold)
    static let ngBody = Font.system(size: 15)
    static let ngCaption = Font.system(size: 11, weight: .semibold)
    static let ngTelemetry = Font.system(size: 15, weight: .medium).monospacedDigit()
}

/// App background: deep base + two soft light sources.
struct NGBackground: View {
    var body: some View {
        ZStack {
            NG.background
            RadialGradient(colors: [NG.primary.opacity(0.14), .clear], center: .topLeading, startRadius: 0,
                           endRadius: 520)
            RadialGradient(colors: [NG.secondary.opacity(0.12), .clear], center: .bottomTrailing, startRadius: 0,
                           endRadius: 520)
        }
        .ignoresSafeArea()
    }
}

struct GlassCard: ViewModifier {
    var accent: Color?
    func body(content: Content) -> some View {
        content
            .padding(20)
            .background {
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .fill(LinearGradient(colors: [Color(hex: 0x16222E, alpha: 0.92), Color(hex: 0x0C131B, alpha: 0.92)],
                                         startPoint: .top, endPoint: .bottom))
                    .overlay {
                        if let accent {
                            RoundedRectangle(cornerRadius: 22, style: .continuous)
                                .fill(LinearGradient(colors: [accent.opacity(0.14), .clear], startPoint: .topLeading,
                                                     endPoint: .center))
                        }
                    }
                    .overlay {
                        RoundedRectangle(cornerRadius: 22, style: .continuous)
                            .strokeBorder(LinearGradient(colors: [.white.opacity(0.16), .white.opacity(0.04)],
                                                         startPoint: .top, endPoint: .bottom), lineWidth: 1)
                    }
            }
    }
}

extension View {
    func glassCard(accent: Color? = nil) -> some View { modifier(GlassCard(accent: accent)) }
}

struct CaptionText: View {
    let text: String
    var color: Color = NG.text2
    init(_ text: String, color: Color = NG.text2) {
        self.text = text
        self.color = color
    }
    var body: some View {
        Text(text.uppercased()).font(.ngCaption).tracking(1.3).foregroundStyle(color)
    }
}

struct GlowButtonStyle: ButtonStyle {
    var kind: Kind = .primary
    enum Kind { case primary, ghost, warning }

    func makeBody(configuration: Configuration) -> some View {
        let fill: Color = kind == .warning ? NG.warning : NG.primary
        return configuration.label
            .font(.system(size: 16, weight: .semibold))
            .frame(maxWidth: .infinity, minHeight: 52)
            .foregroundStyle(kind == .ghost ? NG.text : Color(hex: 0x031018))
            .background {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(kind == .ghost ? AnyShapeStyle(Color.white.opacity(0.06))
                          : AnyShapeStyle(LinearGradient(colors: [fill.opacity(0.95), fill],
                                                         startPoint: .top, endPoint: .bottom)))
                    .overlay {
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .strokeBorder(.white.opacity(kind == .ghost ? 0.14 : 0.25), lineWidth: 1)
                    }
                    .shadow(color: kind == .ghost ? .clear : fill.opacity(configuration.isPressed ? 0.2 : 0.45),
                            radius: 16, y: 6)
            }
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.spring(duration: 0.2), value: configuration.isPressed)
    }
}

struct Chip: View {
    let text: String
    var color: Color = NG.text2
    var body: some View {
        Text(text.uppercased())
            .font(.system(size: 10.5, weight: .semibold)).tracking(0.8)
            .padding(.horizontal, 10).padding(.vertical, 5)
            .foregroundStyle(color)
            .background(Capsule().fill(color.opacity(0.14)))
            .overlay(Capsule().strokeBorder(color.opacity(0.4), lineWidth: 1))
    }
}

/// Segmented HUD confidence gauge.
struct ConfidenceMeter: View {
    var value: Double
    var threshold: Double = 0.75
    var segments = 22

    var body: some View {
        GeometryReader { geo in
            let gap: CGFloat = 3
            let w = (geo.size.width - gap * CGFloat(segments - 1)) / CGFloat(segments)
            HStack(spacing: gap) {
                ForEach(0..<segments, id: \.self) { i in
                    let lit = min(1, max(0, value * Double(segments) - Double(i)))
                    RoundedRectangle(cornerRadius: 2)
                        .fill(lit > 0 ? AnyShapeStyle(LinearGradient(colors: [NG.secondary,
                                                                               NG.confidenceColor(value, threshold: threshold)],
                                                                      startPoint: .leading, endPoint: .trailing))
                              : AnyShapeStyle(Color.white.opacity(0.07)))
                        .opacity(lit > 0 ? 0.35 + 0.65 * lit : 1)
                        .frame(width: w)
                }
            }
        }
        .frame(height: 10)
        .animation(.easeOut(duration: 0.6), value: value)
        .accessibilityElement()
        .accessibilityLabel("Confidence \(Int(value * 100)) percent")
    }
}

/// NEURAL PULSE - the signature element, driven by TimelineView (pauses automatically off-screen).
struct NeuralPulseView: View {
    enum Mode { case idle, capture, analyzing, ready, uncertain, confirmed, error, paused }
    var mode: Mode
    var size: CGFloat = 120
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var colors: (Color, Color) {
        switch mode {
        case .uncertain: return (NG.warning, Color(hex: 0xFF8A47))
        case .confirmed: return (NG.success, Color(hex: 0x2BD4A0))
        case .error: return (NG.error, Color(hex: 0xFF3B7F))
        case .paused: return (Color(hex: 0x6B7785), Color(hex: 0x4A5561))
        default: return (NG.primary, NG.secondary)
        }
    }

    var body: some View {
        TimelineView(.animation(minimumInterval: reduceMotion ? 0.25 : 1 / 60, paused: mode == .paused)) { tl in
            let t = reduceMotion ? 0 : tl.date.timeIntervalSinceReferenceDate
            Canvas { ctx, sz in
                let c = CGPoint(x: sz.width / 2, y: sz.height / 2)
                let r = min(sz.width, sz.height) * 0.26
                let (c1, c2) = colors
                let breathe = 0.5 + 0.5 * sin(t * 1.6)
                var haloScale = 1.0
                var haloAlpha = 0.35
                switch mode {
                case .idle: haloScale = 0.95 + 0.12 * breathe; haloAlpha = 0.2 + 0.15 * breathe
                case .ready, .uncertain: haloScale = 1.05 + 0.05 * breathe; haloAlpha = 0.4
                case .analyzing: haloScale = 1.1 + 0.08 * sin(t * 5); haloAlpha = 0.45
                case .confirmed: haloScale = 1.25; haloAlpha = 0.5
                default: break
                }
                let hr = r * 2 * haloScale
                ctx.fill(Path(ellipseIn: CGRect(x: c.x - hr, y: c.y - hr, width: hr * 2, height: hr * 2)),
                         with: .radialGradient(Gradient(colors: [c1.opacity(haloAlpha), c2.opacity(haloAlpha / 3), .clear]),
                                               center: c, startRadius: 0, endRadius: hr))
                if mode == .capture {
                    let k = (t.truncatingRemainder(dividingBy: 0.9)) / 0.9
                    let rr = r * (1 + 1.3 * k)
                    ctx.stroke(Path(ellipseIn: CGRect(x: c.x - rr, y: c.y - rr, width: rr * 2, height: rr * 2)),
                               with: .color(c1.opacity(0.8 * (1 - k))), lineWidth: 2)
                }
                if mode == .analyzing {
                    for (i, (speed, span, scale)) in [(140.0, 70.0, 1.45), (-95.0, 110.0, 1.7), (60.0, 40.0, 1.95)].enumerated() {
                        let start = Angle.degrees(t * speed + Double(i) * 120)
                        var arc = Path()
                        arc.addArc(center: c, radius: r * scale, startAngle: start,
                                   endAngle: start + .degrees(span), clockwise: false)
                        ctx.stroke(arc, with: .color((i == 1 ? c2 : c1).opacity(0.7 - Double(i) * 0.15)),
                                   style: StrokeStyle(lineWidth: 2, lineCap: .round))
                    }
                }
                ctx.fill(Path(ellipseIn: CGRect(x: c.x - r, y: c.y - r, width: r * 2, height: r * 2)),
                         with: .radialGradient(Gradient(stops: [.init(color: .white.opacity(0.92), location: 0),
                                                               .init(color: c1, location: 0.28),
                                                               .init(color: c2.opacity(0.9), location: 1)]),
                                               center: CGPoint(x: c.x - r * 0.35, y: c.y - r * 0.4),
                                               startRadius: 0, endRadius: r * 1.35))
                ctx.stroke(Path(ellipseIn: CGRect(x: c.x - r, y: c.y - r, width: r * 2, height: r * 2)),
                           with: .color(.white.opacity(0.25)), lineWidth: 1)
            }
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }
}
