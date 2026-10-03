// Learner state – pure, serialisable, versioned. No personal data beyond a self-chosen display name.
// Persistence adapter: ./storage.ts (localStorage today, Supabase later – same shape).

import { evaluate } from "../engine/coach";
import { replay } from "../engine/customer";
import { ACHIEVEMENTS, XP_RULES, type XpReason } from "../engine/gamification";
import { scheduleNext, type AttemptLog, type Confidence, type ItemReview } from "../engine/review";
import type { GradeResult, HandoverNote, Question, Scenario, SimulationEvaluation } from "../types";
import type { FreeEvaluation } from "../ai/coachAI";
import type { FreeTurn } from "../ai/metrics";
import type { TrainingMode } from "../ai/customerAI";
import type { SpendLog } from "../ai/router";

export const SCHEMA_VERSION = 4;

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
  aiSimulations: AiSimulationRecord[];
  ai: { paidCallsEnabled: boolean; monthlyBudgetEur: number; spendLog: SpendLog[]; consentNoticeSeen: boolean };
  reader: { bookmarks: string[]; notes: Record<string, string>; highlights: Record<string, string[]>; lastChapter: string | null };
}

export interface AiSimulationRecord {
  id: string;
  scenarioId: string;
  scenarioVersion: number;
  mode: TrainingMode;
  at: number;
  /** Stored only in this browser. Deletable in Einstellungen / Fehlergedächtnis. */
  transcript: FreeTurn[];
  handover: HandoverNote;
  revealed: string[];
  outcome: string | null;
  evaluation: FreeEvaluation;
  providerId: string;
}

export const MAX_AI_SIMULATIONS = 30;

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
    aiSimulations: [],
    ai: { paidCallsEnabled: false, monthlyBudgetEur: 0, spendLog: [], consentNoticeSeen: false },
    reader: { bookmarks: [], notes: {}, highlights: {}, lastChapter: null },
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
  if (v < 4) {
    // v4 added free-text AI simulations, AI cost settings (paid calls locked) and the Kursbuch reader
    const b = initialState();
    cur = { ...cur, aiSimulations: cur.aiSimulations ?? [], ai: cur.ai ?? b.ai, reader: cur.reader ?? b.reader };
    v = 4;
  }
  return sanitize(cur);
}

const kind = (x: unknown) => (Array.isArray(x) ? "array" : x === null ? "null" : typeof x);

/** Keeps only known top-level keys with the expected JSON kind; anything else falls back to the default. */
function sanitize(cur: Record<string, unknown>): AcademyState {
  const base = initialState() as unknown as Record<string, unknown>;
  const out: Record<string, unknown> = { ...base };
  for (const k of Object.keys(base)) {
    if (!(k in cur)) continue;
    const want = kind(base[k]);
    const got = kind(cur[k]);
    if (k === "profile") out[k] = got === "object" && typeof (cur[k] as Profile).displayName === "string" ? cur[k] : null;
    else if (want === "object" && got === "object") out[k] = { ...(base[k] as object), ...(cur[k] as object) };
    else if (want === got) out[k] = cur[k];
  }
  // arrays must contain objects with a timestamp where the engines expect one
  for (const k of ["attempts", "quizAttempts", "simulations", "aiSimulations", "xpLog"] as const)
    out[k] = (out[k] as unknown[]).filter((x) => x && typeof x === "object" && typeof (x as { at?: unknown }).at === "number");
  out.schemaVersion = SCHEMA_VERSION;
  return out as unknown as AcademyState;
}

export interface BackupCheck {
  ok: boolean;
  problems: string[];
  summary: { name: string | null; lessons: number; answers: number; simulations: number; schemaVersion: number | null };
}

/** Strict check BEFORE an import replaces anything. Rejects empty, foreign or newer-than-app files. */
export function checkBackup(text: string): BackupCheck {
  const problems: string[] = [];
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return { ok: false, problems: ["Kein gültiges JSON – die Datei ist beschädigt oder unvollständig."], summary: { name: null, lessons: 0, answers: 0, simulations: 0, schemaVersion: null } };
  }
  const o = (raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {}) as Record<string, unknown>;
  const v = typeof o.schemaVersion === "number" ? o.schemaVersion : null;
  if (kind(raw) !== "object") problems.push("Die Datei enthält kein Sicherungsobjekt.");
  else if (v === null) problems.push("Keine Versionsangabe – das ist keine Sicherung dieser Akademie.");
  else if (v > SCHEMA_VERSION) problems.push(`Die Sicherung stammt aus einer neueren App-Version (${v}). Bitte zuerst die App aktualisieren.`);
  if (v !== null && v >= 1 && !(o.profile && typeof o.profile === "object")) problems.push("Kein Lernprofil enthalten.");
  const lessons = o.lessonsCompleted && typeof o.lessonsCompleted === "object" ? Object.keys(o.lessonsCompleted).length : 0;
  const answers = Array.isArray(o.attempts) ? o.attempts.length : 0;
  const sims = (Array.isArray(o.simulations) ? o.simulations.length : 0) + (Array.isArray(o.aiSimulations) ? o.aiSimulations.length : 0);
  return {
    ok: problems.length === 0,
    problems,
    summary: { name: (o.profile as Profile | undefined)?.displayName ?? null, lessons, answers, simulations: sims, schemaVersion: v },
  };
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

// ---------- AI simulations & settings ----------

export function recordAiSimulation(s: AcademyState, rec: AiSimulationRecord): AcademyState {
  let next: AcademyState = { ...s, aiSimulations: [...s.aiSimulations, rec].slice(-MAX_AI_SIMULATIONS) };
  next = addXp(next, "simulationFinished", rec.id, rec.at);
  if (rec.evaluation.passed) {
    const passedBefore = s.aiSimulations.some((x) => x.scenarioId === rec.scenarioId && x.evaluation.passed);
    if (!passedBefore) next = addXp(next, "simulationPassed", rec.id, rec.at);
  }
  next = unlock(next, "first-sim", rec.at);
  if (rec.outcome === "respect_no" && rec.evaluation.gates.every((g) => !g.triggered)) next = unlock(next, "respect-no", rec.at);
  return next;
}

export function addSpend(s: AcademyState, e: SpendLog): AcademyState {
  return { ...s, ai: { ...s.ai, spendLog: [...s.ai.spendLog, e].slice(-2000) } };
}

export function deleteAiTranscripts(s: AcademyState): AcademyState {
  return { ...s, aiSimulations: [] };
}

/** Removes everything the error memory is built from (error categories, AI coach reports) – progress stays. */
export function deleteErrorMemory(s: AcademyState): AcademyState {
  return {
    ...s,
    attempts: s.attempts.map((a) => ({ ...a, errorCategories: [] })),
    aiSimulations: s.aiSimulations.map((x) => ({ ...x, evaluation: { ...x.evaluation, coach: null } })),
  };
}

// ---------- Reader ----------
export function toggleBookmark(s: AcademyState, key: string): AcademyState {
  const b = s.reader.bookmarks.includes(key) ? s.reader.bookmarks.filter((x) => x !== key) : [...s.reader.bookmarks, key];
  return { ...s, reader: { ...s.reader, bookmarks: b } };
}
export function setNote(s: AcademyState, key: string, text: string): AcademyState {
  const notes = { ...s.reader.notes };
  if (text.trim()) notes[key] = text.slice(0, 4000);
  else delete notes[key];
  return { ...s, reader: { ...s.reader, notes } };
}
export function addHighlight(s: AcademyState, key: string, text: string): AcademyState {
  const t = text.trim().replace(/\s+/g, " ").slice(0, 400);
  if (t.length < 3) return s;
  const cur = s.reader.highlights[key] ?? [];
  if (cur.includes(t)) return s;
  return { ...s, reader: { ...s.reader, highlights: { ...s.reader.highlights, [key]: [...cur, t] } } };
}
export function removeHighlight(s: AcademyState, key: string, text: string): AcademyState {
  return { ...s, reader: { ...s.reader, highlights: { ...s.reader.highlights, [key]: (s.reader.highlights[key] ?? []).filter((x) => x !== text) } } };
}
