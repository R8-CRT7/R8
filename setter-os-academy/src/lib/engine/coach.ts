// AI SALES COACH (deterministic version) – evaluates a finished simulation.
// Reads only the transcript/state + move metadata. Never writes customer replies.
// Rubric documented in ASSESSMENT_RUBRIC.md – keep both in sync (RUBRIC_VERSION).

import type {
  Competency,
  CompetencyScore,
  HandoverNote,
  Scenario,
  ScenarioMove,
  SimulationEvaluation,
  SimulationState,
} from "../types";

export const RUBRIC_VERSION = "1.0.0";
export const UNKNOWN_VALUE = "Nicht erfragt / unbekannt";
export const PASS_SCORE = 70;

export const COMPETENCIES: { id: Competency; label: string; weight: number; reviewLessonId: string }[] = [
  { id: "eroeffnung", label: "Gesprächseröffnung", weight: 8, reviewLessonId: "M01-L04" },
  { id: "bedarfsermittlung", label: "Bedarfsermittlung", weight: 14, reviewLessonId: "M01-L04" },
  { id: "fragetechnik", label: "Fragetechnik", weight: 10, reviewLessonId: "M01-L04" },
  { id: "zuhoeren", label: "Aktives Zuhören", weight: 8, reviewLessonId: "M01-L04" },
  { id: "klarheit", label: "Klarheit", weight: 6, reviewLessonId: "M01-L01" },
  { id: "qualifizierung", label: "Qualifizierung", weight: 16, reviewLessonId: "M01-L05" },
  { id: "einwaende", label: "Umgang mit Einwänden", weight: 10, reviewLessonId: "M01-L05" },
  { id: "kundenorientierung", label: "Kundenorientierung", weight: 8, reviewLessonId: "M01-L02" },
  { id: "terminvereinbarung", label: "Terminvereinbarung", weight: 8, reviewLessonId: "M01-L01" },
  { id: "dokumentation", label: "Dokumentation", weight: 6, reviewLessonId: "M01-L05" },
  { id: "recht_ethik", label: "Rechtliche & ethische Korrektheit", weight: 6, reviewLessonId: "M01-L06" },
];

const OUTCOME_LABEL: Record<string, string> = {
  book: "Termin gebucht",
  nurture: "Lead in Nurturing überführt",
  disqualify: "Lead sauber disqualifiziert",
  respect_no: "Nein respektiert, Gespräch höflich beendet",
  handoff: "An Fachberater übergeben",
  lost: "Gespräch ohne Ergebnis abgebrochen",
};

const clamp = (n: number, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, n));

function movesUsed(s: Scenario, st: SimulationState): ScenarioMove[] {
  return st.usedMoves.map((id) => s.moves.find((m) => m.id === id)!).filter(Boolean);
}

export function evaluateDocumentation(s: Scenario, st: SimulationState, note: HandoverNote) {
  let correct = 0;
  let fabricated = 0;
  const details: string[] = [];
  for (const key of s.handoverFields) {
    const fact = s.facts.find((f) => f.key === key)!;
    const chosen = note.fields[key] ?? UNKNOWN_VALUE;
    const known = st.revealed.includes(key);
    if (known && chosen === fact.value) correct++;
    else if (!known && chosen === UNKNOWN_VALUE) correct++;
    else if (!known && chosen !== UNKNOWN_VALUE) {
      fabricated++;
      details.push(`„${fact.label}“ wurde dokumentiert, obwohl es im Gespräch nie erfragt wurde.`);
    } else details.push(`„${fact.label}“ falsch oder nicht dokumentiert (im Gespräch: „${fact.value}“).`);
  }
  return { score: s.handoverFields.length ? (correct / s.handoverFields.length) * 100 : 100, fabricated, details };
}

export function evaluate(s: Scenario, st: SimulationState, note: HandoverNote): SimulationEvaluation {
  const used = movesUsed(s, st);
  const sums: Partial<Record<Competency, number>> = {};
  for (const m of used) for (const [k, v] of Object.entries(m.effects)) sums[k as Competency] = (sums[k as Competency] ?? 0) + (v ?? 0);

  const required = s.facts.filter((f) => f.requiredForQualification);
  const coverage = required.length ? required.filter((f) => st.revealed.includes(f.key)).length / required.length : 1;
  const violations = used.filter((m) => m.violation);
  const doc = evaluateDocumentation(s, st, note);
  const outcomeOk = st.outcome !== null && st.outcome !== "lost" && s.acceptableOutcomes.includes(st.outcome);
  const idealReached = st.outcome === s.idealOutcome;

  const comp: CompetencyScore[] = COMPETENCIES.map((c) => {
    const target = s.competencyTargets[c.id];
    let score = target ? clamp(((sums[c.id] ?? 0) / target) * 100) : 0;
    let tested = target !== undefined;
    if (c.id === "qualifizierung") {
      tested = true;
      const movePart = target ? score : coverage * 100;
      score = clamp(0.6 * coverage * 100 + 0.4 * movePart);
    }
    if (c.id === "terminvereinbarung") {
      tested = true;
      const base = target ? score : 0;
      score = clamp((idealReached ? 60 : outcomeOk ? 40 : 0) + 0.4 * base);
    }
    if (c.id === "dokumentation") {
      tested = true;
      score = doc.score;
    }
    if (c.id === "recht_ethik") {
      tested = true;
      score = violations.length ? 0 : 100;
    }
    return { competency: c.id, label: c.label, weight: c.weight, score: Math.round(score), tested };
  });

  const testedComp = comp.filter((c) => c.tested);
  const wSum = testedComp.reduce((a, c) => a + c.weight, 0);
  const rawTotal = Math.round(testedComp.reduce((a, c) => a + c.score * c.weight, 0) / wSum);

  // ---- Gates: a booked appointment never compensates bad qualification or unlawful communication ----
  const unqualifiedBooking = st.outcome === "book" && coverage < 1;
  const bookedAgainstNo = st.outcome === "book" && (s.idealOutcome === "respect_no" || s.idealOutcome === "disqualify");
  const gates = [
    { id: "G1", label: "Rechtlicher/ethischer Verstoß", triggered: violations.length > 0, effect: "Gesamtwert max. 40, nicht bestanden", cap: 40 },
    { id: "G2", label: "Termin ohne vollständige Qualifizierung", triggered: unqualifiedBooking, effect: "Gesamtwert max. 60, nicht bestanden", cap: 60 },
    { id: "G3", label: "Termin trotz Nein/fehlender Passung gebucht", triggered: bookedAgainstNo, effect: "Gesamtwert max. 50, nicht bestanden", cap: 50 },
    { id: "G4", label: "Erfundene Angaben in der Übergabenotiz", triggered: doc.fabricated > 0, effect: "Gesamtwert max. 65, nicht bestanden", cap: 65 },
    { id: "G5", label: "Kein zulässiges Gesprächsergebnis", triggered: !outcomeOk, effect: "nicht bestanden", cap: 100 },
  ];
  let total = rawTotal;
  for (const g of gates) if (g.triggered) total = Math.min(total, g.cap);
  const passed = total >= PASS_SCORE && gates.every((g) => !g.triggered);

  // ---- Feedback ----
  const ranked = [...testedComp].sort((a, b) => b.score - a.score || b.weight - a.weight);
  const strengths: string[] = [];
  for (const c of ranked.filter((c) => c.score >= 60).slice(0, 3)) strengths.push(`${c.label}: ${c.score}/100`);
  for (const m of used.filter((m) => m.quality === "good")) {
    if (strengths.length >= 3) break;
    strengths.push(`Gute Stelle: „${m.text}“ – ${m.coachNote}`);
  }
  while (strengths.length < 3) strengths.push("Du hast die Simulation vollständig durchgeführt – die Basis für gezieltes Üben.");

  const improvements = [...testedComp]
    .sort((a, b) => a.score - b.score || b.weight - a.weight)
    .slice(0, 3)
    .map((c) => `${c.label}: ${c.score}/100 – ${improvementHint(c.competency, coverage, doc.details)}`);

  const keyMoments = st.transcript
    .filter((t) => t.role === "setter" && t.moveId)
    .map((t) => {
      const m = s.moves.find((x) => x.id === t.moveId)!;
      return { turn: t.turn, moveText: m.text, note: m.coachNote, quality: m.quality };
    })
    .filter((k) => k.quality !== "ok");

  const worst = used.find((m) => m.quality === "bad" && m.betterMoveId) ?? used.find((m) => m.quality === "weak" && m.betterMoveId);
  const better = worst ? s.moves.find((m) => m.id === worst.betterMoveId) : undefined;
  const improvedExample =
    worst && better ? { original: worst.text, better: better.text, why: better.coachNote } : null;

  const weakest = [...testedComp].sort((a, b) => a.score - b.score)[0];
  const outcomeAssessment = `${OUTCOME_LABEL[st.outcome ?? "lost"]}. ${
    idealReached
      ? "Das war das bestmögliche Ergebnis für diese Ausgangslage."
      : outcomeOk
        ? `Vertretbar – optimal wäre gewesen: ${OUTCOME_LABEL[s.idealOutcome]}.`
        : `Für diese Ausgangslage nicht angemessen. Optimal: ${OUTCOME_LABEL[s.idealOutcome]}.`
  }`;

  return {
    scenarioId: s.id,
    scenarioVersion: s.version,
    rubricVersion: RUBRIC_VERSION,
    total,
    rawTotal,
    passed,
    gates: gates.map(({ cap: _cap, ...g }) => g),
    competencies: comp,
    strengths: strengths.slice(0, 3),
    improvements,
    keyMoments,
    improvedExample,
    reviewQuestionIds: s.reviewQuestionIds,
    outcome: st.outcome,
    outcomeAssessment: weakest ? `${outcomeAssessment} Schwächste Kompetenz: ${weakest.label}.` : outcomeAssessment,
  };
}

function improvementHint(c: Competency, coverage: number, docDetails: string[]): string {
  switch (c) {
    case "qualifizierung":
      return `Nur ${Math.round(coverage * 100)} % der Pflichtkriterien erfragt. Kläre Bedarf, Zeitrahmen, Entscheider und Rahmen, bevor du einen Termin vorschlägst.`;
    case "dokumentation":
      return docDetails[0] ?? "Dokumentiere nur, was der Kunde tatsächlich gesagt hat.";
    case "recht_ethik":
      return "Kein Druck, keine falschen Versprechen, ein Nein ist ein Nein.";
    case "bedarfsermittlung":
      return "Stelle offene Fragen zur Situation und zum Ziel des Kunden, bevor du über Termine sprichst.";
    case "fragetechnik":
      return "Eine Frage pro Nachricht, offen formuliert, ohne Suggestion.";
    case "zuhoeren":
      return "Greife Aussagen des Kunden auf und fasse sie in eigenen Worten zusammen.";
    case "einwaende":
      return "Einwand erst verstehen (nachfragen), dann ehrlich beantworten – nicht überreden.";
    case "eroeffnung":
      return "Stelle dich vor, nenne den Anlass des Kontakts und frage, ob gerade ein guter Moment ist.";
    case "kundenorientierung":
      return "Orientiere dich am Ziel des Kunden, nicht an deiner Terminquote.";
    case "terminvereinbarung":
      return "Schlage konkrete Zeitfenster vor und bestätige Termin, Teilnehmer und Ablauf.";
    case "klarheit":
      return "Kurze Sätze, klare nächste Schritte, kein Fachjargon.";
  }
}
