// 90-Tage-Plan: Freischaltung, Kalender-Abstand, Stufen-Check.
import { describe, expect, it } from "vitest";
import { program, questionById, scenarioById } from "@/lib/content";
import { UNKNOWN_VALUE } from "@/lib/engine/coach";
import { dayState, currentDay, stageCheckPassed } from "@/lib/engine/program";
import { grade } from "@/lib/engine/quiz";
import { completeLesson, completeProgramDay, fastTrackDay, initialState, migrate, recordAnswer, recordQuizAttempt, recordReviewSession, recordSimulation, startProgram, type AcademyState } from "@/lib/store/state";

const DAY = 86_400_000;
const T0 = new Date(2026, 9, 5, 9, 0).getTime(); // local 09:00

function doDay(s: AcademyState, day: number, now: number): AcademyState {
  const d = program[0]!.days.find((x) => x.day === day)!;
  for (const it of d.items) {
    if (it.type === "lesson") s = completeLesson(s, it.ref, "t", now);
    if (it.type === "review") s = recordReviewSession(s, now);
    if (it.type === "quiz" && !it.ref.startsWith("ST"))
      s = recordQuizAttempt(s, { id: `q-${day}`, moduleId: it.ref, kind: "module-exam", at: now, percent: 60, passed: false, courseVersion: "t", questionVersions: {}, scores: {}, pendingManualReview: 0 });
    if (it.type === "simulation") s = recordSimulation(s, scenarioById(it.ref)!, [], { fields: {} }, now).state;
  }
  return s;
}

describe("90-Tage-Plan", () => {
  it("P1 Ohne Start ist Tag 1 gesperrt", () => {
    expect(dayState(initialState(), program, 1, T0).status).toBe("locked");
  });
  it("P2 Nach Start ist Tag 1 offen, Tag 2 gesperrt", () => {
    const s = startProgram(initialState(), T0);
    expect(dayState(s, program, 1, T0).status).toBe("open");
    expect(dayState(s, program, 2, T0).status).toBe("locked");
  });
  it("P3 Tag lässt sich erst abschließen, wenn alle Pflichtpunkte erledigt sind", () => {
    let s = startProgram(initialState(), T0);
    const before = dayState(s, program, 1, T0);
    expect(before.status === "open" && before.allDone).toBe(false);
    s = doDay(s, 1, T0 + 1000);
    const after = dayState(s, program, 1, T0 + 2000);
    expect(after.status === "open" && after.allDone).toBe(true);
  });
  it("P4 Nächster Tag öffnet erst am nächsten Kalendertag – außer bei ausdrücklichem Vorziehen", () => {
    let s = doDay(startProgram(initialState(), T0), 1, T0);
    s = completeProgramDay(s, 1, T0 + 1000);
    const same = dayState(s, program, 2, T0 + 2000);
    expect(same.status).toBe("locked");
    expect(same.status === "locked" && same.canFastTrack).toBe(true);
    expect(dayState(s, program, 2, T0 + DAY).status).toBe("open");
    expect(dayState(fastTrackDay(s, 2), program, 2, T0 + 2000).status).toBe("open");
  });
  it("P5 Stufe 2 bleibt ohne bestandenen Stufen-Check gesperrt", () => {
    let s = startProgram(initialState(), T0);
    for (let d = 1; d <= 7; d++) {
      s = doDay(s, d, T0 + (d - 1) * DAY);
      s = completeProgramDay(s, d, T0 + (d - 1) * DAY + 1000);
    }
    expect(stageCheckPassed(s, program[0]!)).toBe(false);
    const d8 = dayState(s, program, 8, T0 + 10 * DAY);
    expect(d8.status).toBe("locked");
  });
  it("P6 Stufen-Check verlangt Quiz UND bestandene Pflichtsimulationen", () => {
    let s = initialState();
    s = recordQuizAttempt(s, { id: "c", moduleId: "ST1", kind: "stage-check", at: T0, percent: 90, passed: true, courseVersion: "t", questionVersions: {}, scores: {}, pendingManualReview: 0 });
    expect(stageCheckPassed(s, program[0]!)).toBe(false);
    s = recordSimulation(s, scenarioById("SIM-003")!, ["ack-clarify", "close-respectful"], { fields: { contact_pref: "Keine weiteren Werbenachrichten", reason: "Informiert sich nur, Projekt frühestens in einigen Jahren" } }, T0).state;
    const sim4 = scenarioById("SIM-004")!;
    const moves = ["open-label", "need", "paraphrase", "pv", "follow-day", "timeline", "authority", "propose", "slots", "confirm"];
    const facts = Object.fromEntries(sim4.handoverFields.map((k) => [k, sim4.facts.find((f) => f.key === k)!.value]));
    const r = recordSimulation(s, sim4, moves, { fields: facts }, T0);
    expect(r.evaluation.passed).toBe(true);
    expect(stageCheckPassed(r.state, program[0]!)).toBe(true);
  });
  it("P7 Stufe 2+ ist ehrlich als in Vorbereitung gesperrt", () => {
    const d = dayState(startProgram(initialState(), T0), program, 30, T0);
    expect(d.status === "locked" && d.reason).toContain("ausgearbeitet");
  });
  it("P8 Aktueller Tag ist der erste nicht abgeschlossene", () => {
    let s = startProgram(initialState(), T0);
    expect(currentDay(s, program)).toBe(1);
    s = completeProgramDay(s, 1, T0);
    expect(currentDay(s, program)).toBe(2);
  });
  it("P9 Migration v2 → v3 ergänzt den Plan", () => {
    const s = migrate({ ...initialState(), schemaVersion: 2, program: undefined });
    expect(s.program.startedAt).toBeNull();
  });
  it("P10 Wiederholung gilt als erledigt, wenn nichts fällig ist", () => {
    const s = startProgram(initialState(), T0);
    const d2 = { ...s, program: { ...s.program, dayCompletedAt: { 1: T0 } }, lessonsCompleted: { "M01-L04": { at: T0, courseVersion: "t" }, "M01-L05": { at: T0, courseVersion: "t" } } };
    const st = dayState(d2, program, 2, T0 + DAY);
    expect(st.status === "open" && st.allDone).toBe(true);
    const q = questionById("Q-M01-007")!;
    const withDue = recordAnswer(d2, q, grade(q, { type: "truefalse", value: false }), { durationMs: 1, context: "quiz", now: T0 - DAY * 2 });
    const st2 = dayState(withDue, program, 2, T0 + DAY);
    expect(st2.status === "open" && st2.allDone).toBe(false);
  });
});

describe("SIM-004 Unsichere Kundin", () => {
  it("S-U1 Technikaussage ist ein Verstoß", () => {
    const sc = scenarioById("SIM-004")!;
    const r = recordSimulation(initialState(), sc, ["open-label", "pv", "tech-explain", "nurture"], { fields: Object.fromEntries(sc.handoverFields.map((k) => [k, UNKNOWN_VALUE])) }, T0);
    expect(r.evaluation.gates.find((g) => g.id === "G1")!.triggered).toBe(true);
  });
});
