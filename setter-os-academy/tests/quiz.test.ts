// Fachliche Regressionstests der Quiz-Engine (gegen echte Kursfragen aus content/questions).
import { describe, expect, it } from "vitest";
import { questionById, questions } from "@/lib/content";
import { grade, normalizeText, parseNumber, scoreAttempt } from "@/lib/engine/quiz";
import type { Question } from "@/lib/types";

const q = <T extends Question["type"]>(id: string, type: T) => {
  const x = questionById(id);
  if (!x || x.type !== type) throw new Error(`${id} is not ${type}`);
  return x as Extract<Question, { type: T }>;
};

describe("Single Choice", () => {
  it("R01 Rollenfrage: richtige Antwort b", () => {
    expect(grade(q("Q-M01-001", "single"), { type: "single", optionId: "b" }).correct).toBe(true);
  });
  it("R02 Rollenverwechslung wird als Fehlerkategorie erkannt", () => {
    const r = grade(q("Q-M01-001", "single"), { type: "single", optionId: "a" });
    expect(r.correct).toBe(false);
    expect(r.errorCategories).toContain("rollenverwechslung");
  });
  it("R03 Menge-statt-Qualität-Distraktor = Qualifizierungsfehler", () => {
    expect(grade(q("Q-M01-001", "single"), { type: "single", optionId: "c" }).errorCategories).toEqual(["qualifizierungsfehler"]);
  });
  it("R04 Recht B2C: mutmaßliche Einwilligung ist falsch (Rechtsfehler)", () => {
    const r = grade(q("Q-M01-010", "single"), { type: "single", optionId: "b" });
    expect(r.score).toBe(0);
    expect(r.errorCategories).toContain("rechtsfehler");
  });
  it("R05 Recht B2C: ausdrückliche dokumentierte Einwilligung ist richtig", () => {
    expect(grade(q("Q-M01-010", "single"), { type: "single", optionId: "c" }).score).toBe(1);
  });
  it("R06 Offene Frage erkannt, Mehrfachfrage ist Kommunikationsfehler", () => {
    expect(grade(q("Q-M01-014", "single"), { type: "single", optionId: "c" }).correct).toBe(true);
    expect(grade(q("Q-M01-014", "single"), { type: "single", optionId: "d" }).errorCategories).toContain("kommunikationsfehler");
  });
  it("R07 Steuerfrage: Weiterleitung ist richtig", () => {
    expect(grade(q("Q-M01-025", "single"), { type: "single", optionId: "b" }).correct).toBe(true);
  });
  it("R08 Mitentscheider: Termin mit beiden ist richtig", () => {
    expect(grade(q("Q-M01-021", "single"), { type: "single", optionId: "b" }).correct).toBe(true);
    expect(grade(q("Q-M01-021", "single"), { type: "single", optionId: "d" }).errorCategories).toContain("ethikfehler");
  });
  it("R09 Manipulationsdefinition", () => {
    expect(grade(q("Q-M01-028", "single"), { type: "single", optionId: "b" }).correct).toBe(true);
  });
  it("R10 Unbekannte Option = 0 Punkte, kein Absturz", () => {
    expect(grade(q("Q-M01-009", "single"), { type: "single", optionId: "zzz" }).score).toBe(0);
  });
  it("R11 Falscher Antworttyp wird abgefangen", () => {
    expect(grade(q("Q-M01-009", "single"), { type: "truefalse", value: true }).score).toBe(0);
  });
});

describe("Multiple Choice / Negationsfragen", () => {
  it("R12 Negationsfrage ist als solche markiert", () => {
    expect(q("Q-M01-004", "multi").negation).toBe(true);
  });
  it("R13 Negationsfrage: exakt die NICHT-Setter-Aufgaben = voll", () => {
    expect(grade(q("Q-M01-004", "multi"), { type: "multi", optionIds: ["a", "c", "e"] }).score).toBe(1);
  });
  it("R14 Negationsfrage: Setter-Aufgabe mitgewählt = Abzug + Rollenverwechslung", () => {
    const r = grade(q("Q-M01-004", "multi"), { type: "multi", optionIds: ["a", "b", "c", "e"] });
    expect(r.score).toBeCloseTo(2 / 3, 2);
    expect(r.errorCategories).toContain("rollenverwechslung");
  });
  it("R15 'Alles auswählen' wird nicht belohnt", () => {
    const all = q("Q-M01-017", "multi").options.map((o) => o.id);
    const r = grade(q("Q-M01-017", "multi"), { type: "multi", optionIds: all });
    expect(r.correct).toBe(false);
    expect(r.score).toBeLessThanOrEqual(0.5);
  });
  it("R16 Teilmenge gibt Teilpunkte, nie volle Punkte", () => {
    const r = grade(q("Q-M01-017", "multi"), { type: "multi", optionIds: ["a", "b"] });
    expect(r.score).toBe(0.5);
    expect(r.correct).toBe(false);
    expect(r.errorCategories).toContain("unvollstaendig");
  });
  it("R17 Leere Auswahl = 0", () => {
    expect(grade(q("Q-M01-011", "multi"), { type: "multi", optionIds: [] }).score).toBe(0);
  });
  it("R18 Reihenfolge der Auswahl ist egal", () => {
    expect(grade(q("Q-M01-024", "multi"), { type: "multi", optionIds: ["d", "a", "b"] }).score).toBe(1);
  });
  it("R19 Seriöse Formulierung als unzulässig markiert = Ethik-Denkfehler", () => {
    const r = grade(q("Q-M01-024", "multi"), { type: "multi", optionIds: ["a", "b", "d", "c"] });
    expect(r.correct).toBe(false);
  });
});

describe("Richtig/Falsch, Zuordnung, Reihenfolge, Lückentext", () => {
  it("R20 LinkedIn-Vernetzung ist keine Einwilligung", () => {
    expect(grade(q("Q-M01-012", "truefalse"), { type: "truefalse", value: false }).correct).toBe(true);
    expect(grade(q("Q-M01-012", "truefalse"), { type: "truefalse", value: true }).errorCategories).toEqual(["rechtsfehler"]);
  });
  it("R21 BANT ist nicht wissenschaftlich überlegen", () => {
    expect(grade(q("Q-M01-022", "truefalse"), { type: "truefalse", value: false }).correct).toBe(true);
  });
  it("R22 Rollen-Zuordnung komplett richtig", () => {
    const m = q("Q-M01-003", "matching");
    expect(grade(m, { type: "matching", pairs: m.pairs }).score).toBe(1);
  });
  it("R23 SDR/BDR vertauscht = 50 %", () => {
    expect(grade(q("Q-M01-003", "matching"), { type: "matching", pairs: { setter: "r1", closer: "r2", sdr: "r4", bdr: "r3" } }).score).toBe(0.5);
  });
  it("R24 Lead-Status-Zuordnung: Nein = Kein Interesse", () => {
    const r = grade(q("Q-M01-018", "matching"), { type: "matching", pairs: { s1: "nurture", s2: "termin", s3: "nurture", s4: "disq" } });
    expect(r.score).toBe(0.75);
  });
  it("R25 Funnel-Reihenfolge korrekt", () => {
    expect(grade(q("Q-M01-006", "ordering"), { type: "ordering", order: ["lead", "qualified", "booked", "shown", "won"] }).score).toBe(1);
  });
  it("R26 Ein vertauschtes Paar gibt Teilpunkte, nicht voll", () => {
    const r = grade(q("Q-M01-006", "ordering"), { type: "ordering", order: ["lead", "booked", "qualified", "shown", "won"] });
    expect(r.score).toBeGreaterThan(0.5);
    expect(r.correct).toBe(false);
  });
  it("R27 Unvollständige Reihenfolge = 0", () => {
    expect(grade(q("Q-M01-013", "ordering"), { type: "ordering", order: ["open", "need"] }).score).toBe(0);
  });
  it("R28 Lückentext akzeptiert Groß-/Kleinschreibung und Varianten", () => {
    const r = grade(q("Q-M01-015", "cloze"), { type: "cloze", gaps: { g1: "Offene", g2: " geschlossene ", g3: "suggestivfragen" } });
    expect(r.score).toBe(1);
  });
  it("R29 Lückentext: eine falsche Lücke = 2/3", () => {
    expect(grade(q("Q-M01-015", "cloze"), { type: "cloze", gaps: { g1: "offene", g2: "rhetorische", g3: "Suggestivfragen" } }).score).toBeCloseTo(0.667, 2);
  });
});

describe("Situation, Fehlererkennung, CRM, Kennzahlen", () => {
  it("R30 Situationsfrage: beste Option = 1, akzeptable = 0,5", () => {
    expect(grade(q("Q-M01-002", "situation"), { type: "situation", optionId: "b" }).score).toBe(1);
    expect(grade(q("Q-M01-002", "situation"), { type: "situation", optionId: "c" }).score).toBe(0.5);
  });
  it("R31 Erfundener Rabatt ist inakzeptabel (Ethikfehler)", () => {
    const r = grade(q("Q-M01-002", "situation"), { type: "situation", optionId: "d" });
    expect(r.score).toBe(0);
    expect(r.errorCategories).toContain("ethikfehler");
  });
  it("R32 Nein ignorieren ist inakzeptabel", () => {
    expect(grade(q("Q-M01-023", "situation"), { type: "situation", optionId: "a" }).score).toBe(0);
    expect(grade(q("Q-M01-023", "situation"), { type: "situation", optionId: "b" }).score).toBe(1);
  });
  it("R33 Budget vermuten = Überinterpretation", () => {
    expect(grade(q("Q-M01-020", "situation"), { type: "situation", optionId: "a" }).errorCategories).toContain("ueberinterpretation");
  });
  it("R34 Fehlererkennung: alle drei Fehler = voll", () => {
    expect(grade(q("Q-M01-016", "errorspot"), { type: "errorspot", lineIds: ["l2", "l3", "l5"] }).score).toBe(1);
  });
  it("R35 Fehlererkennung: Fehlalarm wird abgezogen", () => {
    const r = grade(q("Q-M01-016", "errorspot"), { type: "errorspot", lineIds: ["l1", "l2", "l3", "l5"] });
    expect(r.score).toBeCloseTo(2 / 3, 2);
  });
  it("R36 Fehlererkennung: alles markieren lohnt sich nicht", () => {
    const r = grade(q("Q-M01-016", "errorspot"), { type: "errorspot", lineIds: ["l1", "l2", "l3", "l4", "l5"] });
    expect(r.score).toBeLessThanOrEqual(0.34);
  });
  it("R37 CRM-Aufgabe korrekt", () => {
    expect(
      grade(q("Q-M01-019", "crm"), { type: "crm", fields: { status: "Termin gebucht", next: "Terminerinnerung 24 h vorher senden", authority: "Ja" } }).score,
    ).toBe(1);
  });
  it("R38 CRM-Aufgabe: falscher Status = Prozessfehler", () => {
    const r = grade(q("Q-M01-019", "crm"), { type: "crm", fields: { status: "Qualifiziert", next: "Terminerinnerung 24 h vorher senden", authority: "Ja" } });
    expect(r.score).toBeCloseTo(0.667, 2);
    expect(r.errorCategories).toContain("prozessfehler");
  });
  it("R39 Show Rate = 75 %", () => {
    expect(grade(q("Q-M01-008", "calculation"), { type: "calculation", value: 75 }).correct).toBe(true);
  });
  it("R40 Show Rate mit falscher Bezugsgröße (15 %) = Rechenfehler", () => {
    const r = grade(q("Q-M01-008", "calculation"), { type: "calculation", value: 15 });
    expect(r.correct).toBe(false);
    expect(r.errorCategories).toEqual(["rechenfehler"]);
  });
  it("R41 Lead-to-Appointment 24 % innerhalb Toleranz", () => {
    expect(grade(q("Q-M01-029", "calculation"), { type: "calculation", value: 24.4 }).correct).toBe(true);
    expect(grade(q("Q-M01-029", "calculation"), { type: "calculation", value: 66.7 }).correct).toBe(false);
  });
  it("R42 NaN-Eingabe wird abgelehnt", () => {
    expect(grade(q("Q-M01-029", "calculation"), { type: "calculation", value: Number.NaN }).correct).toBe(false);
  });
  it("R43 Zahlen im deutschen Format werden gelesen", () => {
    expect(parseNumber("24,5 %")).toBe(24.5);
    expect(parseNumber("1.250,5")).toBe(1250.5);
    expect(parseNumber("abc")).toBeNull();
  });
});

describe("Freitext – transparent und immer manuell zu prüfen", () => {
  const ft = () => q("Q-M01-030", "freetext");
  it("R44 Musterlösung erfüllt alle Kriterien", () => {
    const r = grade(ft(), { type: "freetext", text: ft().sampleAnswer });
    expect(r.score).toBe(1);
    expect(r.needsManualReview).toBe(true);
  });
  it("R45 Druckformulierung lässt Kriterium scheitern", () => {
    const r = grade(ft(), { type: "freetext", text: "Hallo Frau Lenz, SolarNord hier zu Ihrer Anfrage. Nur heute: Was wollen Sie? Kurz Zeit?" });
    expect(r.score).toBeLessThan(1);
    expect(r.errorCategories).toContain("ethikfehler");
  });
  it("R46 Zu kurze Antwort wird nicht bewertet", () => {
    expect(grade(ft(), { type: "freetext", text: "Hallo" }).score).toBe(0);
  });
  it("R47 Freitext zählt nicht in die automatische Bestehensquote", () => {
    const r1 = grade(ft(), { type: "freetext", text: ft().sampleAnswer });
    const r2 = grade(q("Q-M01-007", "truefalse"), { type: "truefalse", value: true });
    const s = scoreAttempt([r1, r2], 0.8);
    expect(s.autoGraded).toBe(1);
    expect(s.pendingManualReview).toBe(1);
  });
});

describe("Determinismus und Bestehensregeln", () => {
  it("R48 Gleiche Antwort → identisches Ergebnis (100 Wiederholungen)", () => {
    const question = q("Q-M01-017", "multi");
    const first = JSON.stringify(grade(question, { type: "multi", optionIds: ["a", "e"] }));
    for (let i = 0; i < 100; i++) expect(JSON.stringify(grade(question, { type: "multi", optionIds: ["a", "e"] }))).toBe(first);
  });
  it("R49 Bestehensgrenze 80 % ist inklusiv", () => {
    const mk = (score: number) => ({ questionId: "x", score, correct: score === 1, needsManualReview: false, errorCategories: [], feedback: [] });
    expect(scoreAttempt([mk(1), mk(1), mk(1), mk(1), mk(0)], 0.8).passed).toBe(true);
    expect(scoreAttempt([mk(1), mk(1), mk(1), mk(0.9), mk(0)], 0.8).passed).toBe(false);
  });
  it("R50 Jede Kursfrage ist mit ihrer Musterlösung voll lösbar", () => {
    for (const x of questions) {
      const a = solution(x);
      if (!a) continue;
      expect(grade(x, a).score, x.id).toBe(1);
    }
  });
  it("R51 Text-Normalisierung vereinheitlicht Umlaute", () => {
    expect(normalizeText("  Größe   ÄRGER!")).toBe("groesse aerger");
  });
});

function solution(x: Question) {
  switch (x.type) {
    case "single": return { type: "single" as const, optionId: x.correct };
    case "multi": return { type: "multi" as const, optionIds: x.correct };
    case "truefalse": return { type: "truefalse" as const, value: x.correct };
    case "matching": return { type: "matching" as const, pairs: x.pairs };
    case "ordering": return { type: "ordering" as const, order: x.correctOrder };
    case "cloze": return { type: "cloze" as const, gaps: Object.fromEntries(x.gaps.map((g) => [g.id, g.accepted[0]!])) };
    case "situation": return { type: "situation" as const, optionId: x.options.find((o) => o.quality === "best")!.id };
    case "errorspot": return { type: "errorspot" as const, lineIds: x.lines.filter((l) => l.faulty).map((l) => l.id) };
    case "calculation": return { type: "calculation" as const, value: x.correctValue };
    case "crm": return { type: "crm" as const, fields: Object.fromEntries(x.fields.map((f) => [f.id, f.correct])) };
    case "freetext": return { type: "freetext" as const, text: x.sampleAnswer };
  }
}

describe("Fallanalyse (case)", () => {
  const q = questions.find((x) => x.id === "Q-M01-043")!;
  it("Q-CASE-1 alle Teile richtig = 100 %", () => {
    if (q.type !== "case") throw new Error("type");
    const r = grade(q, { type: "case", answers: Object.fromEntries(q.parts.map((p) => [p.id, p.correct])) });
    expect(r.correct).toBe(true);
  });
  it("Q-CASE-2 Teilpunkte je Teilfrage, Denkfehler im Feedback", () => {
    if (q.type !== "case") throw new Error("type");
    const answers = Object.fromEntries(q.parts.map((p, i) => [p.id, i === 0 ? p.options.find((o) => o.id !== p.correct)!.id : p.correct]));
    const r = grade(q, { type: "case", answers });
    expect(r.score).toBeCloseTo(2 / 3, 2);
    expect(r.feedback[0]).toMatch(/Denkfehler/);
    expect(r.errorCategories.length).toBeGreaterThan(0);
  });
  it("Q-CASE-3 falsches Antwortformat wird abgelehnt", () => {
    expect(grade(q, { type: "single", optionId: "a" }).score).toBe(0);
  });
});
