// Typed access to the JSON content. Content is bundled at build time (no backend needed).
import type { KnowledgeEntry, KnowledgeSource, ModuleContent, ProgramStage, Question, Scenario } from "../types";
import sourcesJson from "@content/sources.json";
import knowledgeJson from "@content/knowledge.json";
import curriculumJson from "@content/curriculum.json";
import m01 from "@content/modules/M01.json";
import m02 from "@content/modules/M02.json";
import qM01 from "@content/questions/M01.json";
import qM02 from "@content/questions/M02.json";
import sim001 from "@content/scenarios/SIM-001.json";
import sim002 from "@content/scenarios/SIM-002.json";
import sim003 from "@content/scenarios/SIM-003.json";
import sim004 from "@content/scenarios/SIM-004.json";
import programJson from "@content/program.json";
import glossaryJson from "@content/glossary.json";

export interface CurriculumEntry {
  id: string;
  number: number;
  title: string;
  subtitle: string;
  prerequisites: string[];
  topics: string[];
  status: "verfuegbar" | "in_vorbereitung";
}

export const COURSE_VERSION = "0.2.0-stufe1";

export const sources = sourcesJson as KnowledgeSource[];
export const knowledge = knowledgeJson as KnowledgeEntry[];
export const curriculum = curriculumJson as CurriculumEntry[];
export const modules = [m01, m02] as unknown as ModuleContent[];
export const questions = [...qM01, ...qM02] as unknown as Question[];
export const scenarios = [sim001, sim002, sim003, sim004] as unknown as Scenario[];
export const program = programJson as unknown as ProgramStage[];

export const questionById = (id: string) => questions.find((q) => q.id === id);
export const moduleById = (id: string) => modules.find((m) => m.id === id);
export const scenarioById = (id: string) => scenarios.find((s) => s.id === id);
export const sourceById = (id: string) => sources.find((s) => s.id === id);
export const lessonById = (id: string) => modules.flatMap((m) => m.lessons).find((l) => l.id === id);
export const objectiveById = (id: string) => modules.flatMap((m) => m.objectives).find((o) => o.id === id);

/** Module exam or stage check as one quiz definition. */
export interface QuizDef {
  id: string;
  title: string;
  eyebrow: string;
  kind: "module-exam" | "stage-check";
  questionIds: string[];
  passThreshold: number;
  backHref: string;
}
export function quizById(id: string): QuizDef | undefined {
  const m = moduleById(id);
  if (m) return { id: m.id, title: `Abschlussquiz: ${m.title}`, eyebrow: `Modul ${m.number}`, kind: "module-exam", questionIds: m.examQuestionIds, passThreshold: m.passThreshold, backHref: `/learn/${m.id}/` };
  const st = program.find((p) => p.id === id && p.available);
  if (st) return { id: st.id, title: st.check.title, eyebrow: `Stufe ${st.number}`, kind: "stage-check", questionIds: st.check.questionIds, passThreshold: st.check.passThreshold, backHref: "/plan/" };
  return undefined;
}
export const allQuizIds = () => [...modules.map((m) => m.id), ...program.filter((p) => p.available).map((p) => p.id)];

export const glossary = glossaryJson as { term: string; definition: string; lessonId: string }[];

/** All Kursbuch chapters across modules, with a stable key for bookmarks/notes/highlights. */
export function bookChapters() {
  return modules.flatMap((m) =>
    m.lessons.flatMap((l) =>
      l.blocks.flatMap((b) =>
        b.kind === "book" ? [{ key: `${l.id}:${b.chapter}`, moduleId: m.id, moduleTitle: m.title, lessonId: l.id, lessonTitle: l.title, chapter: b.chapter, title: b.title, paragraphs: b.paragraphs, sourceIds: b.sourceIds ?? [], skills: l.blocks.filter((x) => x.kind === "skill").map((x) => (x as { name: string }).name), checks: l.blocks.filter((x) => x.kind === "check").map((x) => (x as { questionId: string }).questionId) }] : [],
      ),
    ),
  );
}
