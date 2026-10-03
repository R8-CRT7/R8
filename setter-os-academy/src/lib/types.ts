// Central domain types for SETTER OS ACADEMY.
// Content files in /content are validated against these shapes (see src/lib/content/validate.ts).

export type Locale = "de" | "en" | "es";
/** A text that is authored in German first; en/es are prepared but optional. */
export type LocalizedText = { de: string; en?: string; es?: string };

export type EvidenceCategory =
  | "gesetz" // statute text
  | "rechtsprechung" // court decision
  | "behoerde" // official authority (e.g. BNetzA, DRV)
  | "peer_review" // peer-reviewed research / meta-analysis
  | "fachliteratur" // books, established practitioner literature
  | "hersteller" // vendor documentation (HubSpot, Salesforce …)
  | "fachpresse" // law firm articles, trade press – secondary
  | "expertenmeinung"
  | "annahme"; // explicit assumption, never presented as fact

export type VerificationStatus = "verifiziert" | "teilweise_verifiziert" | "unverifiziert";

export interface KnowledgeSource {
  id: string; // SRC-xxx
  title: string;
  authorOrPublisher: string;
  url: string;
  doi?: string;
  publishedAt?: string; // ISO date or year
  lastCheckedAt: string; // ISO date
  evidence: EvidenceCategory;
  verification: VerificationStatus;
  /** How the source was accessed, e.g. "Websuche (Snippet)" — documents research limitations honestly. */
  accessNote: string;
  reviewIntervalDays: number; // how often it must be re-checked (law: short)
}

export interface KnowledgeEntry {
  id: string; // KB-xxx
  topic: string;
  subtopic: string;
  statement: string;
  explanation: string;
  sourceIds: string[];
  evidence: EvidenceCategory;
  scope: string; // Geltungsbereich, e.g. "Deutschland, B2C"
  lessonIds: string[];
  questionIds: string[];
  version: number;
  lastCheckedAt: string;
  contradictions?: string; // documented conflicting views
}

export interface LearningObjective {
  id: string; // LO-M01-01
  moduleId: string;
  text: string;
  bloom: "erinnern" | "verstehen" | "anwenden" | "analysieren" | "bewerten" | "erschaffen";
}

export type LessonBlock =
  | { kind: "text"; title?: string; body: string }
  | { kind: "example"; title: string; body: string }
  | { kind: "workedExample"; title: string; steps: string[] }
  | { kind: "caseStudy"; title: string; situation: string; analysis: string; simulationNote?: string }
  | { kind: "callout"; tone: "info" | "warn" | "legal" | "ethics"; title: string; body: string }
  | { kind: "check"; questionId: string } // inline retrieval practice
  | { kind: "reflect"; prompt: string } // metacognition prompt
  /** Kursbuch-Ausschnitt: long-form reading chapter */
  | { kind: "book"; chapter: string; title: string; paragraphs: string[]; sourceIds?: string[] }
  /** Skill-Karte: a concrete technique with evidence and an ethical boundary */
  | {
      kind: "skill";
      name: string;
      category: "psychologie" | "gespraech" | "schreiben" | "prozess";
      what: string;
      how: string[];
      why: string;
      evidence: string;
      example: string;
      boundary: string;
      sourceIds: string[];
    }
  /** Mythos-Check: popular claim vs. evidence */
  | { kind: "myth"; claim: string; reality: string; sourceIds: string[] };

export interface Lesson {
  id: string; // M01-L01
  moduleId: string;
  title: string;
  minutes: number;
  objectiveIds: string[];
  blocks: LessonBlock[];
  summary: string[];
  sourceIds: string[];
}

export interface ModuleContent {
  id: string; // M01
  number: number;
  title: string;
  subtitle: string;
  status: "verfuegbar" | "in_vorbereitung";
  prerequisites: string[];
  objectives: LearningObjective[];
  lessons: Lesson[];
  transferTask?: { title: string; instructions: string; criteria: string[] };
  examQuestionIds: string[];
  passThreshold: number; // 0..1
  sourceIds: string[];
  version: string;
}

// ---------- Questions ----------

export type Difficulty = 1 | 2 | 3 | 4 | 5;

export type ErrorCategory =
  | "rollenverwechslung" // setter vs closer
  | "begriffsfehler"
  | "qualifizierungsfehler"
  | "rechtsfehler"
  | "ethikfehler"
  | "rechenfehler"
  | "kommunikationsfehler"
  | "prozessfehler"
  | "ueberinterpretation"
  | "unvollstaendig";

interface QuestionBase {
  id: string; // Q-M01-001
  moduleId: string;
  objectiveId: string;
  difficulty: Difficulty;
  prompt: string;
  explanation: string;
  sourceIds: string[];
  version: number;
  /** True for prompts asking "Welche Aussage ist NICHT …" — tests flag these explicitly. */
  negation?: boolean;
  tags?: string[];
}

export interface Option {
  id: string;
  text: string;
  /** Which misconception this distractor tests. Required for wrong options. */
  misconception?: string;
  errorCategory?: ErrorCategory;
}

export interface SingleChoiceQ extends QuestionBase {
  type: "single";
  options: Option[];
  correct: string;
}
export interface MultiChoiceQ extends QuestionBase {
  type: "multi";
  options: Option[];
  correct: string[];
}
export interface TrueFalseQ extends QuestionBase {
  type: "truefalse";
  correct: boolean;
  errorCategory?: ErrorCategory;
}
export interface MatchingQ extends QuestionBase {
  type: "matching";
  left: { id: string; text: string }[];
  right: { id: string; text: string }[];
  /** leftId -> rightId */
  pairs: Record<string, string>;
}
export interface OrderingQ extends QuestionBase {
  type: "ordering";
  items: { id: string; text: string }[];
  correctOrder: string[];
}
export interface ClozeQ extends QuestionBase {
  type: "cloze";
  /** Text with {{gapId}} placeholders */
  text: string;
  gaps: { id: string; accepted: string[] }[];
}
export interface FreeTextQ extends QuestionBase {
  type: "freetext";
  /** Transparent rubric; every criterion is checked with deterministic patterns. */
  rubric: FreeTextCriterion[];
  sampleAnswer: string;
  /** Free text never gets a final automated verdict above this confidence – flagged for manual review. */
  requiresManualReview: true;
}
export interface FreeTextCriterion {
  id: string;
  description: string;
  points: number;
  /** Any of these groups must match; each group is a list of alternatives (case-insensitive substrings). */
  anyOf?: string[][];
  /** If any of these appears, criterion fails (e.g. pressure phrases). */
  forbidden?: string[];
}
export interface SituationQ extends QuestionBase {
  type: "situation";
  situation: string;
  options: (Option & { quality: "best" | "acceptable" | "poor" | "unacceptable"; feedback: string })[];
}
export interface ErrorSpotQ extends QuestionBase {
  type: "errorspot";
  /** Lines of a message/transcript; learner marks the faulty ones. */
  lines: { id: string; text: string; faulty: boolean; why?: string }[];
}
export interface CalculationQ extends QuestionBase {
  type: "calculation";
  given: { label: string; value: number; unit?: string }[];
  correctValue: number;
  unit: string;
  /** absolute tolerance */
  tolerance: number;
  formula: string;
  /** Simulated data must be labelled */
  simulatedData: true;
}
export interface CrmTaskQ extends QuestionBase {
  type: "crm";
  record: { label: string; value: string }[];
  /** Field the learner must set, with allowed values */
  fields: { id: string; label: string; options: string[]; correct: string }[];
  simulatedData: true;
}

/** Gesprächsanalyse / Fallstudie: shared material (transcript or case text) + several single-choice parts. */
export interface CaseQ extends QuestionBase {
  type: "case";
  caseKind: "gespraechsanalyse" | "fallstudie";
  material: { kind: "transcript"; lines: { speaker: "setter" | "kunde"; text: string }[] } | { kind: "text"; body: string };
  parts: { id: string; prompt: string; options: Option[]; correct: string; explanation: string }[];
  /** Simulated data must be labelled */
  simulatedData: true;
}

export type Question =
  | CaseQ
  | SingleChoiceQ
  | MultiChoiceQ
  | TrueFalseQ
  | MatchingQ
  | OrderingQ
  | ClozeQ
  | FreeTextQ
  | SituationQ
  | ErrorSpotQ
  | CalculationQ
  | CrmTaskQ;

export type QuestionType = Question["type"];

export type AnswerValue =
  | { type: "single"; optionId: string }
  | { type: "multi"; optionIds: string[] }
  | { type: "truefalse"; value: boolean }
  | { type: "matching"; pairs: Record<string, string> }
  | { type: "ordering"; order: string[] }
  | { type: "cloze"; gaps: Record<string, string> }
  | { type: "freetext"; text: string }
  | { type: "situation"; optionId: string }
  | { type: "errorspot"; lineIds: string[] }
  | { type: "calculation"; value: number }
  | { type: "crm"; fields: Record<string, string> }
  | { type: "case"; answers: Record<string, string> };

export interface GradeResult {
  questionId: string;
  /** 0..1 – partial credit where defined */
  score: number;
  correct: boolean;
  /** Free text: automated score is provisional */
  needsManualReview: boolean;
  errorCategories: ErrorCategory[];
  feedback: string[];
}

// ---------- Simulation ----------

export type Competency =
  | "eroeffnung"
  | "bedarfsermittlung"
  | "fragetechnik"
  | "zuhoeren"
  | "klarheit"
  | "qualifizierung"
  | "einwaende"
  | "kundenorientierung"
  | "terminvereinbarung"
  | "dokumentation"
  | "recht_ethik";

export type ScenarioOutcome = "book" | "nurture" | "disqualify" | "respect_no" | "handoff";

export interface ScenarioFact {
  key: string; // need, budget, timeline, authority, …
  label: string;
  value: string;
  /** required to call the lead qualified */
  requiredForQualification: boolean;
  /** Plausible but wrong values offered in the handover form (documentation check). */
  distractors: string[];
}

export interface ScenarioMove {
  id: string;
  text: string; // what the setter writes
  intent:
    | "open"
    | "ask"
    | "acknowledge"
    | "summarize"
    | "inform"
    | "handle_objection"
    | "propose_booking"
    | "confirm_booking"
    | "handoff"
    | "nurture"
    | "disqualify"
    | "close_respectfully"
    | "pressure";
  quality: "good" | "ok" | "weak" | "bad";
  /** Competency points awarded (can be negative). */
  effects: Partial<Record<Competency, number>>;
  rapport?: number;
  reveals?: string[]; // fact keys
  /** Move only shown when these facts are revealed */
  requires?: string[];
  /** Move only shown when these flags are set */
  requiresFlags?: string[];
  /** Hide move once these flags are set */
  hiddenByFlags?: string[];
  setsFlags?: string[];
  /** Ethics/legal violation – triggers the gate in the evaluation */
  violation?: string;
  ends?: ScenarioOutcome | "lost";
  coachNote: string;
  /** For weak/bad moves: id of a better move in the same scenario */
  betterMoveId?: string;
  /** Customer reply; conditional variants checked top to bottom, `default` last. */
  reply: { when?: ReplyCondition; text: string; setsFlags?: string[]; reveals?: string[]; ends?: ScenarioOutcome | "lost" }[];
}

export interface ReplyCondition {
  minRapport?: number;
  maxRapport?: number;
  factsRevealed?: string[];
  factsMissing?: string[];
  flags?: string[];
  notFlags?: string[];
}

/** Profile for the free-text AI customer. The deterministic move tree stays the offline mode. */
export interface ScenarioAiProfile {
  personality: string;
  speakingStyle: string;
  situation: string;
  concern: string;
  background: string;
  needs: string[];
  objections: { trigger: string; reaction: string }[];
  customerGoals: string[];
  /** factKey -> what kind of setter question makes the customer share it */
  revealRules: Record<string, string>;
  /** questions the customer will ask that a setter must hand off to an expert */
  adviceBoundaries: string[];
  outcomeGuidance: string;
  lessonLinks: string[];
}

export interface Scenario {
  ai?: ScenarioAiProfile;
  id: string; // SIM-001
  title: string;
  archetype: string; // e.g. "Kunde, der ausdrücklich keinen Termin möchte"
  industry: string;
  channel: "chat" | "telefon_simuliert" | "instagram_dm" | "whatsapp" | "email";
  market: "B2B" | "B2C";
  direction: "inbound" | "outbound";
  difficulty: Difficulty;
  briefing: string; // visible to learner
  persona: { name: string; role: string; avatarHue: number };
  /** Hidden from learner until revealed by suitable questions */
  facts: ScenarioFact[];
  idealOutcome: ScenarioOutcome;
  acceptableOutcomes: ScenarioOutcome[];
  openingMessage: string;
  startRapport: number;
  maxTurns: number;
  moves: ScenarioMove[];
  /** Fact keys the learner documents in the handover note – checked against what was actually revealed */
  handoverFields: string[];
  /** Points that count as 100 % per competency in this scenario. Competencies without target are "nicht geprüft". */
  competencyTargets: Partial<Record<Competency, number>>;
  reviewQuestionIds: string[];
  sourceIds: string[];
  version: number;
}

export interface TranscriptEntry {
  turn: number;
  role: "setter" | "customer" | "system";
  text: string;
  moveId?: string;
}

export interface SimulationState {
  scenarioId: string;
  scenarioVersion: number;
  turn: number;
  rapport: number;
  revealed: string[];
  flags: string[];
  usedMoves: string[];
  transcript: TranscriptEntry[];
  outcome: ScenarioOutcome | "lost" | null;
  finished: boolean;
}

export interface HandoverNote {
  /** factKey -> chosen value; UNKNOWN_VALUE = "nicht erfragt" */
  fields: Record<string, string>;
}

export interface CompetencyScore {
  competency: Competency;
  label: string;
  weight: number;
  score: number; // 0..100
  tested: boolean;
}

export interface SimulationEvaluation {
  scenarioId: string;
  scenarioVersion: number;
  rubricVersion: string;
  total: number; // 0..100 after gates
  rawTotal: number; // before gates
  passed: boolean;
  gates: { id: string; label: string; triggered: boolean; effect: string }[];
  competencies: CompetencyScore[];
  strengths: string[];
  improvements: string[];
  keyMoments: { turn: number; moveText: string; note: string; quality: ScenarioMove["quality"] }[];
  improvedExample: { original: string; better: string; why: string } | null;
  reviewQuestionIds: string[];
  outcome: SimulationState["outcome"];
  outcomeAssessment: string;
}

// ---------- 90-Tage-Programm ----------

export type ProgramItem =
  | { type: "lesson"; ref: string }
  | { type: "quiz"; ref: string; fresh?: boolean } // module id or stage-check id; fresh = new attempt on that day
  | { type: "simulation"; ref: string; fresh?: boolean } // fresh = new run on that day
  | { type: "review" }
  | { type: "transfer"; ref: string; optional?: boolean };

export interface ProgramDay {
  day: number; // 1..90
  title: string;
  items: ProgramItem[];
}

export interface ProgramStage {
  id: string; // ST1
  number: number;
  title: string;
  goal: string;
  dayFrom: number;
  dayTo: number;
  moduleIds: string[];
  available: boolean;
  days: ProgramDay[];
  /** Plan for stages whose content is not written yet */
  plannedTopics?: string[];
  check: { id: string; title: string; questionIds: string[]; passThreshold: number; requiredSimulations: string[] };
}

// ---------- Long-term architecture (V3) ----------
export type ConceptArea = "grundlagen" | "gespraech" | "psychologie" | "qualifizierung" | "chat" | "einwaende" | "termin" | "daten" | "recht" | "business";
/** Node of the concept graph. Mastery is derived from the linked learning objectives only. */
export interface Concept {
  id: string;
  label: string;
  area: ConceptArea;
  moduleId: string;
  description: string;
  prerequisites: string[];
  objectiveIds: string[];
}
export interface Track {
  id: string;
  title: string;
  area: string;
  summary: string;
  requiredConcepts: string[];
  focus: string[];
  legalNote: string | null;
  status: "geplant" | "verfuegbar";
}
export interface LongTermStage {
  id: string;
  number: number;
  title: string;
  dayFrom: number;
  dayTo: number;
  goal: string;
  structure: string[];
  unlock: string;
}
export interface LongTermPlan {
  tracks: Track[];
  stages: LongTermStage[];
  open: { title: string; text: string };
}
