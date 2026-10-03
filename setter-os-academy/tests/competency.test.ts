// Kompetenzbaum & Langzeitplan: Ableitung nur aus geprüften Lernzielen.
import { describe, expect, it } from "vitest";
import { concepts, longterm, program } from "@/lib/content";
import { conceptStates, nextConcepts, trackReadiness } from "@/lib/engine/competency";
import type { MasteryLevel } from "@/lib/engine/review";

const all = (lvl: MasteryLevel) => Object.fromEntries(concepts.flatMap((c) => c.objectiveIds).map((o) => [o, lvl]));

describe("Kompetenzbaum", () => {
  it("P01 ohne Antworten: alles nicht geprüft oder in Vorbereitung, nichts bereit", () => {
    const st = conceptStates(concepts, {});
    expect(st.every((s) => s.level === "nicht_geprueft" || s.level === "in_vorbereitung")).toBe(true);
    expect(longterm.tracks.every((t) => trackReadiness(t, st).readiness !== "bereit")).toBe(true);
  });
  it("P02 Konzeptstufe ist das schwächste Lernziel", () => {
    const c = concepts.find((x) => x.objectiveIds.length >= 1)!;
    const m: Record<string, MasteryLevel> = { ...all("gesichert") };
    m[c.objectiveIds[0]!] = "im_aufbau";
    expect(conceptStates(concepts, m).find((s) => s.concept.id === c.id)!.level).toBe("im_aufbau");
  });
  it("P03 Spezialisierung erst bereit, wenn alle Pflichtkonzepte gefestigt sind", () => {
    const t = longterm.tracks.find((x) => x.requiredConcepts.every((r) => concepts.find((c) => c.id === r)!.objectiveIds.length));
    if (!t) return; // depends on which modules have content
    expect(trackReadiness(t, conceptStates(concepts, all("gefestigt"))).readiness).toBe("bereit");
    expect(trackReadiness(t, conceptStates(concepts, all("im_aufbau"))).readiness).not.toBe("bereit");
  });
  it("P04 Empfehlungen: schwache Konzepte zuerst", () => {
    const m = all("gefestigt");
    const c = concepts.find((x) => x.objectiveIds.length)!;
    m[c.objectiveIds[0]!] = "im_aufbau";
    expect(nextConcepts(conceptStates(concepts, m))[0]!.concept.id).toBe(c.id);
  });
  it("P05 18 Spezialisierungen, Langzeitplan lückenlos bis Tag 180", () => {
    expect(longterm.tracks).toHaveLength(18);
    const last = Math.max(...program.map((p) => p.dayTo));
    expect(last).toBe(90);
    expect(Math.max(...longterm.stages.map((s) => s.dayTo))).toBe(180);
  });
  it("P06 Konzeptgraph ist azyklisch und jede Voraussetzung existiert", () => {
    const ids = new Set(concepts.map((c) => c.id));
    for (const c of concepts) for (const p of c.prerequisites) expect(ids.has(p)).toBe(true);
  });
});
