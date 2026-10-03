// Transparent spaced-repetition scheduler (Leitner variant) + mastery estimation.
//
// Why Leitner and not SM-2/FSRS: every step is explainable to the learner
// ("Box 3 → nächste Wiederholung in 7 Tagen"). It can be replaced later because
// all state lives in ObjectiveProgress / ItemReview and the interface is small.

import type { ErrorCategory } from "../types";

export const BOX_INTERVAL_DAYS = [0, 1, 3, 7, 16, 35] as const; // index = box (1..5); box 0 unused
export const MAX_BOX = 5;
const DAY = 24 * 60 * 60 * 1000;

export type Confidence = 1 | 2 | 3; // 1 = geraten, 2 = unsicher, 3 = sicher

export interface ItemReview {
  questionId: string;
  objectiveId: string;
  box: number; // 1..5
  attempts: number;
  correct: number;
  wrong: number;
  lastScore: number;
  lastAt: number; // epoch ms
  nextDueAt: number;
  lastConfidence?: Confidence;
}

/** Pure function: next state of a review item after an answer. */
export function scheduleNext(
  prev: ItemReview | undefined,
  input: { questionId: string; objectiveId: string; score: number; confidence?: Confidence; now: number },
): ItemReview {
  const base: ItemReview = prev ?? {
    questionId: input.questionId,
    objectiveId: input.objectiveId,
    box: 1,
    attempts: 0,
    correct: 0,
    wrong: 0,
    lastScore: 0,
    lastAt: 0,
    nextDueAt: input.now,
  };
  const isCorrect = input.score >= 0.999;
  let box = base.box;
  if (!isCorrect) {
    box = 1; // wrong -> practise again soon (knowledge is not "lost", only re-scheduled)
  } else if (input.confidence === 1) {
    box = base.box; // correct but guessed: no promotion
  } else {
    box = Math.min(MAX_BOX, base.box + 1);
  }
  const interval = isCorrect ? BOX_INTERVAL_DAYS[box]! : 1;
  return {
    ...base,
    box,
    attempts: base.attempts + 1,
    correct: base.correct + (isCorrect ? 1 : 0),
    wrong: base.wrong + (isCorrect ? 0 : 1),
    lastScore: input.score,
    lastAt: input.now,
    nextDueAt: input.now + interval * DAY,
    lastConfidence: input.confidence,
  };
}

export function isDue(item: ItemReview, now: number): boolean {
  return item.nextDueAt <= now;
}

/**
 * Builds an interleaved review queue: due items sorted by urgency, then re-ordered so
 * that two consecutive items rarely share the same learning objective (Sana & Yan 2022 – interleaving).
 */
export function buildReviewQueue(items: ItemReview[], now: number, limit = 12): ItemReview[] {
  const due = items
    .filter((i) => isDue(i, now))
    .sort((a, b) => a.box - b.box || a.nextDueAt - b.nextDueAt || a.questionId.localeCompare(b.questionId))
    .slice(0, limit);
  const out: ItemReview[] = [];
  const pool = [...due];
  while (pool.length) {
    const lastObj = out[out.length - 1]?.objectiveId;
    const idx = pool.findIndex((i) => i.objectiveId !== lastObj);
    out.push(pool.splice(idx === -1 ? 0 : idx, 1)[0]!);
  }
  return out;
}

// ---------- Objective-level tracking ----------

export interface AttemptLog {
  questionId: string;
  objectiveId: string;
  score: number;
  at: number;
  durationMs: number;
  confidence?: Confidence;
  errorCategories: ErrorCategory[];
  context: "lesson" | "quiz" | "review" | "exam";
}

export type MasteryLevel = "nicht_geprueft" | "im_aufbau" | "gefestigt" | "gesichert";

export interface ObjectiveSummary {
  objectiveId: string;
  attempts: number;
  correct: number;
  wrong: number;
  /** measured: weighted mean of recent scores (newest weight highest) */
  measuredPerformance: number | null;
  /** estimated: conservative label that also needs spacing and delayed success */
  mastery: MasteryLevel;
  masteryReason: string;
  avgDurationMs: number | null;
  lastAt: number | null;
  errorCategories: Partial<Record<ErrorCategory, number>>;
  avgConfidence: number | null;
  /** positive = overconfident, negative = underconfident */
  calibrationGap: number | null;
  simulationScore: number | null;
}

export function summarizeObjective(
  objectiveId: string,
  logs: AttemptLog[],
  simulationScores: number[] = [],
): ObjectiveSummary {
  const mine = logs.filter((l) => l.objectiveId === objectiveId).sort((a, b) => a.at - b.at);
  const errorCategories: Partial<Record<ErrorCategory, number>> = {};
  for (const l of mine) for (const c of l.errorCategories) errorCategories[c] = (errorCategories[c] ?? 0) + 1;
  const sim = simulationScores.length ? simulationScores.reduce((a, b) => a + b, 0) / simulationScores.length : null;
  if (!mine.length) {
    return {
      objectiveId,
      attempts: 0,
      correct: 0,
      wrong: 0,
      measuredPerformance: null,
      mastery: "nicht_geprueft",
      masteryReason: "Noch keine Antworten zu diesem Lernziel.",
      avgDurationMs: null,
      lastAt: null,
      errorCategories,
      avgConfidence: null,
      calibrationGap: null,
      simulationScore: sim,
    };
  }
  const recent = mine.slice(-8);
  let wSum = 0;
  let sSum = 0;
  recent.forEach((l, i) => {
    const w = i + 1;
    wSum += w;
    sSum += w * l.score;
  });
  const measured = sSum / wSum;
  const correct = mine.filter((l) => l.score >= 0.999).length;
  const conf = mine.filter((l) => l.confidence).map((l) => ({ c: l.confidence!, s: l.score }));
  const avgConfidence = conf.length ? conf.reduce((a, b) => a + b.c, 0) / conf.length : null;
  // map confidence 1..3 to expected accuracy 0.33..1 and compare to actual
  const calibrationGap = conf.length
    ? conf.reduce((a, b) => a + (b.c / 3 - b.s), 0) / conf.length
    : null;
  const days = new Set(mine.map((l) => Math.floor(l.at / DAY))).size;
  const firstDay = Math.floor(mine[0]!.at / DAY);
  const delayedSuccess = mine.some((l) => Math.floor(l.at / DAY) - firstDay >= 3 && l.score >= 0.999);

  let mastery: MasteryLevel = "im_aufbau";
  let masteryReason = "Leistung wird noch aufgebaut.";
  if (mine.length >= 3 && measured >= 0.8) {
    mastery = "gefestigt";
    masteryReason = "Mind. 3 Versuche mit ≥ 80 % gewichteter Leistung.";
    if (days >= 2 && delayedSuccess && (sim === null || sim >= 70)) {
      mastery = "gesichert";
      masteryReason = "Auch nach ≥ 3 Tagen Abstand korrekt beantwortet (verzögerter Abruf).";
    } else {
      masteryReason += " Für „gesichert“ fehlt ein korrekter Abruf mit ≥ 3 Tagen Abstand.";
    }
  } else if (mine.length < 3) {
    masteryReason = `Erst ${mine.length} Versuch(e) – zu wenig für eine Einschätzung.`;
  }
  return {
    objectiveId,
    attempts: mine.length,
    correct,
    wrong: mine.length - correct,
    measuredPerformance: Math.round(measured * 1000) / 10,
    mastery,
    masteryReason,
    avgDurationMs: Math.round(mine.reduce((a, b) => a + b.durationMs, 0) / mine.length),
    lastAt: mine[mine.length - 1]!.at,
    errorCategories,
    avgConfidence,
    calibrationGap: calibrationGap === null ? null : Math.round(calibrationGap * 100) / 100,
    simulationScore: sim,
  };
}
