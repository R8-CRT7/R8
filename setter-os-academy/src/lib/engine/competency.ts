// Personal competency tree (pure). A concept's level is the WEAKEST level of its linked objectives:
// one well-practised objective must not hide an untested one. Calendar time never raises a level.
import type { Concept, Track } from "../types";
import type { MasteryLevel } from "./review";

export type ConceptLevel = MasteryLevel | "in_vorbereitung";
const ORDER: MasteryLevel[] = ["nicht_geprueft", "im_aufbau", "gefestigt", "gesichert"];

export interface ConceptState {
  concept: Concept;
  level: ConceptLevel;
  /** objectives at ≥ gefestigt / linked objectives */
  solid: number;
  total: number;
  prerequisitesMet: boolean;
  missingPrerequisites: string[];
}

export function conceptStates(concepts: Concept[], objectiveMastery: Record<string, MasteryLevel>): ConceptState[] {
  const level = new Map<string, ConceptLevel>();
  for (const c of concepts) {
    if (!c.objectiveIds.length) level.set(c.id, "in_vorbereitung");
    else level.set(c.id, ORDER[Math.min(...c.objectiveIds.map((o) => ORDER.indexOf(objectiveMastery[o] ?? "nicht_geprueft")))]!);
  }
  return concepts.map((c) => {
    const missing = c.prerequisites.filter((p) => {
      const l = level.get(p);
      return l !== "gefestigt" && l !== "gesichert";
    });
    return {
      concept: c,
      level: level.get(c.id)!,
      solid: c.objectiveIds.filter((o) => ["gefestigt", "gesichert"].includes(objectiveMastery[o] ?? "")).length,
      total: c.objectiveIds.length,
      prerequisitesMet: missing.length === 0,
      missingPrerequisites: missing,
    };
  });
}

export type TrackReadiness = "bereit" | "teilweise" | "offen" | "inhalt_fehlt";

/** A specialization is "bereit" only when every required concept is at least "gefestigt". */
export function trackReadiness(t: Track, states: ConceptState[]): { readiness: TrackReadiness; met: number; total: number } {
  const req = t.requiredConcepts.map((id) => states.find((s) => s.concept.id === id));
  const met = req.filter((s) => s && (s.level === "gefestigt" || s.level === "gesichert")).length;
  const anyMissingContent = req.some((s) => !s || s.level === "in_vorbereitung");
  const readiness: TrackReadiness = met === req.length ? "bereit" : anyMissingContent && met === 0 ? "inhalt_fehlt" : met > 0 ? "teilweise" : "offen";
  return { readiness, met, total: req.length };
}

/** Concepts to strengthen next: tested-but-weak first, then untested whose prerequisites are solid. */
export function nextConcepts(states: ConceptState[], limit = 3): ConceptState[] {
  const weak = states.filter((s) => s.level === "im_aufbau");
  const ready = states.filter((s) => s.level === "nicht_geprueft" && s.prerequisitesMet);
  return [...weak, ...ready].slice(0, limit);
}
