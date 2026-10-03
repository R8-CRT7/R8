"use client";
import { useMemo, useRef, useState } from "react";
import type { AnswerValue, GradeResult, Question } from "@/lib/types";
import { grade, parseNumber } from "@/lib/engine/quiz";
import type { Confidence } from "@/lib/engine/review";
import { sourceById } from "@/lib/content";
import { Badge, Button, Icon, cx } from "./ui";

const TYPE_LABEL: Record<Question["type"], string> = {
  single: "Single Choice",
  multi: "Mehrfachauswahl",
  truefalse: "Richtig / Falsch",
  matching: "Zuordnung",
  ordering: "Reihenfolge",
  cloze: "Lückentext",
  freetext: "Freitext",
  situation: "Situationsentscheidung",
  errorspot: "Fehlererkennung",
  calculation: "Kennzahlenberechnung",
  crm: "CRM-Aufgabe",
  case: "Gesprächsanalyse / Fallstudie",
};

/** Deterministic shuffle (same order for everyone, every time) – avoids "always b" position bias. */
function seeded<T>(items: T[], seed: string): T[] {
  let h = 2166136261;
  for (const ch of seed) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    h = Math.imul(h ^ (h >>> 13), 2246822507) >>> 0;
    const j = h % (i + 1);
    [a[i], a[j]] = [a[j]!, a[i]!];
  }
  return a;
}

export interface AnsweredMeta {
  durationMs: number;
  confidence?: Confidence;
}

export function QuestionRenderer({
  question: q,
  onAnswered,
  showConfidence = true,
  revealSolution = true,
  index,
  total,
}: {
  question: Question;
  onAnswered?: (r: GradeResult, meta: AnsweredMeta) => void;
  showConfidence?: boolean;
  revealSolution?: boolean;
  index?: number;
  total?: number;
}) {
  const started = useRef(Date.now());
  const [answer, setAnswer] = useState<AnswerValue | null>(initialAnswer(q));
  const [confidence, setConfidence] = useState<Confidence | undefined>();
  const [result, setResult] = useState<GradeResult | null>(null);
  const [inputError, setInputError] = useState<string | null>(null);
  const locked = result !== null;

  function submit() {
    if (!answer) return;
    if (answer.type === "calculation" && !Number.isFinite(answer.value)) return setInputError("Bitte eine Zahl eingeben, z. B. 24 oder 24,5.");
    const r = grade(q, answer);
    setResult(r);
    onAnswered?.(r, { durationMs: Date.now() - started.current, confidence });
  }

  return (
    <article className="fade-in grid gap-4" aria-labelledby={`${q.id}-prompt`}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {index !== undefined && total !== undefined && <Badge>Frage {index + 1} / {total}</Badge>}
        <Badge tone="accent">{TYPE_LABEL[q.type]}</Badge>
        <Badge>Schwierigkeit {"●".repeat(q.difficulty)}{"○".repeat(5 - q.difficulty)}</Badge>
        {q.negation && <Badge tone="warning">Achtung: Negation</Badge>}
      </div>
      <h2 id={`${q.id}-prompt`} className="text-lg font-semibold leading-snug">{q.prompt}</h2>

      <Body q={q} answer={answer} setAnswer={(a) => { setAnswer(a); setInputError(null); }} locked={locked} result={result} />
      {inputError && <p role="alert" className="text-sm text-danger">{inputError}</p>}

      {!locked && (
        <div className="grid gap-3">
          {showConfidence && q.type !== "freetext" && (
            <fieldset>
              <legend className="mb-2 text-sm text-muted">Wie sicher bist du? <span className="text-faint">(trainiert deine Selbsteinschätzung)</span></legend>
              <div className="grid grid-cols-3 gap-2">
                {([1, 2, 3] as Confidence[]).map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-pressed={confidence === c}
                    onClick={() => setConfidence(c)}
                    className={cx("min-h-11 rounded-[var(--radius-sm)] border text-sm transition-colors", confidence === c ? "border-accent bg-accent/15 text-fg" : "border-line text-muted hover:border-line-strong")}
                  >
                    {c === 1 ? "Geraten" : c === 2 ? "Unsicher" : "Sicher"}
                  </button>
                ))}
              </div>
            </fieldset>
          )}
          <Button onClick={submit} disabled={!isComplete(q, answer)} className="min-h-12">
            {q.type === "freetext" ? "Selbstcheck starten" : "Antwort prüfen"}
          </Button>
        </div>
      )}

      {result && <Feedback q={q} r={result} revealSolution={revealSolution} />}
    </article>
  );
}

function initialAnswer(q: Question): AnswerValue | null {
  switch (q.type) {
    case "multi": return { type: "multi", optionIds: [] };
    case "matching": return { type: "matching", pairs: {} };
    case "ordering": return { type: "ordering", order: q.items.map((i) => i.id) };
    case "cloze": return { type: "cloze", gaps: {} };
    case "freetext": return { type: "freetext", text: "" };
    case "errorspot": return { type: "errorspot", lineIds: [] };
    case "crm": return { type: "crm", fields: {} };
    case "case": return { type: "case", answers: {} };
    default: return null;
  }
}

function isComplete(q: Question, a: AnswerValue | null): boolean {
  if (!a) return false;
  switch (a.type) {
    case "multi": return a.optionIds.length > 0;
    case "matching": return q.type === "matching" && q.left.every((l) => a.pairs[l.id]);
    case "cloze": return q.type === "cloze" && q.gaps.every((g) => (a.gaps[g.id] ?? "").trim() !== "");
    case "freetext": return a.text.trim().length >= 15;
    case "errorspot": return a.lineIds.length > 0;
    case "crm": return q.type === "crm" && q.fields.every((f) => a.fields[f.id]);
    case "case": return q.type === "case" && q.parts.every((p) => a.answers[p.id]);
    case "calculation": return !Number.isNaN(a.value);
    default: return true;
  }
}

function OptionRow({ checked, onChange, type, name, children, disabled, state }: {
  checked: boolean; onChange: () => void; type: "radio" | "checkbox"; name: string; children: React.ReactNode; disabled: boolean; state?: "right" | "wrong" | "missed";
}) {
  return (
    <label
      className={cx(
        "flex min-h-12 cursor-pointer items-start gap-3 rounded-[var(--radius-sm)] border p-3 text-sm transition-colors",
        checked ? "border-accent bg-accent/10" : "border-line bg-surface hover:border-line-strong",
        state === "right" && "border-success bg-success/10",
        state === "wrong" && "border-danger bg-danger/10",
        state === "missed" && "border-success/60 border-dashed",
        disabled && "cursor-default",
      )}
    >
      <input type={type} name={name} checked={checked} onChange={onChange} disabled={disabled} className="mt-0.5 h-5 w-5 shrink-0 accent-[var(--accent)]" />
      <span className="flex-1 leading-relaxed">{children}</span>
      {state === "right" && <Icon name="check" className="h-5 w-5 text-success" />}
      {state === "wrong" && <Icon name="x" className="h-5 w-5 text-danger" />}
    </label>
  );
}

function Body({ q, answer, setAnswer, locked, result }: { q: Question; answer: AnswerValue | null; setAnswer: (a: AnswerValue) => void; locked: boolean; result: GradeResult | null }) {
  const options = useMemo(() => ("options" in q ? seeded(q.options, q.id) : []), [q]);
  const show = locked && result;
  switch (q.type) {
    case "single":
    case "situation": {
      const sel = answer && (answer.type === "single" || answer.type === "situation") ? answer.optionId : null;
      const correctId = q.type === "single" ? q.correct : q.options.find((o) => o.quality === "best")!.id;
      return (
        <div className="grid gap-3">
          {q.type === "situation" && <p className="rounded-[var(--radius-sm)] border-l-2 border-accent-2 bg-surface p-3 text-sm italic text-muted">{q.situation}</p>}
          <div role="radiogroup" aria-labelledby={`${q.id}-prompt`} className="grid gap-2">
            {options.map((o) => (
              <OptionRow key={o.id} type="radio" name={q.id} checked={sel === o.id} disabled={locked} onChange={() => setAnswer({ type: q.type, optionId: o.id } as AnswerValue)}
                state={show ? (o.id === correctId ? (sel === o.id ? "right" : "missed") : sel === o.id ? "wrong" : undefined) : undefined}>
                {o.text}
              </OptionRow>
            ))}
          </div>
        </div>
      );
    }
    case "multi": {
      const sel = answer?.type === "multi" ? answer.optionIds : [];
      return (
        <div className="grid gap-2" role="group" aria-labelledby={`${q.id}-prompt`}>
          <p className="text-xs text-faint">Mehrere Antworten möglich.</p>
          {options.map((o) => {
            const on = sel.includes(o.id);
            const isC = q.correct.includes(o.id);
            return (
              <OptionRow key={o.id} type="checkbox" name={q.id} checked={on} disabled={locked}
                onChange={() => setAnswer({ type: "multi", optionIds: on ? sel.filter((x) => x !== o.id) : [...sel, o.id] })}
                state={show ? (isC ? (on ? "right" : "missed") : on ? "wrong" : undefined) : undefined}>
                {o.text}
              </OptionRow>
            );
          })}
        </div>
      );
    }
    case "truefalse": {
      const v = answer?.type === "truefalse" ? answer.value : null;
      return (
        <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-labelledby={`${q.id}-prompt`}>
          {[true, false].map((b) => (
            <OptionRow key={String(b)} type="radio" name={q.id} checked={v === b} disabled={locked} onChange={() => setAnswer({ type: "truefalse", value: b })}
              state={show ? (b === q.correct ? (v === b ? "right" : "missed") : v === b ? "wrong" : undefined) : undefined}>
              {b ? "Richtig" : "Falsch"}
            </OptionRow>
          ))}
        </div>
      );
    }
    case "matching": {
      const pairs = answer?.type === "matching" ? answer.pairs : {};
      const right = seeded(q.right, q.id);
      return (
        <div className="grid gap-3">
          {q.left.map((l) => (
            <div key={l.id} className="grid gap-1.5 sm:grid-cols-[1fr_1.4fr] sm:items-center sm:gap-3">
              <label htmlFor={`${q.id}-${l.id}`} className="text-sm font-medium">{l.text}</label>
              <select
                id={`${q.id}-${l.id}`}
                disabled={locked}
                value={pairs[l.id] ?? ""}
                onChange={(e) => setAnswer({ type: "matching", pairs: { ...pairs, [l.id]: e.target.value } })}
                className={cx("min-h-12 w-full rounded-[var(--radius-sm)] border bg-elev px-3 text-sm",
                  show ? (pairs[l.id] === q.pairs[l.id] ? "border-success" : "border-danger") : "border-line")}
              >
                <option value="">Bitte wählen …</option>
                {right.map((r) => <option key={r.id} value={r.id}>{r.text}</option>)}
              </select>
              {show && pairs[l.id] !== q.pairs[l.id] && (
                <p className="text-xs text-success sm:col-start-2">Richtig: {q.right.find((r) => r.id === q.pairs[l.id])?.text}</p>
              )}
            </div>
          ))}
        </div>
      );
    }
    case "ordering": {
      const order = answer?.type === "ordering" ? answer.order : [];
      const move = (i: number, d: -1 | 1) => {
        const j = i + d;
        if (j < 0 || j >= order.length) return;
        const n = [...order];
        [n[i], n[j]] = [n[j]!, n[i]!];
        setAnswer({ type: "ordering", order: n });
      };
      return (
        <ol className="grid gap-2" aria-label="Reihenfolge – mit den Pfeiltasten-Schaltflächen verschieben">
          {order.map((id, i) => {
            const it = q.items.find((x) => x.id === id)!;
            const ok = show && q.correctOrder[i] === id;
            return (
              <li key={id} className={cx("flex min-h-12 items-center gap-2 rounded-[var(--radius-sm)] border bg-surface p-2 pl-3 text-sm", show ? (ok ? "border-success" : "border-danger") : "border-line")}>
                <span className="w-6 text-faint tabular-nums">{i + 1}.</span>
                <span className="flex-1">{it.text}</span>
                {!locked && (
                  <span className="flex gap-1">
                    <button type="button" className="min-tap grid place-items-center rounded-lg text-muted hover:bg-surface-strong disabled:opacity-30" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`${it.text} nach oben`}>↑</button>
                    <button type="button" className="min-tap grid place-items-center rounded-lg text-muted hover:bg-surface-strong disabled:opacity-30" onClick={() => move(i, 1)} disabled={i === order.length - 1} aria-label={`${it.text} nach unten`}>↓</button>
                  </span>
                )}
              </li>
            );
          })}
          {show && !result!.correct && <p className="text-xs text-success">Richtig: {q.correctOrder.map((id) => q.items.find((x) => x.id === id)!.text).join(" → ")}</p>}
        </ol>
      );
    }
    case "cloze": {
      const gaps = answer?.type === "cloze" ? answer.gaps : {};
      const parts = q.text.split(/(\{\{\w+\}\})/g);
      return (
        <p className="leading-[2.6] text-[15px]">
          {parts.map((p, i) => {
            const m = p.match(/^\{\{(\w+)\}\}$/);
            if (!m) return <span key={i}>{p}</span>;
            const g = q.gaps.find((x) => x.id === m[1])!;
            return (
              <input
                key={i}
                aria-label={`Lücke ${g.id}`}
                disabled={locked}
                value={gaps[g.id] ?? ""}
                onChange={(e) => setAnswer({ type: "cloze", gaps: { ...gaps, [g.id]: e.target.value } })}
                className="mx-1 inline-block min-h-10 w-40 rounded-lg border border-line bg-elev px-2 text-center text-base"
                autoCapitalize="off"
                autoCorrect="off"
              />
            );
          })}
        </p>
      );
    }
    case "errorspot": {
      const sel = answer?.type === "errorspot" ? answer.lineIds : [];
      return (
        <div className="grid gap-2" role="group" aria-label="Problematische Zeilen markieren">
          <p className="text-xs text-faint">Tippe alle Zeilen an, die problematisch sind.</p>
          {q.lines.map((l) => {
            const on = sel.includes(l.id);
            return (
              <div key={l.id}>
                <OptionRow type="checkbox" name={q.id} checked={on} disabled={locked}
                  onChange={() => setAnswer({ type: "errorspot", lineIds: on ? sel.filter((x) => x !== l.id) : [...sel, l.id] })}
                  state={show ? (l.faulty ? (on ? "right" : "missed") : on ? "wrong" : undefined) : undefined}>
                  „{l.text}“
                </OptionRow>
                {show && l.faulty && <p className="ml-11 mt-1 text-xs text-muted">{l.why}</p>}
              </div>
            );
          })}
        </div>
      );
    }
    case "calculation": {
      return (
        <div className="grid gap-3">
          <p className="text-xs font-medium text-warning">Simulierte Beispieldaten</p>
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {q.given.map((g) => (
              <div key={g.label} className="rounded-[var(--radius-sm)] border border-line bg-surface p-3">
                <dt className="text-xs text-faint">{g.label}</dt>
                <dd className="text-lg font-semibold tabular-nums">{g.value.toLocaleString("de-DE")} {g.unit ?? ""}</dd>
              </div>
            ))}
          </dl>
          <label className="grid gap-1.5 text-sm">
            Ergebnis ({q.unit})
            <input
              inputMode="decimal"
              disabled={locked}
              onChange={(e) => {
                const n = parseNumber(e.target.value);
                setAnswer({ type: "calculation", value: n ?? Number.NaN });
              }}
              className="min-h-12 w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-elev px-3 text-base tabular-nums"
              placeholder="z. B. 24,5"
            />
          </label>
        </div>
      );
    }
    case "crm": {
      const fields = answer?.type === "crm" ? answer.fields : {};
      return (
        <div className="grid gap-4">
          <div className="rounded-[var(--radius)] border border-line bg-surface">
            <div className="flex items-center justify-between border-b border-line px-4 py-2 text-xs text-faint">
              <span>Übungs-CRM · Kontaktdatensatz</span>
              <span className="text-warning">Simulation – erfundene Daten</span>
            </div>
            <dl className="grid gap-2 p-4 text-sm">
              {q.record.map((r) => (
                <div key={r.label} className="grid gap-0.5 sm:grid-cols-[140px_1fr]">
                  <dt className="text-faint">{r.label}</dt>
                  <dd>{r.value}</dd>
                </div>
              ))}
            </dl>
          </div>
          {q.fields.map((f) => (
            <label key={f.id} className="grid gap-1.5 text-sm">
              {f.label}
              <select
                disabled={locked}
                value={fields[f.id] ?? ""}
                onChange={(e) => setAnswer({ type: "crm", fields: { ...fields, [f.id]: e.target.value } })}
                className={cx("min-h-12 rounded-[var(--radius-sm)] border bg-elev px-3", show ? (fields[f.id] === f.correct ? "border-success" : "border-danger") : "border-line")}
              >
                <option value="">Bitte wählen …</option>
                {f.options.map((o) => <option key={o}>{o}</option>)}
              </select>
            </label>
          ))}
        </div>
      );
    }
    case "case": {
      const ans = answer?.type === "case" ? answer.answers : {};
      return (
        <div className="grid gap-4">
          <div className="rounded-[var(--radius)] border border-line bg-surface">
            <div className="flex items-center justify-between border-b border-line px-4 py-2 text-xs text-faint">
              <span>{q.caseKind === "gespraechsanalyse" ? "Gesprächsanalyse · Transkript" : "Fallstudie"}</span>
              <span className="text-warning">Simulation – erfundene Daten</span>
            </div>
            {q.material.kind === "transcript" ? (
              <ol className="grid gap-2 p-4 text-sm">
                {q.material.lines.map((l, i) => (
                  <li key={i} className="grid gap-0.5 sm:grid-cols-[90px_1fr]">
                    <span className={cx("text-xs font-semibold uppercase tracking-wider", l.speaker === "setter" ? "text-accent" : "text-faint")}>{i + 1} · {l.speaker === "setter" ? "Setter" : "Kunde"}</span>
                    <span className="leading-relaxed">{l.text}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="whitespace-pre-line p-4 text-sm leading-relaxed">{q.material.body}</p>
            )}
          </div>
          {q.parts.map((p, pi) => (
            <fieldset key={p.id} className="grid gap-2">
              <legend className="mb-1 text-sm font-medium">Teil {pi + 1}: {p.prompt}</legend>
              {p.options.map((o) => (
                <OptionRow key={o.id} type="radio" name={`${q.id}-${p.id}`} checked={ans[p.id] === o.id} disabled={locked} onChange={() => setAnswer({ type: "case", answers: { ...ans, [p.id]: o.id } })}
                  state={show ? (o.id === p.correct ? (ans[p.id] === o.id ? "right" : "missed") : ans[p.id] === o.id ? "wrong" : undefined) : undefined}>
                  {o.text}
                </OptionRow>
              ))}
            </fieldset>
          ))}
        </div>
      );
    }
    case "freetext": {
      const text = answer?.type === "freetext" ? answer.text : "";
      return (
        <div className="grid gap-2">
          <textarea
            aria-label="Deine Antwort"
            disabled={locked}
            value={text}
            onChange={(e) => setAnswer({ type: "freetext", text: e.target.value.slice(0, 1500) })}
            rows={5}
            className="w-full rounded-[var(--radius-sm)] border border-line bg-elev p-3 text-base leading-relaxed"
            placeholder="Schreibe deine Nachricht … (nur erfundene Daten)"
          />
          <p className="text-xs text-faint">{text.length}/1500 · mind. 15 Zeichen · Freitext wird nur vorläufig per Kriterien-Check bewertet.</p>
        </div>
      );
    }
  }
}

function Feedback({ q, r, revealSolution }: { q: Question; r: GradeResult; revealSolution: boolean }) {
  const pct = Math.round(r.score * 100);
  const tone = r.needsManualReview ? "border-accent/50" : r.correct ? "border-success/50" : r.score > 0 ? "border-warning/50" : "border-danger/50";
  return (
    <section aria-live="polite" className={cx("fade-in rounded-[var(--radius)] border bg-surface p-4", tone)}>
      <div className="flex flex-wrap items-center gap-2">
        {r.needsManualReview ? (
          <Badge tone="accent">Selbstcheck · {pct} % der Kriterien erkannt · manuelle Prüfung vorgesehen</Badge>
        ) : r.correct ? (
          <Badge tone="success">Richtig</Badge>
        ) : r.score > 0 ? (
          <Badge tone="warning">Teilweise richtig · {pct} %</Badge>
        ) : (
          <Badge tone="danger">Noch nicht richtig</Badge>
        )}
        {r.errorCategories.length > 0 && !r.correct && r.errorCategories.map((c) => <Badge key={c}>{c}</Badge>)}
      </div>
      <ul className="mt-3 grid gap-1 text-sm text-muted">
        {r.feedback.map((f, i) => <li key={i}>{f}</li>)}
      </ul>
      {revealSolution && (
        <>
          <p className="mt-3 text-sm leading-relaxed">{q.explanation}</p>
          {q.type === "freetext" && (
            <div className="mt-3 rounded-[var(--radius-sm)] border border-line p-3 text-sm">
              <p className="mb-1 text-xs font-semibold text-faint">Beispielantwort</p>
              <p>{q.sampleAnswer}</p>
            </div>
          )}
          <p className="mt-3 text-xs text-faint">
            Quellen:{" "}
            {q.sourceIds.map((id, i) => {
              const s = sourceById(id);
              return <span key={id}>{i > 0 && " · "}{s ? s.title : id}</span>;
            })}
          </p>
        </>
      )}
    </section>
  );
}
