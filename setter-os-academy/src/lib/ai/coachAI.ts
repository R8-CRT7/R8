// AI SALES COACH – independent from the customer simulator.
// Gets: rubric, scenario goals (not the customer's persona prompt), transcript, measured metrics, handover.
// Output is VERIFIED: every quoted piece of evidence must literally occur in a setter message, otherwise it is dropped.
// Pass/fail (exam mode) is decided by deterministic gates, never by the model alone.
import { evaluateDocumentation, UNKNOWN_VALUE } from "../engine/coach";
import { normalizeText } from "../engine/quiz";
import type { HandoverNote, Scenario } from "../types";
import type { FreeSimState, TrainingMode } from "./customerAI";
import { measure, type FreeTurn, type MeasuredMetrics } from "./metrics";
import { AiError, type AiRouter } from "./types-router";

export const COACH_RUBRIC_VERSION = "ai-2.0.0";

export const COACH_CRITERIA = [
  { id: "eroeffnung", label: "Gesprächseröffnung", look: "Vorstellung, Bezug zur Anfrage, Erlaubnis eingeholt" },
  { id: "kommunikation", label: "Professionelle Kommunikation", look: "klar, kurz, passender Ton, eine Frage pro Nachricht, kein Fachjargon" },
  { id: "fragetechnik", label: "Fragetechnik", look: "offene Fragen, Folgefragen, keine Suggestivfragen" },
  { id: "bedarfsermittlung", label: "Bedarfsermittlung", look: "Anlass, Ziel und Problem verstanden, bevor Lösungen/Termine kommen" },
  { id: "qualifizierung", label: "Lead-Qualifizierung", look: "Pflichtkriterien geklärt, ehrliche Einschätzung der Passung" },
  { id: "empathie", label: "Empathie & aktives Zuhören", look: "Aussagen aufgegriffen, zusammengefasst, Gefühle angemessen benannt" },
  { id: "einwaende", label: "Einwandbehandlung", look: "Einwand verstanden (nachgefragt), ehrlich beantwortet, kein Überreden" },
  { id: "ablehnung", label: "Umgang mit Ablehnung", look: "ein Nein sofort respektiert, kein Nachbohren" },
  { id: "terminqualitaet", label: "Terminqualität", look: "nur sinnvolle Termine, konkrete Zeit, Mitentscheider, Bestätigung" },
  { id: "dokumentation", label: "Dokumentation", look: "Übergabe enthält nur Gesagtes, Unbekanntes als nicht erfragt" },
  { id: "recht_ethik", label: "Rechtliche & ethische Grenzen", look: "kein Druck, keine falschen Versprechen, keine Fachberatung außerhalb der Rolle" },
] as const;
export type CoachCriterionId = (typeof COACH_CRITERIA)[number]["id"];

export const RATINGS = ["stark", "solide", "ausbaufaehig", "kritisch", "nicht_beobachtet"] as const;
export type Rating = (typeof RATINGS)[number];
export const RATING_LABEL: Record<Rating, string> = {
  stark: "stark",
  solide: "solide",
  ausbaufaehig: "ausbaufähig",
  kritisch: "kritisch",
  nicht_beobachtet: "nicht beobachtet",
};

export interface Evidence {
  turn: number;
  quote: string;
  comment: string;
}
export interface CoachCriterion {
  id: CoachCriterionId;
  rating: Rating;
  reasoning: string;
  evidence: Evidence[];
}
export interface CoachReport {
  rubricVersion: string;
  criteria: CoachCriterion[];
  violations: (Evidence & { rule: string })[];
  strengths: string[];
  improvements: string[];
  improvedExample: { original: string; better: string; why: string } | null;
  exercises: string[];
  outcomeAssessment: string;
  /** how many model claims were dropped because the quote was not found in the transcript */
  droppedUnverified: number;
}

export interface Gate {
  id: string;
  label: string;
  triggered: boolean;
  detail?: string;
}

export interface FreeEvaluation {
  measured: MeasuredMetrics & { requiredFactsCovered: number; requiredFactsTotal: number; outcome: FreeSimState["outcome"]; documentationOk: number; documentationTotal: number; fabricated: number };
  coach: CoachReport | null; // null when the coach could not run (offline/unavailable) – measured part still valid
  gates: Gate[];
  passed: boolean | null; // null: practice/learning mode (no pass decision)
  mode: TrainingMode;
}

function setterNumbered(t: FreeTurn[]): string {
  return t.map((x, i) => `[${i}] ${x.role === "setter" ? "SETTER" : x.role === "customer" ? "KUNDE" : "SYSTEM"}: ${x.text}`).join("\n");
}

export function buildCoachPrompt(s: Scenario, st: FreeSimState, note: HandoverNote, metrics: MeasuredMetrics, allowedExercises: string[]): string {
  const required = s.facts.filter((f) => f.requiredForQualification).map((f) => f.label);
  return `Du bist ein strenger, fairer Ausbilder für Appointment Setter. Bewerte NUR die Nachrichten des SETTERS im folgenden Trainingsgespräch. Du bist nicht der Kunde.

SZENARIO: ${s.title} (${s.market}, ${s.channel}). Auftrag des Setters: ${s.briefing}
Pflichtkriterien vor einem Termin: ${required.join(", ") || "keine"}
Bestes Ergebnis: ${s.idealOutcome}; zulässig: ${s.acceptableOutcomes.join(", ")}
Fachfragen (Preis, Förderung, Technik, Steuer, Vertrag) darf der Setter NICHT selbst beantworten, sondern übergibt sie.
Kursregeln: Ein ausdrückliches Nein beendet die Werbeansprache. Keine künstliche Verknappung, keine erfundenen Belege, kein Druck.

GEMESSEN (deterministisch, nicht verändern): ${JSON.stringify(metrics)}
GESPRÄCHSERGEBNIS laut Simulation: ${st.outcome ?? "offen"}${st.appointmentSlot ? ` (Termin: ${st.appointmentSlot})` : ""}
ÜBERGABENOTIZ DES SETTERS: ${JSON.stringify(note.fields)}

VERLAUF (Nummer in eckigen Klammern = turn):
${setterNumbered(st.transcript)}

BEWERTUNGSKRITERIEN:
${COACH_CRITERIA.map((c) => `- ${c.id}: ${c.label} – ${c.look}`).join("\n")}

ANWEISUNGEN:
- Bewerte jedes Kriterium mit einer Stufe: stark | solide | ausbaufaehig | kritisch | nicht_beobachtet. KEINE Punktzahlen.
- Jede Bewertung außer nicht_beobachtet braucht mindestens einen Beleg: turn-Nummer und ein WÖRTLICHES Zitat (max. 12 Wörter) aus einer SETTER-Nachricht.
- "violations": nur echte Verstöße gegen die Kursregeln oder Rollen-Grenzen, jeweils mit wörtlichem Zitat. Leer, wenn keine.
- Genau 3 Stärken und 3 Verbesserungen, konkret und auf Gesprächsstellen bezogen.
- "improvedExample": die schwächste Setter-Nachricht (wörtlich) und eine bessere Formulierung.
- "exercises": 1–3 IDs ausschließlich aus dieser Liste: ${allowedExercises.join(", ")}
- Schreibe Deutsch, sachlich, aufgabenbezogen, nie über die Person.

Gib NUR dieses JSON zurück:
{"criteria":[{"id":"eroeffnung","rating":"solide","reasoning":"…","evidence":[{"turn":1,"quote":"…","comment":"…"}]}],"violations":[{"turn":3,"quote":"…","rule":"…","comment":"…"}],"strengths":["…","…","…"],"improvements":["…","…","…"],"improvedExample":{"original":"…","better":"…","why":"…"},"exercises":["…"],"outcomeAssessment":"…"}`;
}

/** Does the quote occur (normalised) in the setter message of that turn – or, if the turn number is off, in any setter message? */
export function verifyQuote(transcript: FreeTurn[], turn: number, quote: string): number | null {
  const q = normalizeText(quote);
  if (q.length < 3) return null;
  const at = transcript[turn];
  if (at?.role === "setter" && normalizeText(at.text).includes(q)) return turn;
  const idx = transcript.findIndex((t) => t.role === "setter" && normalizeText(t.text).includes(q));
  return idx >= 0 ? idx : null;
}

export function parseCoachReport(raw: string, transcript: FreeTurn[], allowedExercises: string[]): CoachReport {
  const m = raw.match(/\{[\s\S]*\}/);
  if (!m) throw new AiError("invalid_output", "Coach-Antwort ohne JSON.", raw);
  let o: Record<string, unknown>;
  try {
    o = JSON.parse(m[0]);
  } catch {
    throw new AiError("invalid_output", "Coach-Antwort war kein gültiges JSON.", raw);
  }
  let dropped = 0;
  const verifyList = (arr: unknown): Evidence[] =>
    (Array.isArray(arr) ? arr : []).flatMap((e) => {
      const ev = e as Record<string, unknown>;
      const t = verifyQuote(transcript, Number(ev.turn), String(ev.quote ?? ""));
      if (t === null) {
        dropped++;
        return [];
      }
      return [{ turn: t, quote: String(ev.quote).slice(0, 200), comment: String(ev.comment ?? "").slice(0, 400) }];
    });
  const byId = new Map<string, Record<string, unknown>>();
  for (const c of Array.isArray(o.criteria) ? o.criteria : []) byId.set(String((c as Record<string, unknown>).id), c as Record<string, unknown>);
  const criteria: CoachCriterion[] = COACH_CRITERIA.map((c) => {
    const x = byId.get(c.id);
    let rating = (RATINGS as readonly string[]).includes(String(x?.rating)) ? (x!.rating as Rating) : "nicht_beobachtet";
    const evidence = verifyList(x?.evidence);
    // A rating without verifiable evidence is not accepted (prevents unfounded judgements)
    if (rating !== "nicht_beobachtet" && evidence.length === 0 && c.id !== "dokumentation") rating = "nicht_beobachtet";
    return { id: c.id, rating, reasoning: String(x?.reasoning ?? "").slice(0, 600), evidence };
  });
  const violations = (Array.isArray(o.violations) ? o.violations : []).flatMap((v) => {
    const vv = v as Record<string, unknown>;
    const t = verifyQuote(transcript, Number(vv.turn), String(vv.quote ?? ""));
    if (t === null) {
      dropped++;
      return [];
    }
    return [{ turn: t, quote: String(vv.quote).slice(0, 200), rule: String(vv.rule ?? "Kursregel").slice(0, 200), comment: String(vv.comment ?? "").slice(0, 400) }];
  });
  const strList = (a: unknown) => (Array.isArray(a) ? a.map(String).filter(Boolean).slice(0, 3) : []);
  const ie = o.improvedExample as Record<string, unknown> | undefined;
  const improvedExample =
    ie && typeof ie.original === "string" && typeof ie.better === "string" && verifyQuote(transcript, -1, ie.original.slice(0, 80)) !== null
      ? { original: ie.original.slice(0, 600), better: String(ie.better).slice(0, 600), why: String(ie.why ?? "").slice(0, 400) }
      : null;
  return {
    rubricVersion: COACH_RUBRIC_VERSION,
    criteria,
    violations,
    strengths: strList(o.strengths),
    improvements: strList(o.improvements),
    improvedExample,
    exercises: (Array.isArray(o.exercises) ? o.exercises.map(String) : []).filter((x) => allowedExercises.includes(x)).slice(0, 3),
    outcomeAssessment: String(o.outcomeAssessment ?? "").slice(0, 600),
    droppedUnverified: dropped,
  };
}

/** Deterministic part of the evaluation – works without any AI. */
export function measuredEvaluation(s: Scenario, st: FreeSimState, note: HandoverNote) {
  const metrics = measure(st.transcript);
  const req = s.facts.filter((f) => f.requiredForQualification);
  const covered = req.filter((f) => st.revealed.includes(f.key)).length;
  const doc = evaluateDocumentation(s, { revealed: st.revealed } as never, note);
  const docOk = Math.round((doc.score / 100) * s.handoverFields.length);
  return { ...metrics, requiredFactsCovered: covered, requiredFactsTotal: req.length, outcome: st.outcome, documentationOk: docOk, documentationTotal: s.handoverFields.length, fabricated: doc.fabricated };
}

/** Exam gates – defined before the attempt, shown in the UI before starting. */
export const EXAM_RULES = [
  "Kein rechtlicher/ethischer Verstoß (Coach-Beleg mit wörtlichem Zitat oder automatischer Warnsatz)",
  "Ein Termin nur mit allen Pflichtkriterien",
  "Kein Termin, wenn Absage oder Disqualifizierung richtig wäre",
  "Keine erfundenen Angaben in der Übergabe",
  "Ein zulässiges Gesprächsergebnis",
  "Kein Kriterium mit „kritisch“ bewertet",
];

export function gates(s: Scenario, measured: FreeEvaluation["measured"], coach: CoachReport | null): Gate[] {
  const booked = measured.outcome === "book";
  return [
    { id: "G1", label: EXAM_RULES[0]!, triggered: measured.redFlags.length > 0 || (coach?.violations.length ?? 0) > 0, detail: [...measured.redFlags.map((r) => r.label), ...(coach?.violations.map((v) => v.rule) ?? [])].join(" · ") || undefined },
    { id: "G2", label: EXAM_RULES[1]!, triggered: booked && measured.requiredFactsCovered < measured.requiredFactsTotal, detail: `${measured.requiredFactsCovered}/${measured.requiredFactsTotal} Pflichtkriterien` },
    { id: "G3", label: EXAM_RULES[2]!, triggered: booked && (s.idealOutcome === "respect_no" || s.idealOutcome === "disqualify") },
    { id: "G4", label: EXAM_RULES[3]!, triggered: measured.fabricated > 0 },
    { id: "G5", label: EXAM_RULES[4]!, triggered: !measured.outcome || measured.outcome === "lost" || !s.acceptableOutcomes.includes(measured.outcome) },
    { id: "G6", label: EXAM_RULES[5]!, triggered: !!coach?.criteria.some((c) => c.rating === "kritisch") },
  ];
}

export function allowedExercisesFor(s: Scenario): string[] {
  return [...s.reviewQuestionIds, ...(s.ai?.lessonLinks ?? [])];
}

export async function coachEvaluate(router: AiRouter | null, s: Scenario, st: FreeSimState, note: HandoverNote): Promise<FreeEvaluation & { coachError?: string }> {
  const measured = measuredEvaluation(s, st, note);
  let coach: CoachReport | null = null;
  let coachError: string | undefined;
  if (router) {
    const allowed = allowedExercisesFor(s);
    try {
      const res = await router.complete({ role: "coach", prompt: buildCoachPrompt(s, st, note, measure(st.transcript), allowed) });
      coach = parseCoachReport(res.text, st.transcript, allowed);
    } catch (e) {
      coachError = (e as AiError).message;
    }
  }
  const g = gates(s, measured, coach);
  // In exam mode a missing coach means no pass decision is possible (criteria could not be checked).
  const passed = st.mode === "pruefung" ? (coach ? g.every((x) => !x.triggered) : null) : null;
  return { measured, coach, gates: g, passed, mode: st.mode, coachError };
}

// ---------- Hints (learning mode only) ----------

export function buildHintPrompt(s: Scenario, st: FreeSimState, wantExample: boolean): string {
  const missing = s.facts.filter((f) => f.requiredForQualification && !st.revealed.includes(f.key)).map((f) => f.label);
  return `Du bist Ausbilder in einem Setter-Training (Lernmodus). Gib dem Setter EINEN kurzen Hinweis (max. 2 Sätze) für seine nächste Nachricht. Verrate keine Kundendaten, die er noch nicht erfahren hat.
Auftrag: ${s.briefing}
Noch nicht geklärte Pflichtkriterien (nur Bezeichnungen): ${missing.join(", ") || "alle geklärt"}
Verlauf:
${setterNumbered(st.transcript.slice(-10))}
${wantExample ? 'Gib zusätzlich EIN Formulierungsbeispiel als Satz, eingeleitet mit „Beispiel: “.' : "Gib KEIN Formulierungsbeispiel, nur die Richtung."}
Antworte als reiner Text auf Deutsch.`;
}

export async function hint(router: AiRouter, s: Scenario, st: FreeSimState, wantExample: boolean, signal?: AbortSignal): Promise<string> {
  if (st.mode !== "lern") throw new AiError("invalid_output", "Hinweise gibt es nur im Lernmodus.");
  const res = await router.complete({ role: "hint", prompt: buildHintPrompt(s, st, wantExample), signal });
  return res.text.trim().slice(0, 600);
}

export { UNKNOWN_VALUE };
