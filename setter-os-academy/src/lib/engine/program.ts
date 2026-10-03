// 90-day program logic (pure). Rules (LEARNING_SCIENCE.md §7):
//  * One program day per calendar day by default (spacing). The learner may unlock the next day early on request.
//  * A day is complete when all required items are done; the learner confirms with "Tag abschließen".
//  * The first day of a stage requires the previous stage check: quiz ≥ threshold AND required simulations passed.
//  * Stages whose content is not written yet stay locked with an honest notice.
import type { ProgramDay, ProgramItem, ProgramStage } from "../types";
import type { AcademyState } from "../store/state";
import { buildReviewQueue } from "./review";

export function localDayKey(ts: number): string {
  const d = new Date(ts);
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

export function allDays(program: ProgramStage[]): (ProgramDay & { stageId: string })[] {
  return program.flatMap((st) => st.days.map((d) => ({ ...d, stageId: st.id })));
}

/** When did the learner get access to this day? (anchor for "review done today") */
export function unlockAnchor(s: AcademyState, day: number): number | null {
  if (day === 1) return s.program.startedAt;
  return s.program.dayCompletedAt[day - 1] ?? null;
}

export function itemDone(s: AcademyState, item: ProgramItem, anchor: number | null, now: number): boolean {
  switch (item.type) {
    case "lesson":
      return !!s.lessonsCompleted[item.ref];
    case "quiz": {
      const attempts = s.quizAttempts.filter((a) => a.moduleId === item.ref);
      // stage checks must be passed, module quizzes only attempted (the stage check is the gate)
      if (item.ref.startsWith("ST")) return attempts.some((a) => a.passed);
      // consolidation days ask for a NEW attempt – an old attempt must not tick the day off
      return item.fresh ? anchor !== null && attempts.some((a) => a.at >= anchor) : attempts.length > 0;
    }
    case "simulation":
      if (item.fresh && anchor === null) return false;
      const since = item.fresh ? anchor! : -Infinity;
      return s.simulations.some((x) => x.scenarioId === item.ref && x.at >= since) || s.aiSimulations.some((x) => x.scenarioId === item.ref && x.at >= since);
    case "transfer":
      return !!s.transferSubmissions[item.ref];
    case "review": {
      if (anchor !== null && s.program.reviewSessions.some((t) => t >= anchor)) return true;
      return buildReviewQueue(Object.values(s.reviews), now).length === 0;
    }
  }
}

export function stageCheckPassed(s: AcademyState, st: ProgramStage): boolean {
  const quiz = s.quizAttempts.some((a) => a.moduleId === st.check.id && a.kind === "stage-check" && a.passed);
  // offline pass or AI exam-mode pass (gates checked, coach evidence verified)
  const sims = st.check.requiredSimulations.every(
    (id) => s.simulations.some((x) => x.scenarioId === id && x.passed) || s.aiSimulations.some((x) => x.scenarioId === id && x.mode === "pruefung" && x.evaluation.passed === true),
  );
  return quiz && sims;
}

export type DayState =
  | { status: "completed"; at: number }
  | { status: "open"; doneCount: number; total: number; allDone: boolean }
  | { status: "locked"; reason: string; canFastTrack: boolean };

export function dayState(s: AcademyState, program: ProgramStage[], day: number, now: number): DayState {
  const stage = program.find((st) => day >= st.dayFrom && day <= st.dayTo);
  if (!stage) return { status: "locked", reason: "Unbekannter Tag.", canFastTrack: false };
  if (!stage.available) return { status: "locked", reason: `Stufe ${stage.number} wird gerade ausgearbeitet und vor deinem Start freigeschaltet.`, canFastTrack: false };
  const done = s.program.dayCompletedAt[day];
  if (done) return { status: "completed", at: done };
  if (!s.program.startedAt) return { status: "locked", reason: "Starte zuerst deinen Plan.", canFastTrack: false };
  if (day > 1) {
    const prevStage = program.find((st) => st.dayTo === day - 1);
    if (prevStage && !stageCheckPassed(s, prevStage))
      return { status: "locked", reason: `Erst Stufen-Check ${prevStage.number} bestehen (≥ ${prevStage.check.passThreshold * 100} % und Pflichtsimulationen).`, canFastTrack: false };
    const prevDone = s.program.dayCompletedAt[day - 1];
    if (!prevDone) return { status: "locked", reason: `Schließe zuerst Tag ${day - 1} ab.`, canFastTrack: false };
    const sameDay = localDayKey(prevDone) === localDayKey(now);
    if (sameDay && !s.program.fastTrack.includes(day))
      return { status: "locked", reason: "Öffnet morgen – Abstand zwischen Lerneinheiten verbessert das Behalten.", canFastTrack: true };
  }
  const d = stage.days.find((x) => x.day === day);
  if (!d) return { status: "locked", reason: "Für diesen Tag gibt es noch keine Inhalte.", canFastTrack: false };
  const anchor = unlockAnchor(s, day);
  const required = d.items.filter((i) => !(i.type === "transfer" && i.optional));
  const doneCount = required.filter((i) => itemDone(s, i, anchor, now)).length;
  return { status: "open", doneCount, total: required.length, allDone: doneCount === required.length };
}

/** The day the learner should work on now (first not-completed day), or null when all available days are done. */
export function currentDay(s: AcademyState, program: ProgramStage[]): number | null {
  for (const d of allDays(program)) if (!s.program.dayCompletedAt[d.day]) return d.day;
  return null;
}

export function programProgress(s: AcademyState, program: ProgramStage[]) {
  const totalDays = Math.max(...program.map((p) => p.dayTo));
  const completed = Object.keys(s.program.dayCompletedAt).length;
  return { totalDays, completed, ratio: completed / totalDays };
}
