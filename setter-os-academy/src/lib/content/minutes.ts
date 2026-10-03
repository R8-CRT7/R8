// Transparent study-time estimate (shown to learners). Assumptions documented in LEARNING_SCIENCE.md §6:
// reading 170 words/min (careful study reading), 1.5 min per question, 2 min per reflection,
// 4 min per case study, 2 min per worked example; module extras: exam 1.2 min/question,
// 12 min per linked simulation, 20 min transfer task.
import type { Lesson, LessonBlock, ModuleContent } from "../types";

const WPM = 170;
const words = (s: string) => s.split(/\s+/).filter(Boolean).length;

function blockWords(b: LessonBlock): number {
  switch (b.kind) {
    case "text": return words((b.title ?? "") + " " + b.body);
    case "example": return words(b.title + " " + b.body);
    case "workedExample": return words(b.title + " " + b.steps.join(" "));
    case "caseStudy": return words(b.situation + " " + b.analysis);
    case "callout": return words(b.title + " " + b.body);
    case "book": return words(b.title + " " + b.paragraphs.join(" "));
    case "skill": return words([b.name, b.what, ...b.how, b.why, b.evidence, b.example, b.boundary].join(" "));
    case "myth": return words(b.claim + " " + b.reality);
    case "reflect": return words(b.prompt);
    case "check": return 0;
  }
}

function blockExtra(b: LessonBlock): number {
  switch (b.kind) {
    case "check": return 1.5;
    case "reflect": return 2;
    case "caseStudy": return 4;
    case "workedExample": return 2;
    default: return 0;
  }
}

export function lessonMinutes(l: Lesson): number {
  const w = l.blocks.reduce((a, b) => a + blockWords(b), 0) + words(l.summary.join(" "));
  return Math.round(w / WPM + l.blocks.reduce((a, b) => a + blockExtra(b), 0));
}

export function moduleMinutes(m: ModuleContent, simulationCount: number) {
  const lessons = m.lessons.reduce((a, l) => a + lessonMinutes(l), 0);
  const exam = Math.round(m.examQuestionIds.length * 1.2);
  const sims = simulationCount * 12;
  const transfer = m.transferTask ? 20 : 0;
  return { lessons, exam, sims, transfer, total: lessons + exam + sims + transfer };
}
