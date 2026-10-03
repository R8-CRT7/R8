// Typed access to the JSON content. Content is bundled at build time (no backend needed).
import type { KnowledgeEntry, KnowledgeSource, ModuleContent, Question, Scenario } from "../types";
import sourcesJson from "@content/sources.json";
import knowledgeJson from "@content/knowledge.json";
import curriculumJson from "@content/curriculum.json";
import m01 from "@content/modules/M01.json";
import qM01 from "@content/questions/M01.json";
import sim001 from "@content/scenarios/SIM-001.json";
import sim002 from "@content/scenarios/SIM-002.json";
import sim003 from "@content/scenarios/SIM-003.json";

export interface CurriculumEntry {
  id: string;
  number: number;
  title: string;
  subtitle: string;
  prerequisites: string[];
  topics: string[];
  status: "verfuegbar" | "in_vorbereitung";
}

export const COURSE_VERSION = "0.1.0-slice";

export const sources = sourcesJson as KnowledgeSource[];
export const knowledge = knowledgeJson as KnowledgeEntry[];
export const curriculum = curriculumJson as CurriculumEntry[];
export const modules = [m01] as unknown as ModuleContent[];
export const questions = [...qM01] as unknown as Question[];
export const scenarios = [sim001, sim002, sim003] as unknown as Scenario[];

export const questionById = (id: string) => questions.find((q) => q.id === id);
export const moduleById = (id: string) => modules.find((m) => m.id === id);
export const scenarioById = (id: string) => scenarios.find((s) => s.id === id);
export const sourceById = (id: string) => sources.find((s) => s.id === id);
export const lessonById = (id: string) => modules.flatMap((m) => m.lessons).find((l) => l.id === id);
export const objectiveById = (id: string) => modules.flatMap((m) => m.objectives).find((o) => o.id === id);
