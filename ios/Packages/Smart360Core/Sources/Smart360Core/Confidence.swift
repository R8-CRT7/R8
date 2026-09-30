import Foundation

/// Composite confidence: weighted geometric mean + caps (the weakest signal limits the result).
public struct ConfidenceInputs: Sendable {
    public var model: Double
    public var ocr: Double = 1
    public var layout: Double = 1
    public var imageClarity: Double = 1
    public var cacheSimilarity: Double?
    public var modelUncertain = false
    public var hasImage = false

    public init(model: Double, ocr: Double = 1, layout: Double = 1, imageClarity: Double = 1,
                cacheSimilarity: Double? = nil, modelUncertain: Bool = false, hasImage: Bool = false) {
        self.model = model
        self.ocr = ocr
        self.layout = layout
        self.imageClarity = imageClarity
        self.cacheSimilarity = cacheSimilarity
        self.modelUncertain = modelUncertain
        self.hasImage = hasImage
    }
}

public enum ConfidenceEngine {
    static let weights: [String: Double] = [
        "model": 0.5, "ocr": 0.18, "layout": 0.12, "image": 0.08, "cache": 0.05,
    ]

    public static func composite(
        _ inp: ConfidenceInputs, manualThreshold: Double = 0.75
    ) -> (value: Double, breakdown: [String: Double]) {
        func clamp(_ v: Double) -> Double { v.isNaN ? 0 : min(1, max(0, v)) }
        var s: [String: Double] = ["model": clamp(inp.model), "ocr": clamp(inp.ocr), "layout": clamp(inp.layout)]
        if inp.hasImage { s["image"] = clamp(inp.imageClarity) }
        if let c = inp.cacheSimilarity { s["cache"] = clamp(c) }
        let total = s.keys.reduce(0.0) { $0 + (weights[$1] ?? 0) }
        let logSum = s.reduce(0.0) { $0 + (weights[$1.key] ?? 0) * log(max($1.value, 1e-4)) }
        var value = exp(logSum / total)
        if let o = s["ocr"], o < 0.55 { value = min(value, 0.6) }
        if let l = s["layout"], l < 0.5 { value = min(value, 0.6) }
        // a true cap (min): values just below the threshold must not stay above the cap (monotonicity)
        if inp.modelUncertain { value = min(value, manualThreshold - 0.01) }
        return (clamp(value), s)
    }
}
