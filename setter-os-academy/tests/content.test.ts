import { describe, expect, it } from "vitest";
import { knowledge, modules, questions, scenarios, sources } from "@/lib/content";
import { validateContent } from "@/lib/content/validate";

describe("Content validation (CI gate)", () => {
  const issues = validateContent({ sources, knowledge, modules, questions, scenarios, now: Date.parse("2026-10-03") });
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
  it("reports warnings transparently (printed, not hidden)", () => {
    const warnings = issues.filter((i) => i.severity === "warning");
    console.log(`Content warnings: ${warnings.length}`, warnings.map((w) => `${w.ref}: ${w.message}`));
    expect(Array.isArray(warnings)).toBe(true);
  });
});
