import XCTest
@testable import Smart360Core

final class StateMachineTests: XCTestCase {
    func testConfirmOnlyForCurrentQuestion() throws {
        let sm = AnalysisStateMachine()
        let gen = try sm.beginCapture()
        try sm.questionDetected("q1", generation: gen)
        XCTAssertThrowsError(try sm.confirm("q1"))  // still analyzing
        try sm.predictionReady(for: "q1", generation: gen)
        XCTAssertThrowsError(try sm.confirm("q2"))
        try sm.confirm("q1")
        XCTAssertEqual(sm.state, .confirmed)
        XCTAssertThrowsError(try sm.confirm("q1"))  // single use
    }

    func testGenericTransitionNeverConfirms() {
        let sm = AnalysisStateMachine()
        XCTAssertThrowsError(try sm.transition(to: .confirmed))
        XCTAssertThrowsError(try sm.transition(to: .rejected))
    }

    func testStalePredictionRejected() throws {
        let sm = AnalysisStateMachine()
        let g1 = try sm.beginCapture()
        try sm.questionDetected("q1", generation: g1)
        try sm.transition(to: .capturing)  // new screen
        XCTAssertThrowsError(try sm.predictionReady(for: "q1", generation: g1))
    }

    func testPauseVoidsQuestion() throws {
        let sm = AnalysisStateMachine()
        let g = try sm.beginCapture()
        try sm.questionDetected("q1", generation: g)
        try sm.predictionReady(for: "q1", generation: g)
        sm.pause()
        XCTAssertThrowsError(try sm.confirm("q1"))
        sm.resume()
        XCTAssertEqual(sm.state, .idle)
    }
}

final class TextTests: XCTestCase {
    func testNormalizeAndNumbers() {
        XCTAssertEqual(TextNormalizer.normalize("  Straße,  RECHTS! "), "strasse, rechts")
        XCTAssertEqual(TextNormalizer.numbers("Bei 50 km/h und 1,5 m."), ["50", "1.5"])
    }

    func testRatioMatchesRapidFuzzDefinition() {
        XCTAssertEqual(Similarity.ratio("abc", "abc"), 1)
        XCTAssertEqual(Similarity.ratio("abcd", "abce"), 0.75, accuracy: 1e-9)
        XCTAssertEqual(Similarity.ratio("", "x"), 0)
    }

    func testNegationGuard() {
        let a = TextNormalizer.normalize(String(repeating: "Sie fahren auf einer Landstraße bei Nacht. ", count: 4)
                                         + "Wann dürfen Sie überholen?")
        let b = a.replacingOccurrences(of: "dürfen sie", with: "dürfen sie nicht")
        XCTAssertGreaterThan(Similarity.ratio(a, b), 0.97)
        XCTAssertFalse(Similarity.textEquivalent(a, b))
    }
}

final class CacheTests: XCTestCase {
    func q(_ t: String, _ a: [String], img: UInt64? = nil) -> Question {
        Question(text: t, answers: a.enumerated().map { AnswerOption(index: $0.offset + 1, text: $0.element) },
                 imageHash: img)
    }

    func testHitAndShuffleRemap() {
        let c = QuestionCache(url: nil)
        let base = q("Wie verhalten Sie sich?", ["Bremsen", "Hupen", "Weiterfahren"])
        c.store(base, correct: [1, 3], numberAnswer: nil, confidence: 0.9, reason: "r", topic: "Verhalten", model: "m")
        XCTAssertEqual(c.lookup(base)?.answers, [1, 3])
        let shuffled = q("Wie verhalten Sie sich?", ["Weiterfahren", "Bremsen", "Hupen"])
        XCTAssertEqual(c.lookup(shuffled)?.answers, [1, 2])
    }

    func testNumbersAndImagesNeverCollide() {
        let c = QuestionCache(url: nil)
        c.store(q("Höchstgeschwindigkeit 50 km/h?", ["Ja", "Nein"]), correct: [1], numberAnswer: nil,
                confidence: 0.9, reason: "r", topic: "t", model: "m")
        XCTAssertNil(c.lookup(q("Höchstgeschwindigkeit 70 km/h?", ["Ja", "Nein"])))
        c.store(q("Was gilt hier?", ["A1", "B2"], img: 0xFFFF_0000), correct: [1], numberAnswer: nil,
                confidence: 0.9, reason: "r", topic: "t", model: "m")
        XCTAssertNil(c.lookup(q("Was gilt hier?", ["A1", "B2"], img: 0x0000_FFFF)))
        XCTAssertNil(c.lookup(q("Was gilt hier?", ["A1", "B2"])))
    }

    func testCorruptedCacheRecovers() throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("c-\(UUID()).json")
        try Data("garbage".utf8).write(to: url)
        let c = QuestionCache(url: url)
        XCTAssertTrue(c.recoveredFromCorruption)
        XCTAssertEqual(c.count, 0)
    }
}

final class SchemaTests: XCTestCase {
    let good = #"{"question":"Q?","answer_texts":["a","b","c"],"answers":[3,1],"number_answer":null,"confidence":0.9,"reason":"Weil.","uncertain":false,"topic":"Vorfahrt"}"#

    func testValid() throws {
        let r = try SolveSchema.parse(Data(good.utf8))
        XCTAssertEqual(r.answers, [1, 3])
    }

    func testRejectsGarbage() {
        XCTAssertThrowsError(try SolveSchema.parse(Data("Die Antwort ist 1".utf8)))
        let bad = good.replacingOccurrences(of: "[3,1]", with: "[4]")
        XCTAssertThrowsError(try SolveSchema.parse(Data(bad.utf8)))
        let conf = good.replacingOccurrences(of: "0.9", with: "1.7")
        XCTAssertThrowsError(try SolveSchema.parse(Data(conf.utf8)))
        let none = good.replacingOccurrences(of: "[3,1]", with: "[]")
        XCTAssertThrowsError(try SolveSchema.parse(Data(none.utf8)))
    }

    func testAnthropicBodyShape() throws {
        let p = AnthropicProvider(apiKey: "k")
        let body = p.requestBody(SolveRequest(ocrText: "x", imageJPEG: Data([1, 2, 3])))
        XCTAssertEqual(body["model"] as? String, "claude-opus-5-5")
        XCTAssertEqual(body["fallbacks"] as? String, "default")
        let oc = body["output_config"] as? [String: Any]
        XCTAssertEqual((oc?["format"] as? [String: Any])?["type"] as? String, "json_schema")
        XCTAssertNil(body["temperature"])
        XCTAssertNoThrow(try JSONSerialization.data(withJSONObject: body))
    }
}

final class ConfidenceTests: XCTestCase {
    func testCaps() {
        XCTAssertGreaterThan(ConfidenceEngine.composite(ConfidenceInputs(model: 0.96)).value, 0.95)
        XCTAssertLessThanOrEqual(ConfidenceEngine.composite(ConfidenceInputs(model: 0.99, ocr: 0.3)).value, 0.6)
        XCTAssertLessThan(ConfidenceEngine.composite(ConfidenceInputs(model: 0.99, modelUncertain: true)).value, 0.75)
    }
}

final class ParserTests: XCTestCase {
    func testParsesPhoneScreenshotLines() {
        let lines = [
            OCRLine(text: "9:41", x: 0.1, y: 0.01, w: 0.1, h: 0.02, confidence: 1),
            OCRLine(text: "Wie verhalten Sie sich an dieser", x: 0.05, y: 0.20, w: 0.9, h: 0.03, confidence: 0.95),
            OCRLine(text: "Kreuzung?", x: 0.05, y: 0.235, w: 0.3, h: 0.03, confidence: 0.95),
            OCRLine(text: "Ich lasse den Radfahrer fahren", x: 0.1, y: 0.50, w: 0.8, h: 0.03, confidence: 0.9),
            OCRLine(text: "Ich fahre zügig", x: 0.1, y: 0.58, w: 0.5, h: 0.03, confidence: 0.9),
            OCRLine(text: "Ich warte", x: 0.1, y: 0.66, w: 0.3, h: 0.03, confidence: 0.9),
            OCRLine(text: "Weiter", x: 0.7, y: 0.85, w: 0.2, h: 0.03, confidence: 0.9),
        ]
        let q = ScreenQuestionParser.parse(lines)
        XCTAssertEqual(q?.text, "Wie verhalten Sie sich an dieser Kreuzung?")
        XCTAssertEqual(q?.answers.map(\.text), ["Ich lasse den Radfahrer fahren", "Ich fahre zügig", "Ich warte"])
    }

    func testFrameHash() {
        let a = [UInt8](repeating: 10, count: 72)
        var b = a
        b[1] = 200
        XCTAssertEqual(FrameHash.distance(FrameHash.dHash(a), FrameHash.dHash(a)), 0)
        XCTAssertGreaterThan(FrameHash.distance(FrameHash.dHash(a), FrameHash.dHash(b)), 0)
    }
}
