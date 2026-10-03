// Szenario- und Bewertungs-Regressionstests (Customer Simulator + Coach).
import { describe, expect, it } from "vitest";
import { scenarioById, scenarios } from "@/lib/content";
import { evaluate, COMPETENCIES, UNKNOWN_VALUE } from "@/lib/engine/coach";
import { applyMove, availableMoves, replay, startSimulation } from "@/lib/engine/customer";
import type { HandoverNote, Scenario, SimulationState } from "@/lib/types";

const sc = (id: string) => scenarioById(id)!;

/** Honest handover: documents exactly what was revealed, "unknown" otherwise. */
function honestNote(s: Scenario, st: SimulationState): HandoverNote {
  return {
    fields: Object.fromEntries(
      s.handoverFields.map((k) => [k, st.revealed.includes(k) ? s.facts.find((f) => f.key === k)!.value : UNKNOWN_VALUE]),
    ),
  };
}
function run(id: string, moves: string[], note?: (s: Scenario, st: SimulationState) => HandoverNote) {
  const s = sc(id);
  const st = replay(s, moves);
  return { s, st, ev: evaluate(s, st, (note ?? honestNote)(s, st)) };
}

const SIM1_BEST = ["open-good", "need-open", "ownership", "timeline", "funding-handoff", "authority", "summary", "propose", "slots", "confirm"];

describe("Customer Simulator – Zustandsmaschine", () => {
  it("S01 Start enthält nur die Eröffnungsnachricht des Kunden", () => {
    const st = startSimulation(sc("SIM-001"));
    expect(st.transcript).toHaveLength(1);
    expect(st.transcript[0]!.role).toBe("customer");
    expect(st.revealed).toEqual([]);
  });
  it("S02 Versteckte Infos werden erst durch passende Fragen sichtbar", () => {
    const s = sc("SIM-001");
    let st = applyMove(s, startSimulation(s), "open-good");
    expect(st.revealed).not.toContain("authority");
    st = applyMove(s, st, "authority");
    expect(st.revealed).toContain("authority");
  });
  it("S03 Züge mit Voraussetzungen sind vorher nicht verfügbar", () => {
    const s = sc("SIM-001");
    const ids = availableMoves(s, startSimulation(s)).map((m) => m.id);
    expect(ids).toEqual(["open-good", "open-weak"]);
  });
  it("S04 Nicht verfügbarer Zug wirft einen Fehler", () => {
    const s = sc("SIM-001");
    expect(() => applyMove(s, startSimulation(s), "confirm")).toThrow();
  });
  it("S05 Förderfrage taucht erst nach der Zeitrahmen-Frage auf", () => {
    const s = sc("SIM-001");
    const st = replay(s, ["open-good", "need-open", "timeline"]);
    expect(st.flags).toContain("asked-funding");
    expect(availableMoves(s, st).map((m) => m.id)).toContain("funding-handoff");
  });
  it("S06 Mehrere sinnvolle Verläufe führen zum Termin (Reihenfolge variabel)", () => {
    const a = run("SIM-001", SIM1_BEST);
    const b = run("SIM-001", ["open-good", "authority", "ownership", "need-open", "timeline", "funding-handoff", "summary", "propose", "slots", "confirm"]);
    expect(a.st.outcome).toBe("book");
    expect(b.st.outcome).toBe("book");
    expect(a.ev.passed && b.ev.passed).toBe(true);
  });
  it("S07 Replay ist deterministisch", () => {
    expect(JSON.stringify(replay(sc("SIM-001"), SIM1_BEST))).toBe(JSON.stringify(replay(sc("SIM-001"), SIM1_BEST)));
  });
  it("S08 Feindseliger Kunde (Rapport ≤ 1) gibt keine Informationen preis", () => {
    const s = sc("SIM-002");
    const st = replay(s, ["open-pitch", "budget-leading", "budget-good"]);
    // rapport 5 -1 -1 = 3 → still shares; push further down to verify the rule
    expect(st.revealed).toContain("budget");
    const hostile = { ...startSimulation(s), rapport: 1, flags: ["opened"] };
    const after = applyMove(s, hostile, "authority");
    expect(after.revealed).not.toContain("authority");
  });
  it("S12 Explizite Kundenaussage gilt auch bei niedrigem Rapport als erfahren", () => {
    const s = sc("SIM-003");
    const st = replay(s, ["why-not", "apologize-close"]);
    expect(st.rapport).toBeLessThanOrEqual(1);
    expect(st.revealed).toContain("contact_pref");
  });
  it("S09 Maximale Züge beenden das Gespräch als 'lost'", () => {
    const s = { ...sc("SIM-003"), maxTurns: 1 };
    const st = applyMove(s, startSimulation(s), "why-not");
    expect(st.finished).toBe(true);
    expect(st.outcome).toBe("lost");
  });
  it("S10 Jedes Szenario hat mindestens einen bestehbaren Pfad (Breitensuche)", () => {
    for (const s of scenarios) expect(findPassingPath(s), s.id).not.toBeNull();
  });
  it("S11 In jedem Szenario existieren Pfade, die durch ein Gate scheitern", () => {
    for (const s of scenarios) expect(hasGateFailure(s), s.id).toBe(true);
  });
});

describe("Coach – Bewertungslogik", () => {
  it("C01 Bester Pfad SIM-001 besteht mit hoher Punktzahl", () => {
    const { ev } = run("SIM-001", SIM1_BEST);
    expect(ev.passed).toBe(true);
    expect(ev.total).toBeGreaterThanOrEqual(85);
    expect(ev.gates.every((g) => !g.triggered)).toBe(true);
  });
  it("C02 Gewichte summieren sich auf 100", () => {
    expect(COMPETENCIES.reduce((a, c) => a + c.weight, 0)).toBe(100);
  });
  it("C03 Termin ohne Entscheider-Klärung: Gate G2, nicht bestanden", () => {
    const { ev, st } = run("SIM-001", ["open-good", "need-open", "propose", "slots", "confirm"]);
    expect(st.outcome).toBe("book");
    expect(ev.gates.find((g) => g.id === "G2")!.triggered).toBe(true);
    expect(ev.passed).toBe(false);
    expect(ev.total).toBeLessThanOrEqual(60);
  });
  it("C04 Förderzusage = Verstoß, Gate G1 trotz gebuchtem Termin", () => {
    const moves = SIM1_BEST.map((m) => (m === "funding-handoff" ? "funding-promise" : m));
    const { ev, st } = run("SIM-001", moves);
    expect(st.outcome).toBe("book");
    expect(ev.gates.find((g) => g.id === "G1")!.triggered).toBe(true);
    expect(ev.total).toBeLessThanOrEqual(40);
    expect(ev.competencies.find((c) => c.competency === "recht_ethik")!.score).toBe(0);
  });
  it("C05 Druck-Buchung beendet Gespräch und scheitert", () => {
    const { ev, st } = run("SIM-001", ["open-good", "pressure-book"]);
    expect(st.outcome).toBe("lost");
    expect(ev.passed).toBe(false);
  });
  it("C06 Erfundene Angaben in der Übergabe: Gate G4", () => {
    const { ev } = run("SIM-001", ["open-good", "need-open", "nurture"], (s) => ({
      fields: Object.fromEntries(s.handoverFields.map((k) => [k, s.facts.find((f) => f.key === k)!.value])),
    }));
    expect(ev.gates.find((g) => g.id === "G4")!.triggered).toBe(true);
  });
  it("C07 Ehrliches 'Nicht erfragt' wird als korrekte Dokumentation gewertet", () => {
    const { ev, st } = run("SIM-002", ["open-good", "budget-good", "disqualify"]);
    expect(st.revealed).not.toContain("authority");
    expect(ev.competencies.find((c) => c.competency === "dokumentation")!.score).toBe(100);
    expect(ev.gates.find((g) => g.id === "G4")!.triggered).toBe(false);
  });
  it("C08 SIM-002: Saubere Disqualifizierung besteht", () => {
    const { ev, st } = run("SIM-002", ["open-good", "need-deepen", "authority", "budget-good", "disqualify"]);
    expect(st.outcome).toBe("disqualify");
    expect(ev.passed).toBe(true);
  });
  it("C09 SIM-002: Termin trotz fehlendem Budget = Gate G3", () => {
    const { ev, st } = run("SIM-002", ["open-good", "authority", "budget-good", "book-anyway"]);
    expect(st.outcome).toBe("book");
    expect(ev.gates.find((g) => g.id === "G3")!.triggered).toBe(true);
    expect(ev.passed).toBe(false);
  });
  it("C10 SIM-002: Unbelegtes Erfolgsversprechen in der Eröffnung = Verstoß", () => {
    const { ev } = run("SIM-002", ["open-pitch", "need-ask", "authority", "budget-good", "disqualify"]);
    expect(ev.gates.find((g) => g.id === "G1")!.triggered).toBe(true);
  });
  it("C11 SIM-003: Nein respektieren besteht", () => {
    const { ev, st } = run("SIM-003", ["ack-clarify", "close-respectful"]);
    expect(st.outcome).toBe("respect_no");
    expect(ev.passed).toBe(true);
    expect(ev.total).toBeGreaterThanOrEqual(85);
  });
  it("C12 SIM-003: Nachbohren nach Nein = Verstoß, auch wenn danach entschuldigt", () => {
    const { ev, st } = run("SIM-003", ["why-not", "apologize-close"]);
    expect(st.outcome).toBe("respect_no");
    expect(ev.passed).toBe(false);
    expect(ev.gates.find((g) => g.id === "G1")!.triggered).toBe(true);
  });
  it("C13 SIM-003: Folgekontakt gegen Widerspruch scheitert", () => {
    const { ev } = run("SIM-003", ["ack-clarify", "later-followup"]);
    expect(ev.passed).toBe(false);
  });
  it("C14 Feedback hat immer 3 Stärken und 3 Verbesserungen", () => {
    for (const path of [SIM1_BEST, ["open-weak", "pressure-book"]]) {
      const { ev } = run("SIM-001", path);
      expect(ev.strengths).toHaveLength(3);
      expect(ev.improvements).toHaveLength(3);
    }
  });
  it("C15 Verbesserte Beispielantwort: schwerster Fehler zuerst", () => {
    const { ev } = run("SIM-001", ["open-weak", "need-leading", "need-open", "pressure-book"]);
    expect(ev.improvedExample!.original).toContain("einfach für morgen");
    expect(ev.improvedExample!.better).toContain("Beratungsgespräch");
    const weakOnly = run("SIM-001", ["open-weak", "need-open", "nurture"]).ev;
    expect(weakOnly.improvedExample!.better).toContain("WärmeWerk Nord");
  });
  it("C16 Wiederholungsübungen werden verlinkt", () => {
    expect(run("SIM-001", SIM1_BEST).ev.reviewQuestionIds.length).toBeGreaterThan(0);
  });
  it("C17 Nicht getestete Kompetenzen fließen nicht in die Gesamtnote ein", () => {
    const { ev } = run("SIM-003", ["ack-clarify", "close-respectful"]);
    expect(ev.competencies.find((c) => c.competency === "einwaende")!.tested).toBe(false);
  });
  it("C18 Konsistenz: identische Eingabe → identische Bewertung (50×)", () => {
    const ref = JSON.stringify(run("SIM-002", ["open-good", "budget-good", "disqualify"]).ev);
    for (let i = 0; i < 50; i++) expect(JSON.stringify(run("SIM-002", ["open-good", "budget-good", "disqualify"]).ev)).toBe(ref);
  });
  it("C19 Fairness: Name/Persona des Kunden beeinflusst die Bewertung nicht", () => {
    const s = sc("SIM-001");
    const variants = ["Selin Kaya", "Hans Müller", "Aylin Demir", "Jean-Pierre N'Diaye"];
    const scores = variants.map((name) => {
      const v: Scenario = { ...s, persona: { ...s.persona, name } };
      const st = replay(v, SIM1_BEST);
      return evaluate(v, st, honestNote(v, st)).total;
    });
    expect(new Set(scores).size).toBe(1);
  });
  it("C20 Ein gebuchter Termin hebt keinen Verstoß auf (Termin + Verstoß < kein Termin + sauber)", () => {
    const bookedWithViolation = run("SIM-001", SIM1_BEST.map((m) => (m === "funding-handoff" ? "funding-promise" : m))).ev.total;
    const nurtureClean = run("SIM-001", ["open-good", "need-open", "nurture"]).ev.total;
    expect(bookedWithViolation).toBeLessThan(nurtureClean);
  });
});

// ---------- helpers: exhaustive search over the (small) move graph ----------
function* paths(s: Scenario, st: SimulationState, depth: number, acc: string[] = []): Generator<{ moves: string[]; st: SimulationState }> {
  if (st.finished || depth === 0) {
    yield { moves: acc, st };
    return;
  }
  for (const m of availableMoves(s, st)) yield* paths(s, applyMove(s, st, m.id), depth - 1, [...acc, m.id]);
}
function findPassingPath(s: Scenario): string[] | null {
  let n = 0;
  for (const p of paths(s, startSimulation(s), s.maxTurns)) {
    if (++n > 200_000) break;
    if (p.st.finished && evaluate(s, p.st, honestNote(s, p.st)).passed) return p.moves;
  }
  return null;
}
function hasGateFailure(s: Scenario): boolean {
  let n = 0;
  for (const p of paths(s, startSimulation(s), 4)) {
    if (++n > 50_000) break;
    if (p.st.finished && evaluate(s, p.st, honestNote(s, p.st)).gates.some((g) => g.triggered && g.id !== "G5")) return true;
  }
  return false;
}
