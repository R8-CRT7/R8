// Content validator – used by tests (CI gate) and the admin view.
// Every rule here protects a promise from the product brief (unique IDs, sources, explanations, plausible distractors …).
import type { Concept, KnowledgeEntry, LongTermPlan, KnowledgeSource, ModuleContent, ProgramStage, Question, Scenario } from "../types";

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
  program?: ProgramStage[];
  concepts?: Concept[];
  longterm?: LongTermPlan;
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
    const body =
      "situation" in q ? q.situation : "text" in q ? q.text : "options" in q ? q.options.map((o) => o.text).join("|") : "lines" in q ? q.lines.map((l) => l.text).join("|") : "items" in q ? q.items.map((i) => i.text).join("|") : "parts" in q ? q.parts.map((p) => p.prompt).join("|") : "";
    const key = [q.prompt.trim().toLowerCase(), q.type, body.trim().toLowerCase()].join("|");
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
      case "case": {
        if (!q.simulatedData) err(q.id, "Fallanalyse nicht als Simulation gekennzeichnet");
        if (q.parts.length < 2) err(q.id, "Fallanalyse braucht ≥ 2 Teilfragen");
        const lines = q.material.kind === "transcript" ? q.material.lines.length : 0;
        if (q.caseKind === "gespraechsanalyse" && lines < 4) err(q.id, "Gesprächsanalyse braucht ein Transkript mit ≥ 4 Zeilen");
        for (const p of q.parts) {
          if (!p.options.some((o) => o.id === p.correct)) err(q.id, `Teil ${p.id}: korrekte Option fehlt`);
          if (p.options.length < 3) err(q.id, `Teil ${p.id}: zu wenige Optionen`);
          for (const o of p.options) if (o.id !== p.correct && !o.misconception) err(q.id, `Teil ${p.id}: Distraktor ${o.id} ohne Denkfehler`);
          if (!p.explanation) err(q.id, `Teil ${p.id}: Erklärung fehlt`);
        }
        break;
      }
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
      for (const b of l.blocks) {
        if (b.kind === "check" && !qIds.has(b.questionId)) err(l.id, `Check-Frage ${b.questionId} fehlt`);
        if ((b.kind === "skill" || b.kind === "myth" || b.kind === "book") && b.sourceIds)
          for (const sid of b.sourceIds) if (!srcIds.has(sid)) err(l.id, `${b.kind}: unbekannte Quelle ${sid}`);
        if (b.kind === "skill" && (!b.boundary || b.how.length < 2)) err(l.id, `Skill-Karte „${b.name}“ ohne Grenze oder Schritte`);
        if (b.kind === "skill" && !b.sourceIds.length) err(l.id, `Skill-Karte „${b.name}“ ohne Quelle`);
      }
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
    if (s.ai) {
      for (const f of s.facts) if (!s.ai.revealRules[f.key]) err(s.id, `KI-Profil: keine Offenlegungsregel für ${f.key}`);
      for (const l of s.ai.lessonLinks) if (!lessonIds.has(l)) err(s.id, `KI-Profil: Lektion ${l} fehlt`);
      if (!s.ai.personality || !s.ai.outcomeGuidance) err(s.id, "KI-Profil unvollständig");
    }
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
  // Program
  for (const st of input.program ?? []) {
    if (st.dayTo < st.dayFrom) err(st.id, "Tagesbereich ungültig");
    if (!st.available) continue;
    const days = st.days.map((d) => d.day);
    for (let d = st.dayFrom; d <= st.dayTo; d++) if (!days.includes(d)) err(st.id, `Tag ${d} fehlt`);
    const scenIds = new Set(input.scenarios.map((x) => x.id));
    const modIds = new Set(input.modules.map((m) => m.id));
    for (const d of st.days)
      for (const it of d.items) {
        if (it.type === "lesson" && !lessonIds.has(it.ref)) err(`${st.id}/Tag ${d.day}`, `Lektion ${it.ref} fehlt`);
        if (it.type === "simulation" && !scenIds.has(it.ref)) err(`${st.id}/Tag ${d.day}`, `Szenario ${it.ref} fehlt`);
        if (it.type === "quiz" && !modIds.has(it.ref) && it.ref !== st.id) err(`${st.id}/Tag ${d.day}`, `Quiz ${it.ref} fehlt`);
        if (it.type === "transfer" && !modIds.has(it.ref)) err(`${st.id}/Tag ${d.day}`, `Transfer ${it.ref} fehlt`);
      }
    for (const q of st.check.questionIds) if (!qIds.has(q)) err(st.id, `Check-Frage ${q} fehlt`);
    for (const x of st.check.requiredSimulations) if (!scenIds.has(x)) err(st.id, `Pflichtsimulation ${x} fehlt`);
    if (st.check.questionIds.length < 15) err(st.id, "Stufen-Check braucht ≥ 15 Fragen");
    const lessonsInPlan = new Set(st.days.flatMap((d) => d.items.filter((i) => i.type === "lesson").map((i) => i.ref)));
    for (const mid of st.moduleIds) {
      const m = input.modules.find((x) => x.id === mid);
      for (const l of m?.lessons ?? []) if (!lessonsInPlan.has(l.id)) err(st.id, `Lektion ${l.id} ist keinem Tag zugeordnet`);
    }
  }
  // Concept graph: references resolve, no cycles; tracks only build on known concepts.
  const cIds = new Set((input.concepts ?? []).map((c) => c.id));
  dup((input.concepts ?? []).map((c) => c.id), "Konzept");
  const modIdsAll = new Set(input.modules.map((m) => m.id));
  for (const c of input.concepts ?? []) {
    for (const p of c.prerequisites) if (!cIds.has(p)) err(c.id, `Voraussetzung ${p} fehlt`);
    for (const o of c.objectiveIds) if (!objIds.has(o)) err(c.id, `Lernziel ${o} fehlt`);
    if (modIdsAll.has(c.moduleId) && !c.objectiveIds.length) warn(c.id, "Modul vorhanden, aber Konzept ohne Lernziel");
  }
  const byId = new Map((input.concepts ?? []).map((c) => [c.id, c]));
  const state = new Map<string, 1 | 2>();
  const visit = (id: string): boolean => {
    if (state.get(id) === 2) return true;
    if (state.get(id) === 1) return false;
    state.set(id, 1);
    for (const p of byId.get(id)?.prerequisites ?? []) if (!visit(p)) return false;
    state.set(id, 2);
    return true;
  };
  for (const c of input.concepts ?? []) if (!visit(c.id)) { err(c.id, "Zyklus im Konzeptgraphen"); break; }
  if (input.longterm) {
    dup(input.longterm.tracks.map((t) => t.id), "Spezialisierungs");
    for (const t of input.longterm.tracks) for (const r of t.requiredConcepts) if (!cIds.has(r)) err(t.id, `Konzept ${r} fehlt`);
    const last = Math.max(...(input.program ?? []).map((p) => p.dayTo), 0);
    let expect = last + 1;
    for (const st of [...input.longterm.stages].sort((a, b) => a.dayFrom - b.dayFrom)) {
      if (st.dayFrom !== expect) err(st.id, `Lücke im Langzeitplan: erwartet Tag ${expect}`);
      expect = st.dayTo + 1;
    }
  }
  return issues;
}
