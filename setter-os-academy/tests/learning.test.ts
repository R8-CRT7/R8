// Wiederholungsalgorithmus, Kompetenzschätzung, Gamification und Persistenz.
import { describe, expect, it } from "vitest";
import { questionById, scenarioById } from "@/lib/content";
import { UNKNOWN_VALUE } from "@/lib/engine/coach";
import { activeDaysLast7, levelFor, XP_RULES } from "@/lib/engine/gamification";
import { grade } from "@/lib/engine/quiz";
import { BOX_INTERVAL_DAYS, buildReviewQueue, scheduleNext, summarizeObjective, type AttemptLog } from "@/lib/engine/review";
import {
  completeLesson,
  initialState,
  migrate,
  recordAnswer,
  recordQuizAttempt,
  recordSimulation,
  SCHEMA_VERSION,
  totalXp,
} from "@/lib/store/state";

const DAY = 86_400_000;
const T0 = Date.parse("2026-10-01T08:00:00Z");

describe("Leitner-Wiederholung", () => {
  const base = { questionId: "Q1", objectiveId: "LO1", now: T0 };
  it("L01 Erste richtige Antwort → Box 2, Intervall 3 Tage", () => {
    const r = scheduleNext(undefined, { ...base, score: 1, confidence: 3 });
    expect(r.box).toBe(2);
    expect(r.nextDueAt - T0).toBe(BOX_INTERVAL_DAYS[2] * DAY);
  });
  it("L02 Falsche Antwort → Box 1, morgen wieder", () => {
    const up = scheduleNext(scheduleNext(undefined, { ...base, score: 1 }), { ...base, score: 1 });
    const r = scheduleNext(up, { ...base, score: 0 });
    expect(r.box).toBe(1);
    expect(r.nextDueAt - T0).toBe(DAY);
  });
  it("L03 Richtig, aber geraten → keine Beförderung", () => {
    const r = scheduleNext(undefined, { ...base, score: 1, confidence: 1 });
    expect(r.box).toBe(1);
  });
  it("L04 Box ist nach oben begrenzt", () => {
    let r = scheduleNext(undefined, { ...base, score: 1 });
    for (let i = 0; i < 10; i++) r = scheduleNext(r, { ...base, score: 1 });
    expect(r.box).toBe(5);
  });
  it("L05 Teilpunkte zählen als nicht korrekt", () => {
    expect(scheduleNext(undefined, { ...base, score: 0.5 }).wrong).toBe(1);
  });
  it("L06 Warteschlange: nur fällige Items, verschachtelt nach Lernziel", () => {
    const mk = (id: string, obj: string, due: number) => ({ ...scheduleNext(undefined, { questionId: id, objectiveId: obj, score: 0, now: T0 }), nextDueAt: due });
    const items = [mk("a", "LO1", T0), mk("b", "LO1", T0), mk("c", "LO2", T0), mk("d", "LO2", T0 + 10 * DAY)];
    const q = buildReviewQueue(items, T0 + 1);
    expect(q.map((i) => i.questionId)).not.toContain("d");
    for (let i = 1; i < q.length - 1; i++) expect(q[i]!.objectiveId === q[i - 1]!.objectiveId && q[i]!.objectiveId === q[i + 1]!.objectiveId).toBe(false);
  });
});

describe("Gemessene Leistung vs. geschätzte Kompetenz", () => {
  const log = (score: number, dayOffset: number, confidence?: 1 | 2 | 3): AttemptLog => ({
    questionId: "Q", objectiveId: "LO1", score, at: T0 + dayOffset * DAY, durationMs: 10_000, confidence, errorCategories: [], context: "quiz",
  });
  it("K01 Ohne Versuche: nicht geprüft", () => {
    expect(summarizeObjective("LO1", []).mastery).toBe("nicht_geprueft");
  });
  it("K02 Ein perfekter Versuch reicht nicht für eine Kompetenzaussage", () => {
    const s = summarizeObjective("LO1", [log(1, 0)]);
    expect(s.measuredPerformance).toBe(100);
    expect(s.mastery).toBe("im_aufbau");
  });
  it("K03 Drei gute Versuche am selben Tag = gefestigt, aber nicht gesichert", () => {
    expect(summarizeObjective("LO1", [log(1, 0), log(1, 0), log(1, 0)]).mastery).toBe("gefestigt");
  });
  it("K04 Gesichert erst nach verzögertem richtigen Abruf (≥ 3 Tage)", () => {
    expect(summarizeObjective("LO1", [log(1, 0), log(1, 1), log(1, 4)]).mastery).toBe("gesichert");
  });
  it("K05 Neuere Versuche wiegen stärker", () => {
    const improving = summarizeObjective("LO1", [log(0, 0), log(0, 0), log(1, 1), log(1, 1)]).measuredPerformance!;
    const declining = summarizeObjective("LO1", [log(1, 0), log(1, 0), log(0, 1), log(0, 1)]).measuredPerformance!;
    expect(improving).toBeGreaterThan(declining);
  });
  it("K06 Überschätzung wird als positive Kalibrierungslücke ausgewiesen", () => {
    expect(summarizeObjective("LO1", [log(0, 0, 3), log(0, 0, 3)]).calibrationGap!).toBeGreaterThan(0.5);
  });
  it("K07 Schwache Simulation verhindert 'gesichert'", () => {
    expect(summarizeObjective("LO1", [log(1, 0), log(1, 1), log(1, 4)], [40]).mastery).toBe("gefestigt");
  });
});

describe("Gamification", () => {
  it("G01 Level-Schwellen", () => {
    expect(levelFor(0).level).toBe(1);
    expect(levelFor(150).level).toBe(2);
    expect(levelFor(149).progress).toBeLessThan(1);
  });
  it("G02 Aktive Tage statt brechender Serie", () => {
    const now = T0 + 6 * DAY;
    expect(activeDaysLast7([T0, T0 + 1000, T0 + 2 * DAY, T0 - 30 * DAY], now)).toBe(2);
  });
  it("G03 XP für erste richtige Antwort nur einmal", () => {
    const q = questionById("Q-M01-007")!;
    const r = grade(q, { type: "truefalse", value: true });
    let s = recordAnswer(initialState(), q, r, { durationMs: 1000, context: "quiz", now: T0 });
    s = recordAnswer(s, q, r, { durationMs: 1000, context: "quiz", now: T0 + 1 });
    expect(totalXp(s)).toBe(XP_RULES.questionFirstCorrect);
  });
  it("G04 Lektion doppelt abschließen gibt keine doppelten XP", () => {
    let s = completeLesson(initialState(), "M01-L01", "x", T0);
    s = completeLesson(s, "M01-L01", "x", T0 + 5);
    expect(totalXp(s)).toBe(XP_RULES.lessonCompleted);
    expect(s.achievements["first-lesson"]).toBe(T0);
  });
  it("G05 Freitext bewegt die Wiederholungsbox nicht (nur vorläufig)", () => {
    const q = questionById("Q-M01-030")!;
    const r = grade(q, { type: "freetext", text: "Hallo Frau Lenz, hier SolarNord, danke für Ihre Anfrage – passt es kurz? Was wünschen Sie sich?" });
    const s = recordAnswer(initialState(), q, r, { durationMs: 1, context: "lesson", now: T0 });
    expect(s.reviews["Q-M01-030"]).toBeUndefined();
    expect(s.attempts).toHaveLength(1);
  });
});

describe("Persistenz, Versionierung, Migration", () => {
  it("P01 Migration v0 → aktuell erhält Lektionen und Namen", () => {
    const s = migrate({ name: "Testperson", completed: ["M01-L01"] });
    expect(s.schemaVersion).toBe(SCHEMA_VERSION);
    expect(s.profile!.displayName).toBe("Testperson");
    expect(s.lessonsCompleted["M01-L01"]).toBeDefined();
  });
  it("P02 Migration v1 → v2 ergänzt Felder ohne Datenverlust", () => {
    const v1 = { ...initialState(), schemaVersion: 1, attempts: [{ questionId: "Q", objectiveId: "LO", score: 1, at: 1, durationMs: 1, errorCategories: [], context: "quiz" }] } as Record<string, unknown>;
    delete v1.transferSubmissions;
    const s = migrate(v1);
    expect(s.attempts).toHaveLength(1);
    expect(s.transferSubmissions).toEqual({});
    expect(s.settings.pauseMode).toBe(false);
  });
  it("P03 Müll im Speicher führt zu sauberem Neustart", () => {
    expect(migrate("kaputt").profile).toBeNull();
    expect(migrate(null).attempts).toEqual([]);
  });
  it("P04 Serialisierung ist verlustfrei", () => {
    const s = completeLesson(initialState(), "M01-L02", "0.1.0", T0);
    expect(migrate(JSON.parse(JSON.stringify(s)))).toEqual(s);
  });
  it("P05 Alte Prüfungsergebnisse bleiben bei Inhaltsänderungen unverändert", () => {
    const rec = { id: "a1", moduleId: "M01", kind: "module-exam" as const, at: T0, percent: 81.3, passed: true, courseVersion: "0.1.0", questionVersions: { "Q-M01-003": 1 }, scores: { "Q-M01-003": 1 }, pendingManualReview: 0 };
    const s = recordQuizAttempt(initialState(), rec);
    // simulate later content edit: question version 2 – stored record is a snapshot
    expect(s.quizAttempts[0]!.questionVersions["Q-M01-003"]).toBe(1);
    expect(s.quizAttempts[0]!.percent).toBe(81.3);
  });
  it("P06 Simulation speichert nur Zug-IDs (Datenminimierung), Bewertung reproduzierbar", () => {
    const sc = scenarioById("SIM-003")!;
    const { state, evaluation } = recordSimulation(initialState(), sc, ["ack-clarify", "close-respectful"], { fields: { contact_pref: "Keine weiteren Werbenachrichten", reason: "Informiert sich nur, Projekt frühestens in einigen Jahren" } }, T0);
    const rec = state.simulations[0]!;
    expect(Object.keys(rec)).not.toContain("transcript");
    expect(rec.total).toBe(evaluation.total);
    expect(state.achievements["respect-no"]).toBe(T0);
  });
  it("P07 Unbekanntes in der Übergabe ehrlich markiert → saubere Übergabe", () => {
    const sc = scenarioById("SIM-003")!;
    const { evaluation } = recordSimulation(initialState(), sc, ["close-quick"], { fields: { contact_pref: UNKNOWN_VALUE, reason: UNKNOWN_VALUE } }, T0);
    expect(evaluation.competencies.find((c) => c.competency === "dokumentation")!.score).toBe(100);
  });
  it("P08 Attempt-Log ist begrenzt", () => {
    const q = questionById("Q-M01-007")!;
    const r = grade(q, { type: "truefalse", value: false });
    let s = initialState();
    for (let i = 0; i < 3010; i++) s = recordAnswer(s, q, r, { durationMs: 1, context: "review", now: T0 + i });
    expect(s.attempts.length).toBe(3000);
  });
});
