// FREE-TEXT AI CUSTOMER. Knows the scenario's hidden facts and persona; knows nothing about scoring.
// The coach (coachAI.ts) never sees this prompt and never produces customer replies.
import type { Scenario, ScenarioOutcome } from "../types";
import type { FreeTurn } from "./metrics";
import { AiError, type AiRouter } from "./types-router";

export const MAX_SETTER_CHARS = 800;
export const CONTEXT_TURNS = 24; // older turns are summarised to keep the context small

export interface FreeSimState {
  scenarioId: string;
  scenarioVersion: number;
  mode: TrainingMode;
  transcript: FreeTurn[];
  revealed: string[];
  mood: number; // 0..10, starts at scenario.startRapport
  finished: boolean;
  outcome: ScenarioOutcome | "lost" | null;
  appointmentSlot: string | null;
  hintsUsed: number;
}

export type TrainingMode = "lern" | "praxis" | "pruefung";

export function startFreeSim(s: Scenario, mode: TrainingMode): FreeSimState {
  return {
    scenarioId: s.id,
    scenarioVersion: s.version,
    mode,
    transcript: [{ role: "customer", text: s.openingMessage }],
    revealed: [],
    mood: s.startRapport,
    finished: false,
    outcome: null,
    appointmentSlot: null,
    hintsUsed: 0,
  };
}

function transcriptBlock(t: FreeTurn[]): string {
  const visible = t.filter((x) => x.role !== "system");
  const cut = visible.length > CONTEXT_TURNS ? visible.length - CONTEXT_TURNS : 0;
  const head = cut ? `[${cut} frühere Nachrichten gekürzt – ihr Inhalt ist in „Bereits preisgegeben“ und „Stimmung“ berücksichtigt.]\n` : "";
  return head + visible.slice(cut).map((x) => `${x.role === "setter" ? "SETTER" : "KUNDE"}: ${x.text}`).join("\n");
}

/** Builds the complete, stateless customer prompt. Exported for tests (context size, content). */
export function buildCustomerPrompt(s: Scenario, st: FreeSimState): string {
  const ai = s.ai!;
  const facts = s.facts
    .map((f) => `- ${f.key} | ${f.label}: „${f.value}“ | preisgeben nur wenn: ${ai.revealRules[f.key] ?? "der Setter gezielt danach fragt"}${st.revealed.includes(f.key) ? " | BEREITS PREISGEGEBEN" : ""}`)
    .join("\n");
  return `Du spielst in einem Vertriebstraining eine fiktive Person, die mit einem Appointment Setter chattet. Du bist NICHT der Trainer und gibst keine Tipps.

PERSON: ${s.persona.name}, ${s.persona.role}
PERSÖNLICHKEIT: ${ai.personality}
SPRECHSTIL: ${ai.speakingStyle}
AUSGANGSLAGE: ${ai.situation}
ANLIEGEN: ${ai.concern}
HINTERGRUND: ${ai.background}
BEDÜRFNISSE: ${ai.needs.join("; ")}
EIGENE ZIELE IM GESPRÄCH: ${ai.customerGoals.join("; ")}
MÖGLICHE EINWÄNDE (nur wenn passend): ${ai.objections.map((o) => `wenn ${o.trigger} → ${o.reaction}`).join(" | ")}
FACHFRAGEN, DIE DU STELLEN KANNST (der Setter darf sie nicht selbst fachlich beantworten): ${ai.adviceBoundaries.join("; ")}
WIE DAS GESPRÄCH AUSGEHEN KANN: ${ai.outcomeGuidance}
KANAL: ${s.channel} (${s.market}, ${s.direction})

VERTRAULICHE FAKTEN (die Wahrheit über dich – nie widersprechen):
${facts}

REGELN:
1. Bleib konsequent in der Rolle. Antworte auf Deutsch, kurz wie im Chat (1–3 Sätze), im beschriebenen Stil.
2. Gib vertrauliche Fakten NUR preis, wenn die letzte Setter-Nachricht passend danach fragt oder es natürlich ins Gespräch passt. Verrate nie alles auf einmal. Nenne nie den Schlüssel (z. B. „need“).
3. Widersprich nie früheren Aussagen oder den Fakten. Erinnere dich an alles im Verlauf.
4. Arbeite NICHT auf einen Termin hin. Stimme einem Termin nur zu, wenn er für dich wirklich sinnvoll ist und der Setter respektvoll war. Disqualifizierung, Nachfassen später oder ein Nein sind genauso realistische Ausgänge.
5. Reagiere realistisch: auf Druck, falsche Versprechen, Fachjargon oder ignorierte Neins mit Ablehnung, Misstrauen oder Gesprächsende. Auf gutes Zuhören mit mehr Offenheit.
6. Wenn der Setter fachliche Zusagen macht (Preis, Förderung, Technik), reagiere wie ein echter Kunde – du darfst sie glauben oder misstrauen, aber du bewertest nichts.
7. Beende das Gespräch, wenn ein Termin mit Zeit vereinbart und bestätigt ist, wenn du eine Ablehnung ausgesprochen hast und der Setter sie akzeptiert, wenn der Setter sauber disqualifiziert/verabschiedet, oder wenn dich das Gespräch verärgert.

STIMMUNG BISHER (0 = verärgert, 10 = sehr offen): ${st.mood}
BEREITS PREISGEGEBEN: ${st.revealed.length ? st.revealed.join(", ") : "nichts"}

VERLAUF:
${transcriptBlock(st.transcript)}

Antworte jetzt als ${s.persona.name} auf die letzte SETTER-Nachricht. Gib NUR ein JSON-Objekt zurück, ohne weiteren Text:
{"reply": "deine Chat-Antwort", "revealed": ["Schlüssel der Fakten, die du IN DIESER Antwort neu preisgibst"], "mood": 0-10, "conversation_over": true|false, "outcome": "book"|"nurture"|"disqualify"|"respect_no"|"handoff"|"lost"|null, "appointment_slot": "vereinbarter Termin oder null"}
Regeln für "outcome": nur setzen, wenn conversation_over true ist. book = Termin mit konkreter Zeit vereinbart; nurture = späterer Kontakt/Infomaterial vereinbart; disqualify = Setter hat ehrlich festgestellt, dass es nicht passt; respect_no = du hast abgelehnt und der Setter hat das akzeptiert; lost = du brichst verärgert ab.`;
}

export interface CustomerReply {
  reply: string;
  revealed: string[];
  mood: number;
  conversationOver: boolean;
  outcome: ScenarioOutcome | "lost" | null;
  appointmentSlot: string | null;
}

const OUTCOMES = ["book", "nurture", "disqualify", "respect_no", "handoff", "lost"];

/** Tolerant JSON extraction + strict validation. Throws invalid_output when the shape is wrong. */
export function parseCustomerReply(raw: string, s: Scenario): CustomerReply {
  const m = raw.match(/\{[\s\S]*\}/);
  if (!m) throw new AiError("invalid_output", "Kunde hat nicht im erwarteten Format geantwortet.", raw);
  let o: Record<string, unknown>;
  try {
    o = JSON.parse(m[0]);
  } catch {
    throw new AiError("invalid_output", "Antwort war kein gültiges JSON.", raw);
  }
  const reply = typeof o.reply === "string" ? o.reply.trim() : "";
  if (!reply) throw new AiError("invalid_output", "Leere Kundenantwort.", raw);
  const keys = new Set(s.facts.map((f) => f.key));
  const revealed = Array.isArray(o.revealed) ? o.revealed.map(String).filter((k) => keys.has(k)) : [];
  const moodN = Number(o.mood);
  const over = o.conversation_over === true;
  const outcome = over && typeof o.outcome === "string" && OUTCOMES.includes(o.outcome) ? (o.outcome as CustomerReply["outcome"]) : over ? "lost" : null;
  return {
    reply: reply.slice(0, 900),
    revealed,
    mood: Number.isFinite(moodN) ? Math.max(0, Math.min(10, Math.round(moodN))) : NaN,
    conversationOver: over,
    outcome,
    appointmentSlot: typeof o.appointment_slot === "string" && o.appointment_slot.trim() ? o.appointment_slot.trim().slice(0, 120) : null,
  };
}

export function applySetterMessage(st: FreeSimState, text: string): FreeSimState {
  const clean = text.replace(/\s+/g, " ").trim().slice(0, MAX_SETTER_CHARS);
  if (!clean) throw new AiError("invalid_output", "Leere Nachricht.");
  if (st.finished) throw new AiError("invalid_output", "Gespräch ist beendet.");
  return { ...st, transcript: [...st.transcript, { role: "setter", text: clean }] };
}

export function applyCustomerReply(s: Scenario, st: FreeSimState, r: CustomerReply): FreeSimState {
  const revealed = [...new Set([...st.revealed, ...r.revealed])];
  const mood = Number.isNaN(r.mood) ? st.mood : r.mood;
  const setterTurns = st.transcript.filter((t) => t.role === "setter").length;
  const transcript: FreeTurn[] = [...st.transcript, { role: "customer", text: r.reply }];
  let finished = r.conversationOver;
  let outcome = r.outcome;
  if (!finished && setterTurns >= s.maxTurns + 6) {
    finished = true;
    outcome = "lost";
    transcript.push({ role: "system", text: "Gesprächszeit abgelaufen – der Interessent hat das Gespräch beendet." });
  }
  return { ...st, transcript, revealed, mood, finished, outcome, appointmentSlot: r.appointmentSlot ?? st.appointmentSlot };
}

/** One full customer turn: setter message in, customer reply out. Removes the setter message again on failure. */
export async function customerTurn(router: AiRouter, s: Scenario, st: FreeSimState, setterText: string, opts: { signal?: AbortSignal; onText?: (t: string) => void } = {}) {
  const withMsg = applySetterMessage(st, setterText);
  const res = await router.complete({ role: "customer", prompt: buildCustomerPrompt(s, withMsg), signal: opts.signal, onText: opts.onText });
  const parsed = parseCustomerReply(res.text, s);
  return { state: applyCustomerReply(s, withMsg, parsed), meta: { providerId: res.providerId, tier: res.tierApplied, costEur: res.costEur } };
}
