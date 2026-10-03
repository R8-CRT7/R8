// Personal error memory: unifies quiz error categories, AI-coach weak criteria and violations,
// and offline-simulation weak moves into eight learner-facing classes.
import type { AcademyState } from "../store/state";
import type { ErrorCategory } from "../types";
import { scenarios } from "../content";

export type MistakeClass =
  | "wissen"
  | "begriffe"
  | "bedarf"
  | "fragen"
  | "gespraech"
  | "termin"
  | "dokumentation"
  | "recht";

export const MISTAKE_LABEL: Record<MistakeClass, string> = {
  wissen: "Wissensfehler",
  begriffe: "Missverstandene Begriffe",
  bedarf: "Unvollständige Bedarfsermittlung",
  fragen: "Ungeeignete Fragen",
  gespraech: "Unpassende Gesprächsführung",
  termin: "Fehler bei der Terminvereinbarung",
  dokumentation: "Dokumentationsfehler",
  recht: "Rechtliche/ethische Fehler",
};

/** What to practise for each class (lessons + scenarios). */
export const MISTAKE_PRACTICE: Record<MistakeClass, { lessons: string[]; scenarios: string[] }> = {
  wissen: { lessons: ["M01-L01", "M01-L02"], scenarios: [] },
  begriffe: { lessons: ["M01-L01", "M01-L05"], scenarios: [] },
  bedarf: { lessons: ["M01-L04", "M02-L03"], scenarios: ["SIM-001", "SIM-004"] },
  fragen: { lessons: ["M02-L03", "M01-L04"], scenarios: ["SIM-004"] },
  gespraech: { lessons: ["M02-L01", "M02-L02", "M02-L05"], scenarios: ["SIM-004"] },
  termin: { lessons: ["M01-L08", "M01-L05"], scenarios: ["SIM-001"] },
  dokumentation: { lessons: ["M01-L05", "M01-L08"], scenarios: ["SIM-002"] },
  recht: { lessons: ["M01-L06", "M01-L03"], scenarios: ["SIM-003"] },
};

const FROM_QUIZ: Record<ErrorCategory, MistakeClass> = {
  rollenverwechslung: "wissen",
  begriffsfehler: "begriffe",
  qualifizierungsfehler: "bedarf",
  rechtsfehler: "recht",
  ethikfehler: "recht",
  rechenfehler: "wissen",
  kommunikationsfehler: "fragen",
  prozessfehler: "termin",
  ueberinterpretation: "dokumentation",
  unvollstaendig: "wissen",
};
const FROM_COACH: Record<string, MistakeClass> = {
  eroeffnung: "gespraech",
  kommunikation: "gespraech",
  fragetechnik: "fragen",
  bedarfsermittlung: "bedarf",
  qualifizierung: "bedarf",
  empathie: "gespraech",
  einwaende: "gespraech",
  ablehnung: "recht",
  terminqualitaet: "termin",
  dokumentation: "dokumentation",
  recht_ethik: "recht",
};

export interface MistakeEvent {
  at: number;
  cls: MistakeClass;
  source: "quiz" | "ki-coach" | "simulation";
  ref: string;
  detail: string;
}

export function mistakeEvents(s: AcademyState): MistakeEvent[] {
  const out: MistakeEvent[] = [];
  for (const a of s.attempts)
    for (const c of a.errorCategories) {
      if (c === "unvollstaendig" && a.errorCategories.length > 1) continue; // counted via the specific category
      out.push({ at: a.at, cls: FROM_QUIZ[c], source: "quiz", ref: a.questionId, detail: c });
    }
  for (const x of s.aiSimulations) {
    const coach = x.evaluation.coach;
    for (const c of coach?.criteria ?? [])
      if (c.rating === "ausbaufaehig" || c.rating === "kritisch") out.push({ at: x.at, cls: FROM_COACH[c.id] ?? "gespraech", source: "ki-coach", ref: x.scenarioId, detail: `${c.id}: ${c.rating}` });
    for (const v of coach?.violations ?? []) out.push({ at: x.at, cls: "recht", source: "ki-coach", ref: x.scenarioId, detail: `„${v.quote}“ – ${v.rule}` });
    for (const r of x.evaluation.measured.redFlags) out.push({ at: x.at, cls: "recht", source: "ki-coach", ref: x.scenarioId, detail: r.label });
    if (x.evaluation.measured.fabricated > 0) out.push({ at: x.at, cls: "dokumentation", source: "ki-coach", ref: x.scenarioId, detail: "Übergabe mit nicht erfragten Angaben" });
  }
  for (const sim of s.simulations) {
    const sc = scenarios.find((z) => z.id === sim.scenarioId);
    for (const id of sim.moveIds) {
      const m = sc?.moves.find((mm) => mm.id === id);
      if (!m || (m.quality !== "bad" && m.quality !== "weak")) continue;
      const cls: MistakeClass = m.violation ? "recht" : m.intent === "ask" ? "fragen" : m.intent === "propose_booking" ? "termin" : "gespraech";
      out.push({ at: sim.at, cls, source: "simulation", ref: sim.scenarioId, detail: m.coachNote });
    }
  }
  return out.sort((a, b) => b.at - a.at);
}

const DAY = 86_400_000;
export function mistakeSummary(s: AcademyState, now: number) {
  const ev = mistakeEvents(s);
  return (Object.keys(MISTAKE_LABEL) as MistakeClass[])
    .map((cls) => {
      const mine = ev.filter((e) => e.cls === cls);
      const recent = mine.filter((e) => now - e.at <= 14 * DAY).length;
      const before = mine.filter((e) => now - e.at > 14 * DAY && now - e.at <= 28 * DAY).length;
      return { cls, label: MISTAKE_LABEL[cls], total: mine.length, recent, before, trend: recent < before ? "besser" : recent > before ? "häufiger" : "gleich", examples: mine.slice(0, 3) };
    })
    .filter((x) => x.total > 0)
    .sort((a, b) => b.recent - a.recent || b.total - a.total);
}
