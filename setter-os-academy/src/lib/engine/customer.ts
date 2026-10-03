// CUSTOMER SIMULATOR – plays the prospect.
// Knows the hidden facts and the reply rules of a scenario. Knows NOTHING about scoring.
// (The coach in ./coach.ts never produces customer replies. Roles are strictly separated.)

import type { ReplyCondition, Scenario, ScenarioMove, SimulationState } from "../types";

export function startSimulation(s: Scenario): SimulationState {
  return {
    scenarioId: s.id,
    scenarioVersion: s.version,
    turn: 0,
    rapport: s.startRapport,
    revealed: [],
    flags: [],
    usedMoves: [],
    transcript: [{ turn: 0, role: "customer", text: s.openingMessage }],
    outcome: null,
    finished: false,
  };
}

function matches(cond: ReplyCondition | undefined, st: SimulationState): boolean {
  if (!cond) return true;
  if (cond.minRapport !== undefined && st.rapport < cond.minRapport) return false;
  if (cond.maxRapport !== undefined && st.rapport > cond.maxRapport) return false;
  if (cond.factsRevealed?.some((f) => !st.revealed.includes(f))) return false;
  if (cond.factsMissing?.some((f) => st.revealed.includes(f))) return false;
  if (cond.flags?.some((f) => !st.flags.includes(f))) return false;
  if (cond.notFlags?.some((f) => st.flags.includes(f))) return false;
  return true;
}

/** Moves the learner may choose now. Deterministic order (authoring order), so tests are stable. */
export function availableMoves(s: Scenario, st: SimulationState): ScenarioMove[] {
  if (st.finished) return [];
  return s.moves.filter(
    (m) =>
      !st.usedMoves.includes(m.id) &&
      (m.requires ?? []).every((f) => st.revealed.includes(f)) &&
      (m.requiresFlags ?? []).every((f) => st.flags.includes(f)) &&
      !(m.hiddenByFlags ?? []).some((f) => st.flags.includes(f)),
  );
}

/** Applies one setter move and produces the customer's reply. Pure: returns a new state. */
export function applyMove(s: Scenario, st: SimulationState, moveId: string): SimulationState {
  if (st.finished) throw new Error("Simulation bereits beendet");
  const move = availableMoves(s, st).find((m) => m.id === moveId);
  if (!move) throw new Error(`Zug ${moveId} ist im aktuellen Zustand nicht verfügbar`);

  const turn = st.turn + 1;
  const flags = [...st.flags, ...(move.setsFlags ?? [])];
  const rapport = Math.max(0, Math.min(10, st.rapport + (move.rapport ?? 0)));
  const revealed = [...st.revealed];
  const interim: SimulationState = { ...st, rapport, flags, revealed };
  const reply = move.reply.find((r) => matches(r.when, interim)) ?? move.reply[move.reply.length - 1]!;
  // A question only yields its fact if the customer is willing (rapport > 1) – a hostile customer shares nothing.
  // What the customer states explicitly in the reply text (reply.reveals) is always known.
  const learned = [...(rapport > 1 ? (move.reveals ?? []) : []), ...(reply.reveals ?? [])];
  for (const f of learned) if (!revealed.includes(f)) revealed.push(f);
  const replyFlags = [...flags, ...(reply.setsFlags ?? [])];

  let outcome: SimulationState["outcome"] = reply.ends ?? move.ends ?? null;
  const transcript = [
    ...st.transcript,
    { turn, role: "setter" as const, text: move.text, moveId: move.id },
    { turn, role: "customer" as const, text: reply.text },
  ];
  let finished = outcome !== null;
  if (!finished && turn >= s.maxTurns) {
    finished = true;
    outcome = "lost";
    transcript.push({ turn, role: "system", text: "Gesprächszeit abgelaufen – der Interessent hat das Gespräch beendet." });
  }
  return {
    ...st,
    turn,
    rapport,
    revealed,
    flags: [...new Set(replyFlags)],
    usedMoves: [...st.usedMoves, move.id],
    transcript,
    outcome,
    finished,
  };
}

/** Replays a list of move ids – used for regression tests and to restore a saved session. */
export function replay(s: Scenario, moveIds: string[]): SimulationState {
  return moveIds.reduce((st, id) => applyMove(s, st, id), startSimulation(s));
}
