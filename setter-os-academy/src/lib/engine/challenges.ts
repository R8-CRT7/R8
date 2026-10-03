// Weekly challenges, practice missions and competence badges.
// Badges are awarded ONLY from verified performance (stage checks, exam-mode simulations, delayed recall) – never for clicks.
import type { AcademyState } from "../store/state";

const DAY = 86_400_000;
export function isoWeekKey(ts: number): string {
  const d = new Date(ts);
  const day = (d.getDay() + 6) % 7;
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - day + 3);
  const firstThu = new Date(d.getFullYear(), 0, 4);
  const week = 1 + Math.round(((d.getTime() - firstThu.getTime()) / DAY - 3 + ((firstThu.getDay() + 6) % 7)) / 7);
  return `${d.getFullYear()}-W${String(week).padStart(2, "0")}`;
}
function weekStart(ts: number): number {
  const d = new Date(ts);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return d.getTime();
}

interface ChallengeDef {
  id: string;
  title: string;
  target: number;
  measure: (s: AcademyState, from: number) => number;
}
const POOL: ChallengeDef[] = [
  { id: "review-20", title: "20 Wiederholungsfragen beantworten", target: 20, measure: (s, f) => s.attempts.filter((a) => a.context === "review" && a.at >= f).length },
  { id: "practice-3", title: "3 KI-Gespräche im Praxis- oder Prüfungsmodus", target: 3, measure: (s, f) => s.aiSimulations.filter((x) => x.at >= f && x.mode !== "lern").length },
  { id: "clean-2", title: "2 Gespräche ohne Grenzverletzung", target: 2, measure: (s, f) => s.aiSimulations.filter((x) => x.at >= f && !x.evaluation.gates.find((g) => g.id === "G1")?.triggered).length + s.simulations.filter((x) => x.at >= f && x.passed).length },
  { id: "open-q", title: "10 offene Fragen in KI-Gesprächen stellen", target: 10, measure: (s, f) => s.aiSimulations.filter((x) => x.at >= f).reduce((a, x) => a + x.evaluation.measured.openQuestions, 0) },
  { id: "days-4", title: "An 4 verschiedenen Tagen lernen", target: 4, measure: (s, f) => new Set(s.attempts.filter((a) => a.at >= f).map((a) => new Date(a.at).toDateString())).size },
  { id: "handover", title: "3 fehlerfreie Übergabenotizen", target: 3, measure: (s, f) => s.aiSimulations.filter((x) => x.at >= f && x.evaluation.measured.documentationOk === x.evaluation.measured.documentationTotal).length },
];

export function weeklyChallenges(s: AcademyState, now: number) {
  const key = isoWeekKey(now);
  let h = 0;
  for (const c of key) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const picks = [POOL[h % POOL.length]!, POOL[(h + 2) % POOL.length]!, POOL[(h + 4) % POOL.length]!];
  const from = weekStart(now);
  return { week: key, items: picks.map((c) => ({ id: c.id, title: c.title, target: c.target, value: Math.min(c.target, c.measure(s, from)) })) };
}

export const MISSIONS = [
  { id: "m-no", title: "Mission: Ein Nein in der Prüfung respektieren", how: "Szenario „Ich möchte keinen Termin“ im Prüfungsmodus bestehen.", href: "/simulator/SIM-003/", done: (s: AcademyState) => s.aiSimulations.some((x) => x.scenarioId === "SIM-003" && x.mode === "pruefung" && x.evaluation.passed) },
  { id: "m-disq", title: "Mission: Ehrlich disqualifizieren", how: "Café ohne Budget im Prüfungsmodus bestehen.", href: "/simulator/SIM-002/", done: (s: AcademyState) => s.aiSimulations.some((x) => x.scenarioId === "SIM-002" && x.mode === "pruefung" && x.evaluation.passed) },
  { id: "m-book", title: "Mission: Ein vollständig qualifizierter Termin", how: "Wärmepumpe im Prüfungsmodus bestehen (alle Pflichtkriterien).", href: "/simulator/SIM-001/", done: (s: AcademyState) => s.aiSimulations.some((x) => x.scenarioId === "SIM-001" && x.mode === "pruefung" && x.evaluation.passed) },
  { id: "m-listen", title: "Mission: Zuhören, bis sie sich verstanden fühlt", how: "Unsichere Kundin im Prüfungsmodus bestehen.", href: "/simulator/SIM-004/", done: (s: AcademyState) => s.aiSimulations.some((x) => x.scenarioId === "SIM-004" && x.mode === "pruefung" && x.evaluation.passed) },
];

export interface Badge {
  id: string;
  title: string;
  criterion: string;
  earned: boolean;
}
export function competenceBadges(s: AcademyState, stageCheckPassed: (id: string) => boolean): Badge[] {
  const examPasses = s.aiSimulations.filter((x) => x.mode === "pruefung" && x.evaluation.passed);
  const delayed = s.attempts.filter((a) => {
    if (a.score < 0.999) return false;
    const first = s.attempts.find((b) => b.questionId === a.questionId);
    return first && a.at - first.at >= 7 * DAY;
  });
  return [
    { id: "b-st1", title: "Basics geprüft", criterion: "Stufen-Check 1 bestanden (Quiz ≥ 80 % + Pflichtsimulationen)", earned: stageCheckPassed("ST1") },
    { id: "b-exam1", title: "Gesprächsprüfung", criterion: "1 KI-Gespräch im Prüfungsmodus bestanden", earned: examPasses.length >= 1 },
    { id: "b-exam4", title: "Vier Szenarien geprüft", criterion: "Alle 4 Szenarien im Prüfungsmodus bestanden", earned: new Set(examPasses.map((x) => x.scenarioId)).size >= 4 },
    { id: "b-recall", title: "Langzeitwissen", criterion: "20 Fragen ≥ 7 Tage nach dem ersten Versuch richtig beantwortet", earned: new Set(delayed.map((a) => a.questionId)).size >= 20 },
  ];
}
