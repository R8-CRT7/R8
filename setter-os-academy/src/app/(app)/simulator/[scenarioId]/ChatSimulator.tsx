"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, ButtonLink, Card, Icon, Ring, cx } from "@/components/ui";
import { questionById, scenarioById } from "@/lib/content";
import { UNKNOWN_VALUE } from "@/lib/engine/coach";
import { applyMove, availableMoves, startSimulation } from "@/lib/engine/customer";
import { recordSimulation } from "@/lib/store/state";
import { getState, update } from "@/lib/store/storage";
import type { HandoverNote, Scenario, SimulationEvaluation, SimulationState } from "@/lib/types";

type Phase = "briefing" | "chat" | "handover" | "result";

/** Deterministic per-turn ordering so the best option is not always first. */
function orderMoves<T extends { id: string }>(moves: T[], seed: string): T[] {
  const h = (s: string) => [...s].reduce((a, c) => Math.imul(a ^ c.charCodeAt(0), 16777619) >>> 0, 2166136261);
  return [...moves].sort((a, b) => h(seed + a.id) - h(seed + b.id));
}

export default function ChatSimulator({ scenarioId }: { scenarioId: string }) {
  const sc = scenarioById(scenarioId)!;
  const [phase, setPhase] = useState<Phase>("briefing");
  const [st, setSt] = useState<SimulationState>(() => startSimulation(sc));
  const [typing, setTyping] = useState(false);
  const [evaluation, setEvaluation] = useState<SimulationEvaluation | null>(null);
  const listRef = useRef<HTMLOListElement>(null);

  // Scroll only the message list (never the page) – keeps header and answer options in place on iPhone.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [st.transcript.length, typing, phase]);

  const moves = useMemo(() => orderMoves(availableMoves(sc, st), `${sc.id}-${st.turn}`), [sc, st]);

  function choose(id: string) {
    const next = applyMove(sc, st, id);
    // Show the setter message immediately, the customer reply after a short "typing" pause.
    const withoutReply = { ...next, transcript: next.transcript.slice(0, st.transcript.length + 1) };
    setSt(withoutReply);
    const reduce = document.documentElement.dataset.motion === "reduce" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setTyping(true);
    window.setTimeout(() => {
      setTyping(false);
      setSt(next);
      if (next.finished) window.setTimeout(() => setPhase("handover"), reduce ? 0 : 600);
    }, reduce ? 0 : 700);
  }

  function restart() {
    setSt(startSimulation(sc));
    setEvaluation(null);
    setPhase("briefing");
  }

  if (phase === "briefing") return <Briefing sc={sc} onStart={() => setPhase("chat")} />;
  if (phase === "result" && evaluation) return <Result sc={sc} st={st} ev={evaluation} onRestart={restart} />;

  return (
    <div className="fade-in mx-auto grid max-w-5xl gap-4 lg:grid-cols-[1fr_280px]">
      <section className="glass flex h-[calc(100dvh-12.5rem)] min-h-[440px] flex-col overflow-hidden rounded-[var(--radius-lg)] lg:h-[calc(100dvh-8rem)]" aria-label="Gespräch">
        <header className="flex items-center gap-3 border-b border-line px-4 py-3">
          <Link href="/simulator/" className="min-tap -ml-2 grid place-items-center rounded-full text-muted hover:text-fg" aria-label="Zurück zur Übersicht">
            <Icon name="back" />
          </Link>
          <Avatar sc={sc} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{sc.persona.name}</p>
            <p className="truncate text-xs text-faint">Simulierte Person · regelbasiert, keine echte Person, keine KI</p>
          </div>
          <Badge>{st.turn}/{sc.maxTurns}</Badge>
        </header>

        <ol ref={listRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-4 py-4" aria-live="polite" aria-label="Nachrichtenverlauf">
          {st.transcript.map((t, i) => (
            <li key={i} className={cx("fade-in flex", t.role === "setter" ? "justify-end" : t.role === "system" ? "justify-center" : "justify-start")}>
              {t.role === "system" ? (
                <span className="rounded-full border border-line px-3 py-1 text-xs text-faint">{t.text}</span>
              ) : (
                <div
                  className={cx(
                    "max-w-[85%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed sm:max-w-[75%]",
                    t.role === "setter" ? "rounded-br-md bg-[linear-gradient(135deg,var(--accent),var(--accent-2))] text-accent-ink" : "rounded-bl-md border border-line bg-elev",
                  )}
                >
                  <span className="sr-only">{t.role === "setter" ? "Du: " : `${sc.persona.name}: `}</span>
                  {t.text}
                </div>
              )}
            </li>
          ))}
          {typing && (
            <li className="flex justify-start" aria-label={`${sc.persona.name} schreibt`}>
              <div className="typing rounded-2xl rounded-bl-md border border-line bg-elev px-4 py-3 text-muted">
                <span>●</span> <span>●</span> <span>●</span>
              </div>
            </li>
          )}
        </ol>

        {phase === "chat" && !st.finished && (
          <div className="border-t border-line bg-[color-mix(in_srgb,var(--bg)_60%,transparent)] p-3">
            <p className="mb-2 px-1 text-xs text-faint">Wähle deine nächste Nachricht:</p>
            <div className="grid max-h-[34dvh] gap-2 overflow-y-auto overscroll-contain pr-1">
              {moves.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  disabled={typing}
                  onClick={() => choose(m.id)}
                  className="flex min-h-12 items-start gap-3 rounded-[var(--radius-sm)] border border-line bg-surface p-3 text-left text-sm transition-colors hover:border-accent/60 hover:bg-accent/5 disabled:opacity-50"
                >
                  <Icon name="send" className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                  <span>{m.text}</span>
                </button>
              ))}
            </div>
          </div>
        )}
        {phase === "handover" && <div className="max-h-[60%] shrink-0 overflow-y-auto"><Handover sc={sc} st={st} onSubmit={(note) => {
          const { state, evaluation: ev } = recordSimulation(getState(), sc, st.usedMoves, note, Date.now());
          update(() => state);
          setEvaluation(ev);
          setPhase("result");
          window.scrollTo({ top: 0 });
        }} /></div>}
      </section>

      <aside className="grid content-start gap-4">
        <Card>
          <h2 className="text-sm font-semibold">Deine Notizen</h2>
          <p className="mb-2 text-xs text-faint">Was du bisher erfahren hast:</p>
          {st.revealed.length === 0 ? (
            <p className="text-sm text-muted">Noch nichts – stelle passende Fragen.</p>
          ) : (
            <ul className="grid gap-2 text-sm">
              {st.revealed.map((k) => {
                const f = sc.facts.find((x) => x.key === k)!;
                return <li key={k}><span className="text-faint">{f.label}:</span> {f.value}</li>;
              })}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="text-sm font-semibold">Auftrag</h2>
          <p className="mt-1 text-xs leading-relaxed text-muted">{sc.briefing}</p>
        </Card>
      </aside>
    </div>
  );
}

function Avatar({ sc, size = 40 }: { sc: Scenario; size?: number }) {
  return (
    <span aria-hidden className="grid shrink-0 place-items-center rounded-full text-sm font-semibold" style={{ width: size, height: size, background: `hsl(${sc.persona.avatarHue} 60% 50% / 0.18)`, color: `hsl(${sc.persona.avatarHue} 80% 72%)` }}>
      {sc.persona.name.split(" ").map((p) => p[0]).join("")}
    </span>
  );
}

function Briefing({ sc, onStart }: { sc: Scenario; onStart: () => void }) {
  return (
    <div className="fade-in mx-auto max-w-2xl">
      <Link href="/simulator/" className="mb-4 inline-flex min-h-10 items-center gap-2 text-sm text-faint hover:text-fg"><Icon name="back" className="h-4 w-4" /> Alle Szenarien</Link>
      <Card>
        <div className="flex items-center gap-3">
          <Avatar sc={sc} size={52} />
          <div>
            <h1 className="text-xl font-semibold">{sc.title}</h1>
            <p className="text-sm text-faint">{sc.persona.name} · {sc.persona.role}</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-1.5">
          <Badge>{sc.market}</Badge><Badge>{sc.direction}</Badge><Badge>{sc.industry}</Badge>
        </div>
        <h2 className="mt-5 text-sm font-semibold">Ausgangslage</h2>
        <p className="mt-1 text-sm leading-relaxed text-muted">{sc.briefing}</p>
        <h2 className="mt-5 text-sm font-semibold">So wird bewertet</h2>
        <ul className="mt-1 grid gap-1 text-sm text-muted">
          <li>• 11 gewichtete Kompetenzen – nur die in diesem Szenario prüfbaren zählen.</li>
          <li>• Harte Grenzen: Druck, falsche Versprechen, ignoriertes Nein, unqualifizierte Termine oder erfundene Notizen begrenzen die Punktzahl – egal ob ein Termin zustande kommt.</li>
          <li>• Am Ende schreibst du eine Übergabenotiz. Notiere nur, was du wirklich erfahren hast.</li>
        </ul>
        <p className="mt-4 rounded-[var(--radius-sm)] border border-line p-3 text-xs text-faint">
          Simulation mit erfundenen Personen. Der Gesprächspartner ist regelbasiert (kein KI-Modell). Es werden nur deine gewählten Züge gespeichert, keine Texte.
        </p>
        <Button className="mt-5 min-h-12 w-full" onClick={onStart}>Gespräch beginnen</Button>
      </Card>
    </div>
  );
}

function Handover({ sc, st, onSubmit }: { sc: Scenario; st: SimulationState; onSubmit: (n: HandoverNote) => void }) {
  const [fields, setFields] = useState<Record<string, string>>({});
  const complete = sc.handoverFields.every((k) => fields[k]);
  return (
    <div className="fade-in border-t border-line p-4">
      <h2 className="font-semibold">Übergabenotiz für das CRM</h2>
      <p className="mt-1 text-sm text-muted">Gespräch beendet. Dokumentiere für die Kollegin/den Kollegen. Wenn du etwas nicht erfragt hast, wähle „{UNKNOWN_VALUE}“.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {sc.handoverFields.map((k) => {
          const f = sc.facts.find((x) => x.key === k)!;
          // Stable, non-revealing order of options
          const opts = [f.value, ...f.distractors].sort((a, b) => a.localeCompare(b, "de"));
          return (
            <label key={k} className="grid gap-1.5 text-sm">
              {f.label}
              <select value={fields[k] ?? ""} onChange={(e) => setFields((x) => ({ ...x, [k]: e.target.value }))} className="min-h-12 rounded-[var(--radius-sm)] border border-line bg-elev px-3">
                <option value="">Bitte wählen …</option>
                <option>{UNKNOWN_VALUE}</option>
                {opts.map((o) => <option key={o}>{o}</option>)}
              </select>
            </label>
          );
        })}
      </div>
      <p className="mt-3 text-xs text-faint">Ergebnis des Gesprächs: {st.outcome === "lost" ? "abgebrochen" : st.outcome}</p>
      <Button className="mt-4 min-h-12 w-full" disabled={!complete} onClick={() => onSubmit({ fields })}>Übergabe abschließen & Auswertung ansehen</Button>
    </div>
  );
}

function Result({ sc, st, ev, onRestart }: { sc: Scenario; st: SimulationState; ev: SimulationEvaluation; onRestart: () => void }) {
  const firstReview = ev.reviewQuestionIds.map((id) => questionById(id)).filter(Boolean)[0];
  return (
    <div className="fade-in mx-auto max-w-4xl">
      <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-accent">AI Sales Coach · deterministische Auswertung · Rubrik v{ev.rubricVersion}</p>
      <h1 className="mb-6 font-[family-name:var(--font-display)] text-2xl font-semibold sm:text-3xl">{sc.title}</h1>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="flex flex-col items-center text-center">
          <Ring value={ev.total / 100} size={120} label="Gesamtbewertung"><span className="text-2xl">{ev.total}</span></Ring>
          <Badge tone={ev.passed ? "success" : "warning"} className="mt-3">{ev.passed ? "Bestanden (≥ 70, keine Grenze verletzt)" : "Nicht bestanden"}</Badge>
          {ev.rawTotal !== ev.total && <p className="mt-2 text-xs text-faint">Rohwert {ev.rawTotal} → durch Grenzen begrenzt auf {ev.total}</p>}
          <p className="mt-3 text-sm text-muted">{ev.outcomeAssessment}</p>
        </Card>

        <Card className="lg:col-span-2">
          <h2 className="mb-3 font-semibold">Bewertung nach Kompetenz</h2>
          <ul className="grid gap-2.5">
            {ev.competencies.map((c) => (
              <li key={c.competency} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 text-sm">
                <span className={c.tested ? "" : "text-faint"}>{c.label} <span className="text-xs text-faint">· Gewicht {c.weight}</span></span>
                <span className="tabular-nums">{c.tested ? `${c.score}` : "nicht geprüft"}</span>
                {c.tested && (
                  <div className="col-span-2 h-1.5 overflow-hidden rounded-full bg-surface-strong" aria-hidden>
                    <div className={cx("h-full rounded-full", c.score >= 70 ? "bg-success" : c.score >= 40 ? "bg-warning" : "bg-danger")} style={{ width: `${c.score}%` }} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {ev.gates.some((g) => g.triggered) && (
        <Card className="mt-4 border-danger/40">
          <h2 className="mb-2 font-semibold text-danger">Verletzte Grenzen</h2>
          <ul className="grid gap-1 text-sm">
            {ev.gates.filter((g) => g.triggered).map((g) => <li key={g.id}><strong>{g.label}</strong> – {g.effect}</li>)}
          </ul>
        </Card>
      )}

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="mb-2 font-semibold text-success">Drei Stärken</h2>
          <ol className="grid gap-2 text-sm text-muted">{ev.strengths.map((x, i) => <li key={i}>{i + 1}. {x}</li>)}</ol>
        </Card>
        <Card>
          <h2 className="mb-2 font-semibold text-warning">Drei Verbesserungspunkte</h2>
          <ol className="grid gap-2 text-sm text-muted">{ev.improvements.map((x, i) => <li key={i}>{i + 1}. {x}</li>)}</ol>
        </Card>
      </div>

      {ev.keyMoments.length > 0 && (
        <Card className="mt-4">
          <h2 className="mb-3 font-semibold">Entscheidende Gesprächsstellen</h2>
          <ol className="grid gap-3">
            {ev.keyMoments.map((k, i) => (
              <li key={i} className="grid gap-1 rounded-[var(--radius-sm)] border border-line p-3 text-sm">
                <div className="flex items-center gap-2">
                  <Badge tone={k.quality === "good" ? "success" : k.quality === "weak" ? "warning" : "danger"}>Zug {k.turn} · {k.quality === "good" ? "stark" : k.quality === "weak" ? "schwach" : "kritisch"}</Badge>
                </div>
                <p className="italic">„{k.moveText}“</p>
                <p className="text-muted">{k.note}</p>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {ev.improvedExample && (
        <Card className="mt-4">
          <h2 className="mb-3 font-semibold">Verbesserte Beispielantwort</h2>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-[var(--radius-sm)] border border-danger/40 p-3 text-sm"><p className="mb-1 text-xs text-faint">Du hast geschrieben</p>„{ev.improvedExample.original}“</div>
            <div className="rounded-[var(--radius-sm)] border border-success/40 p-3 text-sm"><p className="mb-1 text-xs text-faint">Besser</p>„{ev.improvedExample.better}“</div>
          </div>
          <p className="mt-2 text-sm text-muted">Warum: {ev.improvedExample.why}</p>
        </Card>
      )}

      <Card className="mt-4">
        <h2 className="mb-2 font-semibold">Passende Wiederholungsübung</h2>
        {firstReview ? <p className="text-sm text-muted">„{firstReview.prompt}“ und {ev.reviewQuestionIds.length - 1} weitere Fragen wurden für dich verknüpft.</p> : null}
        <div className="mt-4 flex flex-wrap gap-2">
          <ButtonLink href={`/review/?focus=${ev.reviewQuestionIds.join(",")}`}>Wiederholungsübung starten</ButtonLink>
          <Button variant="secondary" onClick={onRestart}>Szenario erneut spielen</Button>
          <ButtonLink href="/simulator/" variant="ghost">Andere Szenarien</ButtonLink>
        </div>
      </Card>

      <details className="mt-4 rounded-[var(--radius)] border border-line p-4">
        <summary className="cursor-pointer text-sm font-medium">Gesprächsverlauf anzeigen</summary>
        <ol className="mt-3 grid gap-1.5 text-sm">
          {st.transcript.map((t, i) => <li key={i}><span className="text-faint">{t.role === "setter" ? "Du" : t.role === "customer" ? sc.persona.name : "System"}:</span> {t.text}</li>)}
        </ol>
      </details>
    </div>
  );
}
