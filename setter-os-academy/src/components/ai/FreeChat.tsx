"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Badge, Button, ButtonLink, Card, Icon, cx } from "@/components/ui";
import { lessonById, questionById } from "@/lib/content";
import { COACH_CRITERIA, coachEvaluate, EXAM_RULES, hint, RATING_LABEL, UNKNOWN_VALUE, type FreeEvaluation } from "@/lib/ai/coachAI";
import { customerTurn, MAX_SETTER_CHARS, startFreeSim, type FreeSimState, type TrainingMode } from "@/lib/ai/customerAI";
import { AiError } from "@/lib/ai/types";
import { recordAiSimulation } from "@/lib/store/state";
import { update } from "@/lib/store/storage";
import type { HandoverNote, Scenario } from "@/lib/types";
import { useAiRouter, useVisualViewportHeight } from "./useAi";

const MODE_INFO: Record<TrainingMode, { title: string; text: string }> = {
  lern: { title: "Lernmodus", text: "Freie Eingabe. Du kannst Hinweise und Formulierungsbeispiele anfordern und passende Kursbuch-Kapitel öffnen." },
  praxis: { title: "Praxismodus", text: "Freie Eingabe ohne ungefragte Hilfen. Realistische Reaktionen, vollständige Auswertung am Ende." },
  pruefung: { title: "Prüfungsmodus", text: "Keine Hilfen. Die Bestehensregeln stehen vorher fest; das Ergebnis wird gespeichert." },
};

const ERR_COPY: Record<string, string> = {
  not_granted: "Du hast der Akademie die Nutzung von Claude nicht erlaubt. Der Offline-Modus funktioniert weiterhin.",
  rate_limited: "Gerade zu viele Anfragen oder dein Claude-Nutzungslimit ist erreicht. Versuche es später erneut.",
  invalid_output: "Die Kundenantwort kam in einem unerwarteten Format. Sende deine Nachricht noch einmal.",
  refused: "Diese Nachricht wurde nicht verarbeitet. Formuliere sie anders.",
  upstream_error: "Verbindung unterbrochen. Sende deine Nachricht noch einmal.",
  budget_blocked: "Kostenpflichtige KI ist gesperrt. Nichts wurde berechnet.",
  unavailable: "Keine KI verfügbar. Öffne die Akademie über deinen claude.ai-Link.",
};

export function FreeChat({ sc, onExit }: { sc: Scenario; onExit: () => void }) {
  const ai = useAiRouter();
  const [mode, setMode] = useState<TrainingMode | null>(null);
  const [st, setSt] = useState<FreeSimState | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<null | "customer" | "hint" | "coach">(null);
  const [streamText, setStreamText] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [hintText, setHintText] = useState<string | null>(null);
  const [phase, setPhase] = useState<"chat" | "handover" | "result">("chat");
  const [evaluation, setEvaluation] = useState<(FreeEvaluation & { coachError?: string }) | null>(null);
  const ctl = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLOListElement>(null);
  const vvh = useVisualViewportHeight();

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [st?.transcript.length, busy, hintText]);

  if (!mode || !st) {
    return (
      <div className="fade-in mx-auto max-w-2xl">
        <button onClick={onExit} className="mb-4 inline-flex min-h-10 items-center gap-2 text-sm text-faint hover:text-fg"><Icon name="back" className="h-4 w-4" /> Zurück</button>
        <Card>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">KI-Gespräch · freie Eingabe</p>
          <h1 className="mt-1 text-xl font-semibold">{sc.title}</h1>
          <p className="mt-2 text-sm text-muted">{sc.briefing}</p>
          <AiStatus status={ai.status} label={ai.providerLabel} costKind={ai.costKind} />
          <div className="mt-5 grid gap-2">
            {(Object.keys(MODE_INFO) as TrainingMode[]).map((m) => (
              <button
                key={m}
                disabled={ai.status !== "ready"}
                onClick={() => {
                  setMode(m);
                  setSt(startFreeSim(sc, m));
                }}
                className="min-h-14 rounded-[var(--radius-sm)] border border-line bg-surface p-3 text-left transition-colors hover:border-accent/60 disabled:opacity-50"
              >
                <span className="block font-medium">{MODE_INFO[m].title}</span>
                <span className="block text-sm text-muted">{MODE_INFO[m].text}</span>
              </button>
            ))}
          </div>
          <details className="mt-4 rounded-[var(--radius-sm)] border border-line p-3 text-sm">
            <summary className="cursor-pointer font-medium">Bestehensregeln im Prüfungsmodus</summary>
            <ul className="mt-2 grid gap-1 text-muted">{EXAM_RULES.map((r) => <li key={r}>• {r}</li>)}</ul>
            <p className="mt-2 text-xs text-faint">Gemessene Werte (z. B. Anzahl offener Fragen) werden getrennt von der Einschätzung des Coaches angezeigt. Coach-Aussagen zählen nur mit wörtlichem Beleg aus deinem Gespräch.</p>
          </details>
        </Card>
      </div>
    );
  }

  async function send() {
    if (!st || !draft.trim() || busy) return;
    setError(null);
    setHintText(null);
    const text = draft;
    setDraft("");
    const optimistic: FreeSimState = { ...st, transcript: [...st.transcript, { role: "setter", text: text.trim() }] };
    setSt(optimistic);
    setBusy("customer");
    setStreamText("");
    ctl.current = new AbortController();
    try {
      const { state } = await customerTurn(ai.router, sc, st, text, { signal: ctl.current.signal });
      setSt(state);
      if (state.finished) setPhase("handover");
    } catch (e) {
      const err = e as AiError;
      setSt(st); // roll back – the message was not answered
      setDraft(text);
      if (err.code !== "cancelled") setError(ERR_COPY[err.code] ?? err.message);
    } finally {
      setBusy(null);
    }
  }

  async function askHint(example: boolean) {
    if (!st || busy) return;
    setBusy("hint");
    setError(null);
    try {
      const h = await hint(ai.router, sc, st, example);
      setHintText(h);
      setSt({ ...st, hintsUsed: st.hintsUsed + 1 });
    } catch (e) {
      setError(ERR_COPY[(e as AiError).code] ?? (e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function finish(note: HandoverNote) {
    if (!st) return;
    setBusy("coach");
    const ev = await coachEvaluate(ai.router, sc, st, note);
    update((x) =>
      recordAiSimulation(x, {
        id: `ai-${Date.now().toString(36)}`,
        scenarioId: sc.id,
        scenarioVersion: sc.version,
        mode: st.mode,
        at: Date.now(),
        transcript: st.transcript,
        handover: note,
        revealed: st.revealed,
        outcome: st.outcome,
        evaluation: ev,
        providerId: "claude-artifact",
      }),
    );
    setEvaluation(ev);
    setBusy(null);
    setPhase("result");
    window.scrollTo({ top: 0 });
  }

  if (phase === "result" && evaluation) return <FreeResult sc={sc} st={st} ev={evaluation} onRestart={() => { setMode(null); setSt(null); setPhase("chat"); setEvaluation(null); }} />;

  // Mobile: pinned to the *visual* viewport so the iOS keyboard never covers the input.
  const style = { "--chat-h": vvh ? `${vvh.height}px` : "100dvh", "--chat-top": vvh ? `${vvh.offsetTop}px` : "0px" } as CSSProperties;
  return (
    <div className="fixed inset-x-0 top-[var(--chat-top)] z-40 flex h-[var(--chat-h)] flex-col bg-bg lg:static lg:z-auto lg:mx-auto lg:h-[calc(100dvh-8rem)] lg:max-w-3xl lg:rounded-[var(--radius-lg)] lg:border lg:border-line" style={style} data-testid="free-chat">
      <header className="flex items-center gap-3 border-b border-line px-3 py-2.5" style={{ paddingTop: "max(0.625rem, env(safe-area-inset-top))" }}>
        <button onClick={() => { ctl.current?.abort(); onExit(); }} className="min-tap grid place-items-center rounded-full text-muted hover:text-fg" aria-label="Gespräch verlassen"><Icon name="back" /></button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{sc.persona.name}</p>
          <p className="truncate text-[11px] text-faint">KI-Simulation (Claude) · fiktive Person · {MODE_INFO[st.mode].title}</p>
        </div>
        {phase === "chat" && !st.finished && (
          <Button variant="ghost" className="min-h-9 px-2 text-xs" onClick={() => { setSt({ ...st, finished: true, outcome: st.outcome ?? "lost" }); setPhase("handover"); }}>Beenden</Button>
        )}
      </header>

      <ol ref={listRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-3 py-4" aria-live="polite" aria-label="Nachrichtenverlauf">
        {st.transcript.map((t, i) => (
          <li key={i} className={cx("flex", t.role === "setter" ? "justify-end" : t.role === "system" ? "justify-center" : "justify-start")}>
            {t.role === "system" ? (
              <span className="rounded-full border border-line px-3 py-1 text-xs text-faint">{t.text}</span>
            ) : (
              <div className={cx("max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed", t.role === "setter" ? "rounded-br-md bg-accent-solid text-accent-ink" : "rounded-bl-md border border-line bg-elev")}>
                <span className="sr-only">{t.role === "setter" ? "Du: " : `${sc.persona.name}: `}</span>
                {t.text}
              </div>
            )}
          </li>
        ))}
        {busy === "customer" && (
          <li className="flex justify-start" aria-label={`${sc.persona.name} schreibt`}>
            <div className="typing rounded-2xl rounded-bl-md border border-line bg-elev px-4 py-3 text-muted">{streamText ? "…" : <><span>●</span> <span>●</span> <span>●</span></>}</div>
          </li>
        )}
        {hintText && (
          <li className="mx-auto max-w-[92%] rounded-[var(--radius-sm)] border border-accent-2/40 bg-accent-2/10 p-3 text-sm" role="note">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-accent-2">Hinweis des Coaches</p>
            <p className="whitespace-pre-wrap">{hintText}</p>
          </li>
        )}
      </ol>

      {phase === "handover" ? (
        <div className="max-h-[70%] shrink-0 overflow-y-auto border-t border-line">
          <FreeHandover sc={sc} busy={busy === "coach"} onSubmit={finish} />
        </div>
      ) : (
        <div className="shrink-0 border-t border-line bg-elev/80 px-3 pt-2 backdrop-blur" style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}>
          {error && <p role="alert" className="mb-2 text-sm text-danger">{error}</p>}
          {st.mode === "lern" && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              <Button variant="secondary" className="min-h-9 px-3 text-xs" disabled={!!busy} onClick={() => askHint(false)}>Hinweis</Button>
              <Button variant="secondary" className="min-h-9 px-3 text-xs" disabled={!!busy} onClick={() => askHint(true)}>Formulierungsbeispiel</Button>
              {sc.ai?.lessonLinks.slice(0, 2).map((l) => (
                <Link key={l} href={`/learn/${lessonById(l)?.moduleId}/${l}/`} className="inline-flex min-h-9 items-center rounded-[var(--radius-sm)] px-2 text-xs text-accent hover:underline">Kursbuch: {lessonById(l)?.title}</Link>
              ))}
            </div>
          )}
          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <label htmlFor="setter-input" className="sr-only">Deine Nachricht</label>
            <textarea
              id="setter-input"
              value={draft}
              maxLength={MAX_SETTER_CHARS}
              rows={1}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !("ontouchstart" in window)) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder="Deine Nachricht an den Kunden …"
              className="max-h-32 min-h-11 flex-1 resize-none rounded-[var(--radius-sm)] border border-line bg-bg px-3 py-2.5 text-base leading-snug"
              disabled={busy === "customer"}
            />
            {busy === "customer" ? (
              <Button type="button" variant="secondary" className="min-h-11" onClick={() => ctl.current?.abort()}>Stopp</Button>
            ) : (
              <Button type="submit" className="min-h-11 px-3" disabled={!draft.trim() || !!busy} aria-label="Senden"><Icon name="send" className="h-4 w-4" /></Button>
            )}
          </form>
          <p className="mt-1 text-[11px] text-faint">Nur erfundene Daten verwenden. {draft.length}/{MAX_SETTER_CHARS}</p>
        </div>
      )}
    </div>
  );
}

function AiStatus({ status, label, costKind }: { status: string; label: string | null; costKind: string | null }) {
  if (status === "checking") return <p className="mt-4 text-sm text-faint">Prüfe KI-Verfügbarkeit …</p>;
  if (status === "ready")
    return (
      <div className="mt-4 rounded-[var(--radius-sm)] border border-success/40 bg-success/5 p-3 text-sm">
        <p className="font-medium text-success">KI verfügbar</p>
        <p className="text-muted">{label}. {costKind === "claude-plan" ? "Nutzt dein Claude-Kontingent, keine zusätzliche Rechnung. Beim ersten Mal fragt Claude um Erlaubnis." : costKind === "per-token" ? "Kostenpflichtig über eigenen Proxy (von dir freigegeben)." : ""}</p>
      </div>
    );
  return (
    <div className="mt-4 rounded-[var(--radius-sm)] border border-warning/40 bg-warning/5 p-3 text-sm">
      <p className="font-medium text-warning">{status === "blocked" ? "Kostenpflichtige KI gesperrt" : "KI in dieser Ansicht nicht verfügbar"}</p>
      <p className="text-muted">Die freie KI-Simulation läuft, wenn du die Akademie über deinen claude.ai-Link öffnest. Das Offline-Training mit Antwortauswahl funktioniert immer.</p>
    </div>
  );
}

function FreeHandover({ sc, busy, onSubmit }: { sc: Scenario; busy: boolean; onSubmit: (n: HandoverNote) => void }) {
  const [fields, setFields] = useState<Record<string, string>>({});
  return (
    <div className="p-4">
      <h2 className="font-semibold">Übergabenotiz für das CRM</h2>
      <p className="mt-1 text-sm text-muted">Dokumentiere nur, was der Kunde wirklich gesagt hat. Sonst „{UNKNOWN_VALUE}“.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {sc.handoverFields.map((k) => {
          const f = sc.facts.find((x) => x.key === k)!;
          const opts = [f.value, ...f.distractors].sort((a, b) => a.localeCompare(b, "de"));
          return (
            <label key={k} className="grid gap-1.5 text-sm">
              {f.label}
              <select value={fields[k] ?? ""} onChange={(e) => setFields((x) => ({ ...x, [k]: e.target.value }))} className="min-h-12 rounded-[var(--radius-sm)] border border-line bg-bg px-3">
                <option value="">Bitte wählen …</option>
                <option>{UNKNOWN_VALUE}</option>
                {opts.map((o) => <option key={o}>{o}</option>)}
              </select>
            </label>
          );
        })}
      </div>
      <Button className="mt-4 min-h-12 w-full" disabled={busy || !sc.handoverFields.every((k) => fields[k])} onClick={() => onSubmit({ fields })}>
        {busy ? "Coach wertet aus … (kann bis zu einer Minute dauern)" : "Abschließen und auswerten"}
      </Button>
    </div>
  );
}

const RATING_TONE = { stark: "success", solide: "accent", ausbaufaehig: "warning", kritisch: "danger", nicht_beobachtet: "neutral" } as const;

function FreeResult({ sc, st, ev, onRestart }: { sc: Scenario; st: FreeSimState; ev: FreeEvaluation & { coachError?: string }; onRestart: () => void }) {
  const m = ev.measured;
  return (
    <div className="fade-in mx-auto max-w-4xl">
      <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-accent">Auswertung · {MODE_INFO[st.mode].title}</p>
      <h1 className="mb-4 font-[family-name:var(--font-display)] text-2xl font-semibold">{sc.title}</h1>
      {ev.passed !== null && (
        <Card className={cx("mb-4", ev.passed ? "border-success/50" : "border-danger/40")}>
          <p className={cx("text-lg font-semibold", ev.passed ? "text-success" : "text-danger")}>{ev.passed ? "Prüfung bestanden" : "Prüfung nicht bestanden"}</p>
          <ul className="mt-2 grid gap-1 text-sm">{ev.gates.map((g) => <li key={g.id} className={g.triggered ? "text-danger" : "text-muted"}>{g.triggered ? "✗" : "✓"} {g.label}{g.triggered && g.detail ? ` – ${g.detail}` : ""}</li>)}</ul>
        </Card>
      )}
      {st.mode === "pruefung" && ev.passed === null && <Card className="mb-4 border-warning/40"><p className="text-sm text-warning">Der Coach war nicht erreichbar. Ohne geprüfte Kriterien gibt es keine Prüfungsentscheidung – bitte später erneut versuchen.</p></Card>}

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card>
          <h2 className="mb-1 font-semibold">Gemessen</h2>
          <p className="mb-3 text-xs text-faint">Automatisch gezählt, ohne KI.</p>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            {[
              ["Deine Nachrichten", m.setterMessages],
              ["Fragen gestellt", m.questions],
              ["davon offen", m.openQuestions],
              ["Mehrfachfragen", m.multiQuestionMessages],
              ["Ø Wörter/Nachricht", m.avgWordsPerMessage],
              ["Pflichtkriterien", `${m.requiredFactsCovered}/${m.requiredFactsTotal}`],
              ["Übergabe korrekt", `${m.documentationOk}/${m.documentationTotal}`],
              ["Ergebnis", m.outcome ?? "offen"],
            ].map(([k, v]) => (
              <div key={k as string} className="rounded-[var(--radius-sm)] border border-line p-2"><dt className="text-[11px] text-faint">{k}</dt><dd className="font-semibold tabular-nums">{v}</dd></div>
            ))}
          </dl>
          {m.redFlags.length > 0 && <div className="mt-3 rounded-[var(--radius-sm)] border border-danger/40 p-2 text-xs text-danger">Warnsätze: {m.redFlags.map((r) => `„${r.quote}“ (${r.label})`).join(" · ")}</div>}
        </Card>
        <Card>
          <h2 className="mb-1 font-semibold">Einschätzung des Coaches</h2>
          {!ev.coach ? (
            <p className="text-sm text-muted">Der Coach konnte nicht laufen{ev.coachError ? `: ${ev.coachError}` : ""}. Die gemessenen Werte bleiben gültig.</p>
          ) : (
            <>
              <p className="mb-3 text-xs text-faint">Qualitative Stufen statt Punkte. Jede Aussage ist mit einem wörtlichen Zitat aus deinem Gespräch belegt{ev.coach.droppedUnverified ? `; ${ev.coach.droppedUnverified} unbelegte Aussage(n) wurden verworfen` : ""}.</p>
              <ul className="grid gap-2">
                {ev.coach.criteria.map((c) => (
                  <li key={c.id} className="rounded-[var(--radius-sm)] border border-line p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{COACH_CRITERIA.find((x) => x.id === c.id)?.label}</span>
                      <Badge tone={RATING_TONE[c.rating]}>{RATING_LABEL[c.rating]}</Badge>
                    </div>
                    {c.reasoning && <p className="mt-1 text-muted">{c.reasoning}</p>}
                    {c.evidence.map((e, i) => <p key={i} className="mt-1 text-xs text-faint">Nachricht {e.turn}: „{e.quote}“ – {e.comment}</p>)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
      </div>

      {ev.coach && (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Card><h2 className="mb-2 font-semibold text-success">Drei Stärken</h2><ol className="grid gap-1.5 text-sm text-muted">{ev.coach.strengths.map((x, i) => <li key={i}>{i + 1}. {x}</li>)}</ol></Card>
          <Card><h2 className="mb-2 font-semibold text-warning">Drei Verbesserungen</h2><ol className="grid gap-1.5 text-sm text-muted">{ev.coach.improvements.map((x, i) => <li key={i}>{i + 1}. {x}</li>)}</ol></Card>
        </div>
      )}
      {ev.coach?.violations.length ? (
        <Card className="mt-4 border-danger/40"><h2 className="mb-2 font-semibold text-danger">Grenzverletzungen (belegt)</h2><ul className="grid gap-1 text-sm">{ev.coach.violations.map((v, i) => <li key={i}>Nachricht {v.turn}: „{v.quote}“ – {v.rule}</li>)}</ul></Card>
      ) : null}
      {ev.coach?.improvedExample && (
        <Card className="mt-4">
          <h2 className="mb-3 font-semibold">Bessere Formulierung</h2>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-[var(--radius-sm)] border border-danger/40 p-3 text-sm"><p className="mb-1 text-xs text-faint">Du</p>„{ev.coach.improvedExample.original}“</div>
            <div className="rounded-[var(--radius-sm)] border border-success/40 p-3 text-sm"><p className="mb-1 text-xs text-faint">Besser</p>„{ev.coach.improvedExample.better}“</div>
          </div>
          <p className="mt-2 text-sm text-muted">{ev.coach.improvedExample.why}</p>
        </Card>
      )}
      <Card className="mt-4">
        <h2 className="mb-2 font-semibold">Passende Übungen</h2>
        <ul className="grid gap-1.5 text-sm">
          {(ev.coach?.exercises.length ? ev.coach.exercises : sc.reviewQuestionIds.slice(0, 2)).map((id) => {
            const l = lessonById(id);
            if (l) return <li key={id}><Link className="text-accent hover:underline" href={`/learn/${l.moduleId}/${l.id}/`}>Lektion: {l.title}</Link></li>;
            const q = questionById(id);
            return q ? <li key={id}><Link className="text-accent hover:underline" href={`/review/?focus=${id}`}>Übungsfrage: {q.prompt}</Link></li> : null;
          })}
        </ul>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={onRestart}>Neues Gespräch</Button>
          <ButtonLink href="/mistakes/" variant="secondary">Fehlergedächtnis</ButtonLink>
        </div>
      </Card>
      <details className="mt-4 rounded-[var(--radius)] border border-line p-4">
        <summary className="cursor-pointer text-sm font-medium">Gesprächsverlauf</summary>
        <ol className="mt-3 grid gap-1.5 text-sm">{st.transcript.map((t, i) => <li key={i}><span className="text-faint">[{i}] {t.role === "setter" ? "Du" : t.role === "customer" ? sc.persona.name : "System"}:</span> {t.text}</li>)}</ol>
      </details>
    </div>
  );
}
