// Deterministic, measured conversation metrics (no AI involved). Shown separately from the coach's estimate.
import { normalizeText } from "../engine/quiz";

export interface FreeTurn {
  role: "setter" | "customer" | "system";
  text: string;
}

const OPEN_STARTERS = ["was", "wie", "welche", "welcher", "welches", "wodurch", "woran", "wobei", "inwiefern", "wofuer", "womit", "wann", "wer", "wo", "erzaehlen", "beschreiben"];

/** Deterministic red flags – phrases that are pressure, false scarcity or unverifiable promises in this course. */
export const RED_FLAG_PATTERNS: { re: RegExp; label: string }[] = [
  { re: /nur (noch )?heute/i, label: "Künstliche Verknappung („nur heute“)" },
  { re: /letzte chance/i, label: "Künstliche Verknappung („letzte Chance“)" },
  { re: /(angebot|preis|aktion) (gilt|endet) (nur )?(noch )?(bis )?(morgen|heute)/i, label: "Befristungsdruck" },
  { re: /garantiert|100 ?%( sicher)?|auf jeden fall .*(gefördert|sparen)/i, label: "Garantie-/Erfolgsversprechen" },
  { re: /förderung (ist )?(ihnen |dir )?sicher/i, label: "Ungeprüfte Förderzusage" },
  { re: /ich (trage|buche) (sie|dich) (einfach|jetzt)/i, label: "Termin ohne Zustimmung" },
  { re: /(alle|ihre) nachbarn (haben|sind)/i, label: "Unbelegter Social Proof" },
];

export function questionSentences(text: string): string[] {
  return text.split(/(?<=[?])/).map((s) => s.trim()).filter((s) => s.endsWith("?"));
}

export function isOpenQuestion(q: string): boolean {
  const words = normalizeText(q).split(" ");
  // look at the first 4 words – "Und was …", "Darf ich fragen, wie …"
  return words.slice(0, 4).some((w) => OPEN_STARTERS.includes(w));
}

export interface MeasuredMetrics {
  setterMessages: number;
  questions: number;
  openQuestions: number;
  multiQuestionMessages: number;
  avgWordsPerMessage: number;
  longestMessageWords: number;
  redFlags: { turn: number; label: string; quote: string }[];
}

export function measure(transcript: FreeTurn[]): MeasuredMetrics {
  const setter = transcript.map((t, i) => ({ ...t, turn: i })).filter((t) => t.role === "setter");
  let questions = 0;
  let open = 0;
  let multi = 0;
  let words = 0;
  let longest = 0;
  const redFlags: MeasuredMetrics["redFlags"] = [];
  for (const m of setter) {
    const qs = questionSentences(m.text);
    questions += qs.length;
    open += qs.filter(isOpenQuestion).length;
    if (qs.length >= 2) multi++;
    const w = m.text.split(/\s+/).filter(Boolean).length;
    words += w;
    longest = Math.max(longest, w);
    for (const f of RED_FLAG_PATTERNS) {
      const hit = m.text.match(f.re);
      if (hit) redFlags.push({ turn: m.turn, label: f.label, quote: hit[0] });
    }
  }
  return {
    setterMessages: setter.length,
    questions,
    openQuestions: open,
    multiQuestionMessages: multi,
    avgWordsPerMessage: setter.length ? Math.round(words / setter.length) : 0,
    longestMessageWords: longest,
    redFlags,
  };
}
