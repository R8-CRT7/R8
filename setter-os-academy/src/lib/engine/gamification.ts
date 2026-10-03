// Gamification – motivates practice without claiming competence.
// Rules (see LEARNING_SCIENCE.md §Gamification):
//  * XP only for learning actions, never for logins.
//  * No streak that "breaks": we show active days in the last 7 days; pauses are explicitly allowed.
//  * Nothing earned is ever taken away. No purchase triggers.
//  * Level ≠ competence. The UI always shows mastery separately.

export const XP_RULES = {
  lessonCompleted: 30,
  questionFirstCorrect: 10, // only the first correct answer per question counts
  reviewAnswered: 4, // any review answer, right or wrong – effort counts
  quizPassed: 50,
  simulationFinished: 40,
  simulationPassed: 60,
  transferTaskSubmitted: 40,
} as const;

export type XpReason = keyof typeof XP_RULES;

export const LEVELS = [
  { level: 1, xp: 0, title: "Einsteiger:in" },
  { level: 2, xp: 150, title: "Zuhörer:in" },
  { level: 3, xp: 400, title: "Gesprächsstarter:in" },
  { level: 4, xp: 800, title: "Qualifizierer:in" },
  { level: 5, xp: 1400, title: "Terminprofi in Ausbildung" },
  { level: 6, xp: 2200, title: "Setter:in (Praxisniveau in Prüfung)" },
] as const;

export function levelFor(xp: number) {
  let cur: (typeof LEVELS)[number] = LEVELS[0];
  for (const l of LEVELS) if (xp >= l.xp) cur = l;
  const next = LEVELS.find((l) => l.xp > xp);
  return {
    ...cur,
    nextXp: next?.xp ?? null,
    progress: next ? (xp - cur.xp) / (next.xp - cur.xp) : 1,
  };
}

const DAY = 86_400_000;
/** Active learning days in the last 7 calendar days (local time is approximated via UTC days). */
export function activeDaysLast7(activityTimestamps: number[], now: number): number {
  const today = Math.floor(now / DAY);
  return new Set(activityTimestamps.map((t) => Math.floor(t / DAY)).filter((d) => today - d < 7 && d <= today)).size;
}

export interface AchievementDef {
  id: string;
  title: string;
  description: string;
  icon: string;
}

export const ACHIEVEMENTS: AchievementDef[] = [
  { id: "first-lesson", title: "Erster Schritt", description: "Erste Lektion abgeschlossen.", icon: "◆" },
  { id: "module-1", title: "Fundament gelegt", description: "Abschlussquiz Modul 1 bestanden.", icon: "▲" },
  { id: "first-sim", title: "Erstes Gespräch", description: "Erste Simulation beendet.", icon: "◎" },
  { id: "respect-no", title: "Nein heißt Nein", description: "Ein ausdrückliches Nein in der Simulation respektiert.", icon: "✋" },
  { id: "clean-handover", title: "Saubere Übergabe", description: "Übergabenotiz ohne Fehler ausgefüllt.", icon: "✎" },
  { id: "delayed-recall", title: "Langzeitgedächtnis", description: "Eine Frage nach ≥ 3 Tagen Abstand richtig beantwortet.", icon: "⟲" },
  { id: "honest-confidence", title: "Gute Selbsteinschätzung", description: "10 Antworten mit treffender Sicherheitsangabe.", icon: "◐" },
];
