// Individual practice recommendations (transparent rules, no ML).
import type { AcademyState } from "../store/state";
import { lessonById, questions, scenarioById } from "../content";
import { buildReviewQueue, summarizeObjective } from "./review";
import { mistakeSummary, MISTAKE_PRACTICE } from "./errorMemory";

export interface Recommendation {
  kind: "review" | "lesson" | "simulation" | "objective";
  title: string;
  reason: string;
  href: string;
}

export function recommendations(s: AcademyState, now: number, limit = 4): Recommendation[] {
  const out: Recommendation[] = [];
  const due = buildReviewQueue(Object.values(s.reviews), now);
  if (due.length) out.push({ kind: "review", title: `${due.length} fällige Wiederholungen`, reason: "Abruf mit Abstand festigt Wissen am stärksten.", href: "/review/" });
  for (const m of mistakeSummary(s, now).slice(0, 2)) {
    const p = MISTAKE_PRACTICE[m.cls];
    const l = p.lessons.map(lessonById).find(Boolean);
    if (l) out.push({ kind: "lesson", title: `Lektion: ${l.title}`, reason: `Häufig im Fehlergedächtnis: ${m.label} (${m.recent} in 14 Tagen).`, href: `/learn/${l.moduleId}/${l.id}/` });
    const sc = p.scenarios.map(scenarioById).find(Boolean);
    if (sc) out.push({ kind: "simulation", title: `Gespräch üben: ${sc.title}`, reason: `Trainiert gezielt: ${m.label}.`, href: `/simulator/${sc.id}/` });
  }
  // weakest attempted objective
  const objIds = [...new Set(questions.map((q) => q.objectiveId))];
  const weak = objIds
    .map((o) => summarizeObjective(o, s.attempts))
    .filter((x) => x.attempts >= 2 && (x.measuredPerformance ?? 100) < 70)
    .sort((a, b) => (a.measuredPerformance ?? 0) - (b.measuredPerformance ?? 0))[0];
  if (weak) {
    const qs = questions.filter((q) => q.objectiveId === weak.objectiveId).slice(0, 5).map((q) => q.id);
    out.push({ kind: "objective", title: "Schwächstes Lernziel gezielt üben", reason: `Gemessene Leistung ${weak.measuredPerformance} % bei ${weak.attempts} Versuchen.`, href: `/review/?focus=${qs.join(",")}` });
  }
  const seen = new Set<string>();
  return out.filter((r) => (seen.has(r.href) ? false : (seen.add(r.href), true))).slice(0, limit);
}
