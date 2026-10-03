// Learner state – pure, serialisable, versioned. No personal data beyond a self-chosen display name.
// Persistence adapter: ./storage.ts (localStorage today, Supabase later – same shape).

import { evaluate } from "../engine/coach";
import { replay } from "../engine/customer";
import { ACHIEVEMENTS, XP_RULES, type XpReason } from "../engine/gamification";
import { scheduleNext, type AttemptLog, type Confidence, type ItemReview } from "../engine/review";
import type { GradeResult, HandoverNote, Question, Scenario, SimulationEvaluation } from "../types";

export const SCHEMA_VERSION = 3;

export interface Settings {
  theme: "dark" | "light" | "system";
  motion: "system" | "reduce";
  pauseMode: boolean; // learning pause: no reminders, nothing is lost
}

export interface Profile {
  id: string;
  displayName: string;
  createdAt: number;
  locale: "de" | "en" | "es";
  privacyNoticeVersion: string;
  privacyNoticeAcceptedAt: number;
}

export interface QuizAttemptRecord {
  id: string;
  moduleId: string;
  kind: "module-exam" | "practice" | "stage-check";
  at: number;
  percent: number;
  passed: boolean;
  courseVersion: string;
  /** Question versions at attempt time – later content edits never change old results */
  questionVersions: Record<string, number>;
  scores: Record<string, number>;
  pendingManualReview: number;
}

export interface SimulationRecord {
  id: string;
  scenarioId: string;
  scenarioVersion: number;
  at: number;
  /** Data minimisation: only move ids are stored. The transcript is reproducible via replay(). */
  moveIds: string[];
  handover: HandoverNote;
  total: number;
  passed: boolean;
  rubricVersion: string;
  competencyScores: Record<string, number>;
}

export interface AcademyState {
  schemaVersion: number;
  profile: Profile | null;
  settings: Settings;
  lessonsCompleted: Record<string, { at: number; courseVersion: string }>;
  attempts: AttemptLog[];
  reviews: Record<string, ItemReview>;
  firstCorrect: string[];
  quizAttempts: QuizAttemptRecord[];
  simulations: SimulationRecord[];
  xpLog: { at: number; reason: XpReason; amount: number; ref: string }[];
  achievements: Record<string, number>;
  transferSubmissions: Record<string, { at: number; text: string; selfCheck: string[] }>;
  program: ProgramProgress;
}

export interface ProgramProgress {
  startedAt: number | null;
  /** day number -> completion timestamp */
  dayCompletedAt: Record<number, number>;
  /** days unlocked early on the learner's explicit request */
  fastTrack: number[];
  /** timestamps of finished review sessions */
  reviewSessions: number[];
}

export const MAX_ATTEMPT_LOGS = 3000;

export function initialState(): AcademyState {
  return {
    schemaVersion: SCHEMA_VERSION,
    profile: null,
    settings: { theme: "dark", motion: "system", pauseMode: false },
    lessonsCompleted: {},
    attempts: [],
    reviews: {},
    firstCorrect: [],
    quizAttempts: [],
    simulations: [],
    xpLog: [],
    achievements: {},
    transferSubmissions: {},
    program: { startedAt: null, dayCompletedAt: {}, fastTrack: [], reviewSessions: [] },
  };
}

/** Migrations from older stored shapes. Each step is small and tested. */
export function migrate(raw: unknown): AcademyState {
  if (!raw || typeof raw !== "object") return initialState();
  const s = raw as Record<string, unknown>;
  let v = typeof s.schemaVersion === "number" ? s.schemaVersion : 0;
  let cur: Record<string, unknown> = { ...s };
  if (v < 1) {
    // v0 (pre-release) stored only a name and completed lessons as string[]
    const done = Array.isArray(cur.completed) ? (cur.completed as string[]) : [];
    cur = {
      ...initialState(),
      profile: typeof cur.name === "string" ? newProfile(cur.name as string, 0) : null,
      lessonsCompleted: Object.fromEntries(done.map((id) => [id, { at: 0, courseVersion: "unknown" }])),
    };
    v = 1;
  }
  if (v < 2) {
    // v2 added transfer submissions and the pause mode setting
    cur = {
      ...cur,
      transferSubmissions: cur.transferSubmissions ?? {},
      settings: { ...initialState().settings, ...(cur.settings as object | undefined), pauseMode: false },
    };
    v = 2;
  }
  if (v < 3) {
    // v3 added the 90-day program
    cur = { ...cur, program: cur.program ?? initialState().program };
    v = 3;
  }
  const base = initialState();
  return { ...base, ...(cur as Partial<AcademyState>), schemaVersion: SCHEMA_VERSION };
}

export function newProfile(displayName: string, now: number): Profile {
  return {
    id: `local-${now.toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    displayName: displayName.trim().slice(0, 40) || "Lernende:r",
    createdAt: now,
    locale: "de",
    privacyNoticeVersion: "2026-10-draft",
    privacyNoticeAcceptedAt: now,
  };
}

// ---------- Pure state transitions ----------

function addXp(s: AcademyState, reason: XpReason, ref: string, now: number): AcademyState {
  return { ...s, xpLog: [...s.xpLog, { at: now, reason, amount: XP_RULES[reason], ref }] };
}

function unlock(s: AcademyState, id: string, now: number): AcademyState {
  if (s.achievements[id] || !ACHIEVEMENTS.some((a) => a.id === id)) return s;
  return { ...s, achievements: { ...s.achievements, [id]: now } };
}

export function totalXp(s: AcademyState): number {
  return s.xpLog.reduce((a, b) => a + b.amount, 0);
}

export function completeLesson(s: AcademyState, lessonId: string, courseVersion: string, now: number): AcademyState {
  if (s.lessonsCompleted[lessonId]) return s;
  let next: AcademyState = { ...s, lessonsCompleted: { ...s.lessonsCompleted, [lessonId]: { at: now, courseVersion } } };
  next = addXp(next, "lessonCompleted", lessonId, now);
  return unlock(next, "first-lesson", now);
}

export function recordAnswer(
  s: AcademyState,
  q: Question,
  r: GradeResult,
  meta: { durationMs: number; confidence?: Confidence; context: AttemptLog["context"]; now: number },
): AcademyState {
  const log: AttemptLog = {
    questionId: q.id,
    objectiveId: q.objectiveId,
    score: r.score,
    at: meta.now,
    durationMs: meta.durationMs,
    confidence: meta.confidence,
    errorCategories: r.errorCategories,
    context: meta.context,
  };
  const prevReview = s.reviews[q.id];
  // Free-text answers are provisional: they are logged but do not move the review box.
  const review = r.needsManualReview
    ? prevReview
    : scheduleNext(prevReview, { questionId: q.id, objectiveId: q.objectiveId, score: r.score, confidence: meta.confidence, now: meta.now });
  let next: AcademyState = {
    ...s,
    attempts: [...s.attempts, log].slice(-MAX_ATTEMPT_LOGS),
    reviews: review ? { ...s.reviews, [q.id]: review } : s.reviews,
  };
  if (r.correct && !r.needsManualReview && !s.firstCorrect.includes(q.id)) {
    next = { ...next, firstCorrect: [...next.firstCorrect, q.id] };
    next = addXp(next, "questionFirstCorrect", q.id, meta.now);
  }
  if (meta.context === "review") next = addXp(next, "reviewAnswered", q.id, meta.now);
  // Achievement: delayed recall (≥ 3 days since first attempt, correct)
  const first = s.attempts.find((a) => a.questionId === q.id);
  if (first && r.correct && meta.now - first.at >= 3 * 86_400_000) next = unlock(next, "delayed-recall", meta.now);
  // Achievement: calibrated confidence (sure & right or guessed & wrong) 10 times
  const calibrated = next.attempts.filter((a) => (a.confidence === 3 && a.score >= 0.999) || (a.confidence === 1 && a.score < 0.5)).length;
  if (calibrated >= 10) next = unlock(next, "honest-confidence", meta.now);
  return next;
}

export function recordQuizAttempt(s: AcademyState, rec: QuizAttemptRecord): AcademyState {
  let next: AcademyState = { ...s, quizAttempts: [...s.quizAttempts, rec] };
  const alreadyPassed = s.quizAttempts.some((a) => a.moduleId === rec.moduleId && a.kind === rec.kind && a.passed);
  if (rec.passed && !alreadyPassed) {
    next = addXp(next, "quizPassed", rec.id, rec.at);
    if (rec.moduleId === "M01" && rec.kind === "module-exam") next = unlock(next, "module-1", rec.at);
  }
  return next;
}

export function recordSimulation(
  s: AcademyState,
  scenario: Scenario,
  moveIds: string[],
  handover: HandoverNote,
  now: number,
): { state: AcademyState; evaluation: SimulationEvaluation } {
  const st = replay(scenario, moveIds);
  const ev = evaluate(scenario, st, handover);
  const rec: SimulationRecord = {
    id: `sim-${now.toString(36)}`,
    scenarioId: scenario.id,
    scenarioVersion: scenario.version,
    at: now,
    moveIds,
    handover,
    total: ev.total,
    passed: ev.passed,
    rubricVersion: ev.rubricVersion,
    competencyScores: Object.fromEntries(ev.competencies.filter((c) => c.tested).map((c) => [c.competency, c.score])),
  };
  let next: AcademyState = { ...s, simulations: [...s.simulations, rec] };
  next = addXp(next, "simulationFinished", rec.id, now);
  const passedBefore = s.simulations.some((x) => x.scenarioId === scenario.id && x.passed);
  if (ev.passed && !passedBefore) next = addXp(next, "simulationPassed", rec.id, now);
  next = unlock(next, "first-sim", now);
  if (st.outcome === "respect_no") next = unlock(next, "respect-no", now);
  if (ev.competencies.find((c) => c.competency === "dokumentation")?.score === 100) next = unlock(next, "clean-handover", now);
  return { state: next, evaluation: ev };
}

export function submitTransfer(s: AcademyState, moduleId: string, text: string, selfCheck: string[], now: number): AcademyState {
  const first = !s.transferSubmissions[moduleId];
  let next: AcademyState = {
    ...s,
    transferSubmissions: { ...s.transferSubmissions, [moduleId]: { at: now, text: text.slice(0, 8000), selfCheck } },
  };
  if (first) next = addXp(next, "transferTaskSubmitted", moduleId, now);
  return next;
}

/** Days with any learning action – used for the non-punitive "active days" indicator. */
export function activityTimestamps(s: AcademyState): number[] {
  return [
    ...s.attempts.map((a) => a.at),
    ...Object.values(s.lessonsCompleted).map((l) => l.at),
    ...s.simulations.map((x) => x.at),
  ];
}

// ---------- 90-Tage-Programm ----------

export function startProgram(s: AcademyState, now: number): AcademyState {
  if (s.program.startedAt) return s;
  return { ...s, program: { ...s.program, startedAt: now } };
}

export function completeProgramDay(s: AcademyState, day: number, now: number): AcademyState {
  if (s.program.dayCompletedAt[day]) return s;
  return { ...s, program: { ...s.program, dayCompletedAt: { ...s.program.dayCompletedAt, [day]: now } } };
}

export function fastTrackDay(s: AcademyState, day: number): AcademyState {
  if (s.program.fastTrack.includes(day)) return s;
  return { ...s, program: { ...s.program, fastTrack: [...s.program.fastTrack, day] } };
}

export function recordReviewSession(s: AcademyState, now: number): AcademyState {
  return { ...s, program: { ...s.program, reviewSessions: [...s.program.reviewSessions, now].slice(-500) } };
}
