import { describe, expect, it } from "vitest";
import { concepts, knowledge, longterm, modules, program, questions, scenarios, sources } from "@/lib/content";
import { moduleMinutes } from "@/lib/content/minutes";
import { validateContent } from "@/lib/content/validate";

describe("Content validation (CI gate)", () => {
  const issues = validateContent({ sources, knowledge, modules, questions, scenarios, program, concepts, longterm, now: Date.parse("2026-10-03") });
  it("has no content errors", () => {
    const errors = issues.filter((i) => i.severity === "error");
    expect(errors, JSON.stringify(errors, null, 2)).toEqual([]);
  });
  it("module 1 meets vertical-slice minimums", () => {
    const m1 = questions.filter((q) => q.moduleId === "M01");
    expect(m1.length).toBeGreaterThanOrEqual(10);
    expect(new Set(m1.map((q) => q.type)).size).toBeGreaterThanOrEqual(10);
    expect(scenarios.length).toBeGreaterThanOrEqual(3);
  });
  it("every available module has ≥ 2 hours of material and ≥ 25 questions", () => {
    for (const m of modules) {
      const mins = moduleMinutes(m, 1);
      expect(mins.total, m.id).toBeGreaterThanOrEqual(120);
      expect(questions.filter((q) => q.moduleId === m.id).length, m.id).toBeGreaterThanOrEqual(25);
      expect(m.lessons.every((l) => l.blocks.some((b) => b.kind === "book")), `${m.id} Kursbuch je Lektion`).toBe(true);
      expect(m.lessons.filter((l) => l.blocks.some((b) => b.kind === "skill")).length, `${m.id} Skill-Karten`).toBeGreaterThanOrEqual(5);
    }
  });
  it("stage 1 covers exactly 7 days", () => {
    const st = program.find((p) => p.id === "ST1")!;
    expect(st.days.map((d) => d.day)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(Math.max(...program.map((p) => p.dayTo))).toBe(90);
  });
  it("reports warnings transparently (printed, not hidden)", () => {
    const warnings = issues.filter((i) => i.severity === "warning");
    console.log(`Content warnings: ${warnings.length}`, warnings.map((w) => `${w.ref}: ${w.message}`));
    expect(Array.isArray(warnings)).toBe(true);
  });
});
