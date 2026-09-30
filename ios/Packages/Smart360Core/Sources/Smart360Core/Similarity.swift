import Foundation

/// Indel-based similarity (same definition as RapidFuzz `fuzz.ratio`, 0...1).
public enum Similarity {
    public static func ratio(_ a: String, _ b: String) -> Double {
        let x = Array(a), y = Array(b)
        if x.isEmpty && y.isEmpty { return 1 }
        if x.isEmpty || y.isEmpty { return 0 }
        var prev = [Int](repeating: 0, count: y.count + 1)
        var cur = prev
        for i in 1...x.count {
            for j in 1...y.count {
                cur[j] = x[i - 1] == y[j - 1] ? prev[j - 1] + 1 : max(prev[j], cur[j - 1])
            }
            swap(&prev, &cur)
        }
        let lcs = prev[y.count]
        return Double(2 * lcs) / Double(x.count + y.count)
    }

    /// OCR noise changes characters inside words; it does not insert or delete whole words.
    public static func wordsCompatible(_ a: String, _ b: String) -> Bool {
        let wa = a.split(separator: " ").map(String.init)
        let wb = b.split(separator: " ").map(String.init)
        if wa.count != wb.count {
            return a.replacingOccurrences(of: " ", with: "") == b.replacingOccurrences(of: " ", with: "")
        }
        for (x, y) in zip(wa, wb) where x != y {
            if x.count <= 3 || y.count <= 3 { return false }
            if ratio(x, y) < 0.8 { return false }
        }
        return true
    }

    public static func textEquivalent(_ a: String, _ b: String, threshold: Double = 0.97) -> Bool {
        if a == b { return true }
        guard TextNormalizer.numbers(a) == TextNormalizer.numbers(b) else { return false }
        return ratio(a, b) >= threshold && wordsCompatible(a, b)
    }
}
