// Derived, read-only views on the learner state (pure functions → easy to test and reuse).
import { modules, questions, scenarios } from "./content";
import { activeDaysLast7, levelFor } from "./engine/gamification";
import { buildReviewQueue, summarizeObjective, type ObjectiveSummary } from "./engine/review";
import { COMPETENCIES } from "./engine/coach";
import { activityTimestamps, totalXp, type AcademyState } from "./store/state";
import type { ErrorCategory } from "./types";

export const ERROR_LABEL: Record<ErrorCategory, string> = {
  rollenverwechslung: "Rollenverwechslung (Setter/Closer/Berater)",
  begriffsfehler: "Begriffe verwechselt",
  qualifizierungsfehler: "Qualifizierung unvollständig",
  rechtsfehler: "Rechtliche Grenze übersehen",
  ethikfehler: "Ethische Grenze überschritten",
  rechenfehler: "Rechen-/Bezugsgrößenfehler",
  kommunikationsfehler: "Kommunikation (Fragetechnik, Klarheit)",
  prozessfehler: "Prozess/CRM-Ablauf",
  ueberinterpretation: "Überinterpretation/Vermutung als Fakt",
  unvollstaendig: "Unvollständig",
};

export function moduleProgress(s: AcademyState, moduleId: string) {
  const m = modules.find((x) => x.id === moduleId);
  if (!m) return { lessonsDone: 0, lessons: 0, ratio: 0, examPassed: false, bestExam: null as number | null };
  const done = m.lessons.filter((l) => s.lessonsCompleted[l.id]).length;
  const exams = s.quizAttempts.filter((a) => a.moduleId === moduleId && a.kind === "module-exam");
  return {
    lessonsDone: done,
    lessons: m.lessons.length,
    ratio: m.lessons.length ? done / m.lessons.length : 0,
    examPassed: exams.some((e) => e.passed),
    bestExam: exams.length ? Math.max(...exams.map((e) => e.percent)) : null,
  };
}

export function objectiveSummaries(s: AcademyState): (ObjectiveSummary & { text: string; moduleId: string })[] {
  return modules.flatMap((m) =>
    m.objectives.map((o) => {
      const sim = s.simulations
        .filter((x) => scenarios.find((sc) => sc.id === x.scenarioId)?.reviewQuestionIds.some((qid) => questions.find((q) => q.id === qid)?.objectiveId === o.id))
        .map((x) => x.total);
      return { ...summarizeObjective(o.id, s.attempts, sim), text: o.text, moduleId: m.id };
    }),
  );
}

export function dueReviews(s: AcademyState, now: number) {
  return buildReviewQueue(Object.values(s.reviews), now, 12);
}

export function errorAnalysis(s: AcademyState) {
  const counts: Partial<Record<ErrorCategory, number>> = {};
  for (const a of s.attempts) for (const c of a.errorCategories) counts[c] = (counts[c] ?? 0) + 1;
  return (Object.entries(counts) as [ErrorCategory, number][]).sort((a, b) => b[1] - a[1]);
}

export function competencyAverages(s: AcademyState) {
  return COMPETENCIES.map((c) => {
    const vals = s.simulations.map((x) => x.competencyScores[c.id]).filter((v): v is number => typeof v === "number");
    return { ...c, avg: vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null, n: vals.length };
  });
}

export function overview(s: AcademyState, now: number) {
  const xp = totalXp(s);
  return {
    xp,
    level: levelFor(xp),
    activeDays: activeDaysLast7(activityTimestamps(s), now),
    due: dueReviews(s, now).length,
    answered: s.attempts.length,
    accuracy: s.attempts.length ? s.attempts.filter((a) => a.score >= 0.999).length / s.attempts.length : null,
    simulations: s.simulations.length,
  };
}
