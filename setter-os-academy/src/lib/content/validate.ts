// Content validator – used by tests (CI gate) and the admin view.
// Every rule here protects a promise from the product brief (unique IDs, sources, explanations, plausible distractors …).
import type { KnowledgeEntry, KnowledgeSource, ModuleContent, Question, Scenario } from "../types";

export interface Issue {
  severity: "error" | "warning";
  ref: string;
  message: string;
}

const DAY = 86_400_000;

export function validateContent(input: {
  sources: KnowledgeSource[];
  knowledge: KnowledgeEntry[];
  modules: ModuleContent[];
  questions: Question[];
  scenarios: Scenario[];
  now?: number;
}): Issue[] {
  const issues: Issue[] = [];
  const err = (ref: string, message: string) => issues.push({ severity: "error", ref, message });
  const warn = (ref: string, message: string) => issues.push({ severity: "warning", ref, message });
  const now = input.now ?? Date.now();
  const srcIds = new Set(input.sources.map((s) => s.id));
  const qIds = new Set<string>();
  const lessonIds = new Set(input.modules.flatMap((m) => m.lessons.map((l) => l.id)));
  const objIds = new Set(input.modules.flatMap((m) => m.objectives.map((o) => o.id)));

  const dup = (ids: string[], kind: string) => {
    const seen = new Set<string>();
    for (const id of ids) {
      if (seen.has(id)) err(id, `Doppelte ${kind}-ID`);
      seen.add(id);
    }
  };
  dup(input.sources.map((s) => s.id), "Quellen");
  dup(input.knowledge.map((k) => k.id), "Wissens");
  dup(input.questions.map((q) => q.id), "Fragen");
  dup(input.scenarios.map((s) => s.id), "Szenario");

  for (const s of input.sources) {
    if (!/^https?:\/\//.test(s.url)) err(s.id, "Quelle ohne gültige URL");
    const age = (now - Date.parse(s.lastCheckedAt)) / DAY;
    if (age > s.reviewIntervalDays) warn(s.id, `Prüfintervall (${s.reviewIntervalDays} Tage) überschritten – Quelle als veraltet markiert`);
  }

  // Questions
  const promptSeen = new Map<string, string>();
  for (const q of input.questions) {
    qIds.add(q.id);
    if (!objIds.has(q.objectiveId)) err(q.id, `Unbekanntes Lernziel ${q.objectiveId}`);
    if (!q.explanation || q.explanation.length < 20) err(q.id, "Erklärung fehlt oder zu kurz");
    if (!q.sourceIds.length) err(q.id, "Keine Quelle");
    for (const s of q.sourceIds) if (!srcIds.has(s)) err(q.id, `Unbekannte Quelle ${s}`);
    const key = q.prompt.trim().toLowerCase() + "|" + q.type;
    if (promptSeen.has(key)) err(q.id, `Doppelte Frage (gleich wie ${promptSeen.get(key)})`);
    promptSeen.set(key, q.id);
    if (/\bnicht\b/i.test(q.prompt) && /NICHT/.test(q.prompt) && !q.negation) warn(q.id, "Negationsfrage ohne negation-Flag");
    switch (q.type) {
      case "single": {
        const ids = q.options.map((o) => o.id);
        if (!ids.includes(q.correct)) err(q.id, "Korrekte Option existiert nicht");
        if (q.options.length < 3) err(q.id, "Zu wenige Optionen");
        for (const o of q.options) if (o.id !== q.correct && !o.misconception) err(q.id, `Distraktor ${o.id} ohne geprüften Denkfehler`);
        break;
      }
      case "multi": {
        const ids = q.options.map((o) => o.id);
        if (q.correct.length < 2) err(q.id, "Mehrfachauswahl braucht ≥ 2 richtige Optionen");
        if (q.correct.some((c) => !ids.includes(c))) err(q.id, "Korrekte Option existiert nicht");
        if (q.correct.length === q.options.length) err(q.id, "Alle Optionen richtig – keine Trennschärfe");
        for (const o of q.options) if (!q.correct.includes(o.id) && !o.misconception && !q.negation) err(q.id, `Distraktor ${o.id} ohne Denkfehler`);
        break;
      }
      case "situation":
        if (!q.options.some((o) => o.quality === "best")) err(q.id, "Keine beste Option");
        break;
      case "matching": {
        const right = new Set(q.right.map((r) => r.id));
        for (const l of q.left) if (!right.has(q.pairs[l.id] ?? "")) err(q.id, `Zuordnung für ${l.id} fehlt`);
        break;
      }
      case "ordering": {
        const items = new Set(q.items.map((i) => i.id));
        if (q.correctOrder.length !== items.size || q.correctOrder.some((i) => !items.has(i))) err(q.id, "Reihenfolge inkonsistent");
        if (q.items.every((it, i) => it.id === q.correctOrder[i])) err(q.id, "Items stehen bereits in Lösungsreihenfolge");
        break;
      }
      case "cloze":
        for (const g of q.gaps) if (!q.text.includes(`{{${g.id}}}`)) err(q.id, `Lücke ${g.id} nicht im Text`);
        break;
      case "errorspot":
        if (!q.lines.some((l) => l.faulty)) err(q.id, "Keine fehlerhafte Zeile");
        for (const l of q.lines) if (l.faulty && !l.why) err(q.id, `Fehlerzeile ${l.id} ohne Begründung`);
        break;
      case "calculation":
        if (!q.simulatedData) err(q.id, "Rechenaufgabe nicht als Simulation gekennzeichnet");
        break;
      case "crm":
        for (const f of q.fields) if (!f.options.includes(f.correct)) err(q.id, `CRM-Feld ${f.id}: Lösung nicht in Optionen`);
        break;
      case "freetext":
        if (!q.requiresManualReview) err(q.id, "Freitext muss manuelle Prüfung vorsehen");
        if (!q.rubric.length) err(q.id, "Freitext ohne Rubrik");
        break;
      case "truefalse":
        break;
    }
  }

  // Modules & lessons
  for (const m of input.modules) {
    for (const s of m.sourceIds) if (!srcIds.has(s)) err(m.id, `Unbekannte Quelle ${s}`);
    for (const id of m.examQuestionIds) if (!qIds.has(id)) err(m.id, `Prüfungsfrage ${id} fehlt`);
    for (const l of m.lessons) {
      if (!l.summary.length) err(l.id, "Lektion ohne Zusammenfassung");
      for (const s of l.sourceIds) if (!srcIds.has(s)) err(l.id, `Unbekannte Quelle ${s}`);
      for (const b of l.blocks) if (b.kind === "check" && !qIds.has(b.questionId)) err(l.id, `Check-Frage ${b.questionId} fehlt`);
      for (const o of l.objectiveIds) if (!objIds.has(o)) err(l.id, `Unbekanntes Lernziel ${o}`);
    }
    if (m.status === "verfuegbar") {
      if (!m.lessons.some((l) => l.blocks.some((b) => b.kind === "caseStudy"))) err(m.id, "Keine Fallstudie");
      if (!m.transferTask) err(m.id, "Keine Transferaufgabe");
      for (const o of m.objectives) {
        if (!input.questions.some((q) => q.objectiveId === o.id)) err(o.id, "Lernziel ohne Fragen");
      }
    }
  }

  // Knowledge base
  for (const k of input.knowledge) {
    for (const s of k.sourceIds) if (!srcIds.has(s)) err(k.id, `Unbekannte Quelle ${s}`);
    for (const l of k.lessonIds) if (!lessonIds.has(l)) err(k.id, `Unbekannte Lektion ${l}`);
    for (const q of k.questionIds) if (!qIds.has(q)) err(k.id, `Unbekannte Frage ${q}`);
    const unverified = k.sourceIds.every((s) => input.sources.find((x) => x.id === s)?.verification === "unverifiziert");
    if (unverified && k.lessonIds.length && k.evidence !== "annahme" && k.evidence !== "expertenmeinung")
      warn(k.id, "Nur unverifizierte Quellen, aber in Lektion verwendet");
  }

  // Scenarios
  for (const s of input.scenarios) {
    const moveIds = new Set(s.moves.map((m) => m.id));
    const factKeys = new Set(s.facts.map((f) => f.key));
    if (!s.acceptableOutcomes.includes(s.idealOutcome)) err(s.id, "Ideales Ergebnis nicht unter den zulässigen");
    for (const f of s.handoverFields) if (!factKeys.has(f)) err(s.id, `Übergabefeld ${f} ohne Fakt`);
    for (const q of s.reviewQuestionIds) if (!qIds.has(q)) err(s.id, `Wiederholungsfrage ${q} fehlt`);
    for (const f of s.facts) if (f.distractors.length < 2) err(s.id, `Fakt ${f.key}: zu wenige Distraktoren`);
    for (const m of s.moves) {
      if (!m.reply.length) err(`${s.id}/${m.id}`, "Zug ohne Kundenantwort");
      const last = m.reply[m.reply.length - 1]!;
      if (last.when) err(`${s.id}/${m.id}`, "Letzte Antwortvariante muss bedingungslos sein (Default)");
      for (const r of [...(m.reveals ?? []), ...m.reply.flatMap((x) => x.reveals ?? []), ...(m.requires ?? [])])
        if (!factKeys.has(r)) err(`${s.id}/${m.id}`, `Unbekannter Fakt ${r}`);
      if (m.betterMoveId && !moveIds.has(m.betterMoveId)) err(`${s.id}/${m.id}`, `betterMoveId ${m.betterMoveId} fehlt`);
      if ((m.quality === "bad" || m.quality === "weak") && !m.betterMoveId) warn(`${s.id}/${m.id}`, "Schwacher Zug ohne bessere Alternative");
      if (m.intent === "pressure" && !m.violation) err(`${s.id}/${m.id}`, "Druck-Zug ohne Verstoß-Kennzeichnung");
    }
  }
  return issues;
}
