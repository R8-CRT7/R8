// Quiz engine: deterministic grading for every question type.
// Same question + same answer => always the same result (no randomness, no AI call).

import type {
  AnswerValue,
  ErrorCategory,
  FreeTextQ,
  GradeResult,
  Question,
} from "../types";

/** Normalises user text for comparisons: lower-case, trimmed, collapsed whitespace, unified umlauts. */
export function normalizeText(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFKC")
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .replace(/[„“"'.,;:!?()]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Parses "12,5", "12.5", "12,5 %" or "1.250" (German thousands) into a number. */
export function parseNumber(input: string): number | null {
  let s = input.replace(/[%€\s]/g, "").trim();
  if (s === "") return null;
  // "1.250,5" -> German formatting
  if (/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(s)) s = s.replace(/\./g, "").replace(",", ".");
  else s = s.replace(",", ".");
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function result(
  q: Question,
  score: number,
  feedback: string[],
  errorCategories: ErrorCategory[] = [],
  needsManualReview = false,
): GradeResult {
  const s = Math.max(0, Math.min(1, Math.round(score * 1000) / 1000));
  return {
    questionId: q.id,
    score: s,
    correct: s >= 0.999,
    needsManualReview,
    errorCategories: [...new Set(errorCategories)],
    feedback,
  };
}

function typeMismatch(q: Question): GradeResult {
  return result(q, 0, ["Antwortformat passt nicht zum Fragetyp."], ["unvollstaendig"]);
}

export function grade(q: Question, a: AnswerValue): GradeResult {
  switch (q.type) {
    case "single": {
      if (a.type !== "single") return typeMismatch(q);
      if (a.optionId === q.correct) return result(q, 1, ["Richtig."]);
      const opt = q.options.find((o) => o.id === a.optionId);
      return result(
        q,
        0,
        [opt?.misconception ? `Denkfehler: ${opt.misconception}` : "Leider falsch."],
        opt?.errorCategory ? [opt.errorCategory] : [],
      );
    }
    case "situation": {
      if (a.type !== "situation") return typeMismatch(q);
      const opt = q.options.find((o) => o.id === a.optionId);
      if (!opt) return result(q, 0, ["Keine gültige Option gewählt."], ["unvollstaendig"]);
      const scoreMap = { best: 1, acceptable: 0.5, poor: 0, unacceptable: 0 } as const;
      const cats: ErrorCategory[] =
        opt.quality === "unacceptable" ? [opt.errorCategory ?? "ethikfehler"] : opt.errorCategory ? [opt.errorCategory] : [];
      return result(q, scoreMap[opt.quality], [opt.feedback], opt.quality === "best" ? [] : cats);
    }
    case "multi": {
      if (a.type !== "multi") return typeMismatch(q);
      // Partial credit: (correct picks - wrong picks) / number of correct; never below 0.
      // Full credit only for the exact set – avoids rewarding "select everything".
      const chosen = new Set(a.optionIds);
      const correct = new Set(q.correct);
      let hits = 0;
      let wrong = 0;
      const cats: ErrorCategory[] = [];
      const fb: string[] = [];
      for (const id of chosen) {
        if (correct.has(id)) hits++;
        else {
          wrong++;
          const o = q.options.find((x) => x.id === id);
          if (o?.errorCategory) cats.push(o.errorCategory);
          if (o?.misconception) fb.push(`Falsch gewählt: ${o.misconception}`);
        }
      }
      const missed = q.correct.length - hits;
      if (missed > 0) {
        fb.push(`${missed} richtige Option(en) fehlen.`);
        cats.push("unvollstaendig");
      }
      const score = Math.max(0, (hits - wrong) / q.correct.length);
      const exact = wrong === 0 && missed === 0;
      return result(q, exact ? 1 : Math.min(score, 0.99), exact ? ["Richtig – alle zutreffenden Optionen gewählt."] : fb, cats);
    }
    case "truefalse": {
      if (a.type !== "truefalse") return typeMismatch(q);
      return a.value === q.correct
        ? result(q, 1, ["Richtig."])
        : result(q, 0, ["Leider falsch."], q.errorCategory ? [q.errorCategory] : []);
    }
    case "matching": {
      if (a.type !== "matching") return typeMismatch(q);
      const keys = Object.keys(q.pairs);
      const ok = keys.filter((k) => a.pairs[k] === q.pairs[k]).length;
      return result(
        q,
        ok / keys.length,
        ok === keys.length ? ["Alle Zuordnungen richtig."] : [`${ok} von ${keys.length} Zuordnungen richtig.`],
        ok === keys.length ? [] : ["begriffsfehler"],
      );
    }
    case "ordering": {
      if (a.type !== "ordering") return typeMismatch(q);
      // Score = share of adjacent pairs in the correct relative order (robust against one misplaced item).
      const pos = new Map(a.order.map((id, i) => [id, i]));
      if (a.order.length !== q.correctOrder.length || q.correctOrder.some((id) => !pos.has(id)))
        return result(q, 0, ["Bitte alle Schritte einordnen."], ["unvollstaendig"]);
      let okPairs = 0;
      for (let i = 0; i < q.correctOrder.length - 1; i++) {
        if (pos.get(q.correctOrder[i]!)! < pos.get(q.correctOrder[i + 1]!)!) okPairs++;
      }
      const total = q.correctOrder.length - 1;
      const exact = q.correctOrder.every((id, i) => a.order[i] === id);
      return result(
        q,
        exact ? 1 : Math.min(0.99, okPairs / total),
        exact ? ["Reihenfolge korrekt."] : [`${okPairs} von ${total} Übergängen stimmen.`],
        exact ? [] : ["prozessfehler"],
      );
    }
    case "cloze": {
      if (a.type !== "cloze") return typeMismatch(q);
      let ok = 0;
      const fb: string[] = [];
      for (const g of q.gaps) {
        const given = normalizeText(a.gaps[g.id] ?? "");
        if (g.accepted.some((acc) => normalizeText(acc) === given)) ok++;
        else fb.push(`Lücke ${g.id}: erwartet z. B. „${g.accepted[0]}“.`);
      }
      return result(q, ok / q.gaps.length, ok === q.gaps.length ? ["Alle Lücken richtig."] : fb, ok === q.gaps.length ? [] : ["begriffsfehler"]);
    }
    case "errorspot": {
      if (a.type !== "errorspot") return typeMismatch(q);
      const marked = new Set(a.lineIds);
      const faulty = q.lines.filter((l) => l.faulty);
      const found = faulty.filter((l) => marked.has(l.id)).length;
      const falseAlarms = q.lines.filter((l) => !l.faulty && marked.has(l.id)).length;
      const score = Math.max(0, (found - falseAlarms) / faulty.length);
      const exact = found === faulty.length && falseAlarms === 0;
      const fb = q.lines.filter((l) => l.faulty && !marked.has(l.id)).map((l) => `Übersehen: „${l.text}“ – ${l.why ?? ""}`.trim());
      if (falseAlarms) fb.push(`${falseAlarms} korrekte Zeile(n) fälschlich markiert.`);
      return result(q, exact ? 1 : Math.min(0.99, score), exact ? ["Alle Fehler gefunden."] : fb, exact ? [] : ["kommunikationsfehler"]);
    }
    case "calculation": {
      if (a.type !== "calculation") return typeMismatch(q);
      const ok = Number.isFinite(a.value) && Math.abs(a.value - q.correctValue) <= q.tolerance + 1e-9;
      return ok
        ? result(q, 1, [`Richtig: ${q.formula}`])
        : result(q, 0, [`Erwartet ${q.correctValue} ${q.unit}. Rechenweg: ${q.formula}`], ["rechenfehler"]);
    }
    case "crm": {
      if (a.type !== "crm") return typeMismatch(q);
      const ok = q.fields.filter((f) => a.fields[f.id] === f.correct).length;
      const fb = q.fields.filter((f) => a.fields[f.id] !== f.correct).map((f) => `${f.label}: richtig wäre „${f.correct}“.`);
      return result(q, ok / q.fields.length, ok === q.fields.length ? ["CRM-Eintrag korrekt."] : fb, ok === q.fields.length ? [] : ["prozessfehler"]);
    }
    case "freetext": {
      if (a.type !== "freetext") return typeMismatch(q);
      return gradeFreeText(q, a.text);
    }
    case "case": {
      if (a.type !== "case") return typeMismatch(q);
      // Equal weight per part; every part gets its own feedback line.
      const cats: ErrorCategory[] = [];
      const fb: string[] = [];
      let ok = 0;
      q.parts.forEach((p, i) => {
        if (a.answers[p.id] === p.correct) {
          ok++;
          fb.push(`Teil ${i + 1}: richtig.`);
        } else {
          const o = p.options.find((x) => x.id === a.answers[p.id]);
          if (o?.errorCategory) cats.push(o.errorCategory);
          else cats.push("ueberinterpretation");
          fb.push(`Teil ${i + 1}: ${o?.misconception ? `Denkfehler: ${o.misconception}. ` : a.answers[p.id] ? "" : "nicht beantwortet. "}${p.explanation}`);
        }
      });
      return result(q, ok / q.parts.length, fb, ok === q.parts.length ? [] : cats);
    }
  }
}

/**
 * Free text: transparent pattern rubric. The score is ALWAYS provisional
 * (needsManualReview = true) – the UI shows it as "Selbstcheck", never as a final verdict.
 */
export function gradeFreeText(q: FreeTextQ, text: string): GradeResult {
  const norm = normalizeText(text);
  const total = q.rubric.reduce((s, c) => s + c.points, 0);
  let got = 0;
  const fb: string[] = [];
  const cats: ErrorCategory[] = [];
  if (norm.length < 15) {
    return result(q, 0, ["Antwort zu kurz für eine Bewertung."], ["unvollstaendig"], true);
  }
  for (const c of q.rubric) {
    const forbiddenHit = c.forbidden?.find((f) => norm.includes(normalizeText(f)));
    const groups = c.anyOf ?? [];
    const allGroupsMatch = groups.every((alts) => alts.some((alt) => norm.includes(normalizeText(alt))));
    if (forbiddenHit) {
      fb.push(`✗ ${c.description} (problematische Formulierung: „${forbiddenHit}“)`);
      cats.push("ethikfehler");
    } else if (allGroupsMatch) {
      got += c.points;
      fb.push(`✓ ${c.description}`);
    } else {
      fb.push(`○ ${c.description}`);
      cats.push("unvollstaendig");
    }
  }
  return result(q, total ? got / total : 0, fb, cats, true);
}

/** Aggregates a quiz attempt. Free-text items are reported separately and do not decide pass/fail on their own. */
export function scoreAttempt(results: GradeResult[], passThreshold: number) {
  const auto = results.filter((r) => !r.needsManualReview);
  const pending = results.filter((r) => r.needsManualReview);
  const sum = auto.reduce((s, r) => s + r.score, 0);
  const pct = auto.length ? sum / auto.length : 0;
  return {
    percent: Math.round(pct * 1000) / 10,
    passed: auto.length > 0 && pct >= passThreshold,
    autoGraded: auto.length,
    pendingManualReview: pending.length,
  };
}
