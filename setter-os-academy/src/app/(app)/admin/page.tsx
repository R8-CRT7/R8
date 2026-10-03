"use client";
import { useMemo, useState } from "react";
import { Badge, Button, Card, PageHeader, Stat } from "@/components/ui";
import { COURSE_VERSION, knowledge, modules, questions, scenarios, sources } from "@/lib/content";
import { validateContent } from "@/lib/content/validate";
import type { Question } from "@/lib/types";
import { useAcademy } from "@/lib/store/storage";

type Tab = "check" | "questions" | "scenarios" | "review" | "process";

export default function Admin() {
  const [tab, setTab] = useState<Tab>("check");
  const issues = useMemo(() => validateContent({ sources, knowledge, modules, questions, scenarios }), []);
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");
  return (
    <div className="fade-in">
      <PageHeader eyebrow="Adminbereich · Inhaltsverwaltung" title="Content Studio">
        Prototyp: lokal und ohne Rollenprüfung. In Produktion nur für Rollen „editor/reviewer/admin“ (Row-Level-Security). Änderungen werden nie automatisch veröffentlicht – sie entstehen als Entwurf und brauchen ein Review (Vier-Augen-Prinzip).
      </PageHeader>
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="Kursversion" value={COURSE_VERSION} />
        <Stat label="Fragen" value={questions.length} hint="Architektur ≥ 1.000" />
        <Stat label="Szenarien" value={scenarios.length} />
        <Stat label="Fehler" value={errors.length} />
        <Stat label="Warnungen" value={warnings.length} />
      </div>
      <div className="mb-4 flex gap-1 overflow-x-auto rounded-[var(--radius-sm)] border border-line p-1" role="tablist">
        {([["check", "Qualitätsprüfung"], ["questions", "Fragen bearbeiten"], ["scenarios", "Szenarien"], ["review", "Manuelle Prüfung"], ["process", "Aktualisierungsprozess"]] as [Tab, string][]).map(([t, l]) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`min-h-10 shrink-0 rounded-lg px-4 text-sm ${tab === t ? "bg-surface-strong text-fg" : "text-muted"}`}>{l}</button>
        ))}
      </div>
      {tab === "check" && (
        <Card>
          <h2 className="mb-3 font-semibold">Automatische Inhaltsprüfung</h2>
          {issues.length === 0 ? <p className="text-sm text-success">Keine Befunde.</p> : (
            <ul className="grid gap-2 text-sm">
              {issues.map((i, k) => (
                <li key={k} className="flex gap-2"><Badge tone={i.severity === "error" ? "danger" : "warning"}>{i.severity === "error" ? "Fehler" : "Warnung"}</Badge><span className="text-faint">{i.ref}</span><span className="text-muted">{i.message}</span></li>
              ))}
            </ul>
          )}
          <p className="mt-4 text-xs text-faint">Dieselben Regeln laufen als Test (npm test) – fehlerhafte Inhalte können nicht gebaut werden. Veraltete Quellen (Prüfintervall überschritten) werden als Warnung markiert.</p>
        </Card>
      )}
      {tab === "questions" && <QuestionEditor />}
      {tab === "scenarios" && (
        <div className="grid gap-3">
          {scenarios.map((s) => (
            <Card key={s.id}>
              <div className="flex flex-wrap items-center gap-2"><Badge>{s.id} · v{s.version}</Badge><Badge tone="accent">{s.archetype}</Badge></div>
              <h2 className="mt-2 font-medium">{s.title}</h2>
              <p className="mt-1 text-sm text-muted">{s.moves.length} Züge · {s.facts.length} verborgene Fakten · Ideal: {s.idealOutcome} · zulässig: {s.acceptableOutcomes.join(", ")}</p>
              <details className="mt-2"><summary className="cursor-pointer text-sm text-accent">Züge anzeigen</summary>
                <ul className="mt-2 grid gap-1 text-xs text-muted">{s.moves.map((m) => <li key={m.id}><Badge>{m.quality}</Badge> {m.id}: {m.text}{m.violation && <span className="text-danger"> · Verstoß: {m.violation}</span>}</li>)}</ul>
              </details>
            </Card>
          ))}
        </div>
      )}
      {tab === "review" && <ManualReview />}
      {tab === "process" && (
        <Card>
          <h2 className="mb-2 font-semibold">Aktualisierungsprozess (CONTENT_GUIDELINES.md)</h2>
          <ol className="grid gap-2 text-sm text-muted">
            <li>1. Quellen mit überschrittenem Prüfintervall erscheinen als Warnung (Recht: 14–90 Tage, Technik: 60–180 Tage, Forschung: 1–5 Jahre).</li>
            <li>2. Redakteur:in prüft die Quelle, aktualisiert Aussage + Prüfdatum, erhöht die Version der betroffenen Wissenseinträge und Fragen.</li>
            <li>3. Änderungen entstehen als Entwurf (Status „draft“). KI-Vorschläge sind als „ai_generated“ markiert.</li>
            <li>4. Eine zweite Person reviewt (Vier-Augen-Prinzip, in der Datenbank erzwungen) und veröffentlicht eine neue Kursversion.</li>
            <li>5. Alte Versuche behalten ihre Fragenversion – Ergebnisse werden nie rückwirkend verändert.</li>
            <li>6. Rechtsinhalte: jährliche Prüfung durch eine Rechtsanwältin/einen Rechtsanwalt; bei Gesetzesänderungen (z. B. FernUSG-Reform) sofort.</li>
          </ol>
        </Card>
      )}
    </div>
  );
}

function QuestionEditor() {
  const [id, setId] = useState(questions[0]!.id);
  const original = questions.find((q) => q.id === id)!;
  const [draft, setDraft] = useState<string>(JSON.stringify(original, null, 2));
  const [status, setStatus] = useState<string | null>(null);

  const parsed = useMemo(() => {
    try { return { q: JSON.parse(draft) as Question, err: null }; } catch (e) { return { q: null, err: (e as Error).message }; }
  }, [draft]);
  const issues = useMemo(() => {
    if (!parsed.q) return [];
    const qs = questions.map((q) => (q.id === id ? parsed.q! : q));
    return validateContent({ sources, knowledge, modules, questions: qs, scenarios }).filter((i) => i.ref === id && i.severity === "error");
  }, [parsed, id]);

  function exportDraft() {
    if (!parsed.q) return;
    const out = { ...parsed.q, version: original.version + 1, _status: "draft", _basedOn: `${original.id}@v${original.version}`, _editedAt: new Date().toISOString() };
    const blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${id}-v${out.version}-entwurf.json`;
    a.click();
    setStatus(`Entwurf ${id} v${out.version} exportiert – zur Prüfung einreichen. Nicht veröffentlicht.`);
  }

  const field = (k: "prompt" | "explanation") => (parsed.q ? (parsed.q as unknown as Record<string, string>)[k] ?? "" : "");
  const setField = (k: string, v: string | number) => { if (parsed.q) setDraft(JSON.stringify({ ...parsed.q, [k]: v }, null, 2)); };

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
      <Card className="max-h-[70dvh] overflow-y-auto p-2">
        <ul>
          {questions.map((q) => (
            <li key={q.id}>
              <button onClick={() => { setId(q.id); setDraft(JSON.stringify(q, null, 2)); setStatus(null); }} className={`w-full rounded-lg px-3 py-2 text-left text-sm ${q.id === id ? "bg-surface-strong" : "hover:bg-surface"}`}>
                <span className="block text-xs text-faint">{q.id} · {q.type} · v{q.version}</span>
                <span className="line-clamp-2">{q.prompt}</span>
              </button>
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <h2 className="font-semibold">{id} bearbeiten (Entwurf)</h2>
        <label className="mt-3 grid gap-1 text-sm">Fragetext<textarea rows={2} value={field("prompt")} onChange={(e) => setField("prompt", e.target.value)} className="rounded-[var(--radius-sm)] border border-line bg-elev p-2 text-base" /></label>
        <label className="mt-3 grid gap-1 text-sm">Erklärung<textarea rows={3} value={field("explanation")} onChange={(e) => setField("explanation", e.target.value)} className="rounded-[var(--radius-sm)] border border-line bg-elev p-2 text-base" /></label>
        <label className="mt-3 grid max-w-[200px] gap-1 text-sm">Schwierigkeit
          <select value={parsed.q?.difficulty ?? 1} onChange={(e) => setField("difficulty", Number(e.target.value))} className="min-h-11 rounded-[var(--radius-sm)] border border-line bg-elev px-2">{[1, 2, 3, 4, 5].map((d) => <option key={d}>{d}</option>)}</select>
        </label>
        <details className="mt-3"><summary className="cursor-pointer text-sm text-accent">Erweitert: Antwortoptionen & Lösung (JSON)</summary>
          <textarea rows={16} value={draft} onChange={(e) => setDraft(e.target.value)} spellCheck={false} className="mt-2 w-full rounded-[var(--radius-sm)] border border-line bg-elev p-2 font-mono text-xs" aria-label="Frage als JSON" />
        </details>
        {parsed.err && <p className="mt-2 text-sm text-danger">JSON-Fehler: {parsed.err}</p>}
        {issues.length > 0 && <ul className="mt-2 grid gap-1 text-sm text-danger">{issues.map((i, k) => <li key={k}>• {i.message}</li>)}</ul>}
        {draft !== JSON.stringify(original, null, 2) && <p className="mt-2 text-xs text-warning">Ungespeicherte Änderungen gegenüber v{original.version}.</p>}
        <div className="mt-4 flex flex-wrap gap-2">
          <Button disabled={!parsed.q || issues.length > 0} onClick={exportDraft}>Als Entwurf exportieren (v{original.version + 1})</Button>
          <Button variant="ghost" onClick={() => setDraft(JSON.stringify(original, null, 2))}>Zurücksetzen</Button>
        </div>
        {status && <p role="status" className="mt-2 text-sm text-success">{status}</p>}
      </Card>
    </div>
  );
}

function ManualReview() {
  const s = useAcademy();
  const subs = Object.entries(s.transferSubmissions);
  const freetext = s.attempts.filter((a) => questions.find((q) => q.id === a.questionId)?.type === "freetext");
  return (
    <div className="grid gap-4">
      <Card>
        <h2 className="font-semibold">Transferaufgaben ({subs.length})</h2>
        {subs.length === 0 ? <p className="mt-2 text-sm text-muted">Keine Abgaben.</p> : subs.map(([mid, sub]) => {
          const m = modules.find((x) => x.id === mid);
          return (
            <div key={mid} className="mt-3 rounded-[var(--radius-sm)] border border-line p-3 text-sm">
              <p className="text-xs text-faint">{mid} · {new Date(sub.at).toLocaleString("de-DE")} · Selbstcheck {sub.selfCheck.length}/{m?.transferTask?.criteria.length ?? 0}</p>
              <p className="mt-2 whitespace-pre-wrap text-muted">{sub.text}</p>
            </div>
          );
        })}
      </Card>
      <Card>
        <h2 className="font-semibold">Freitext-Selbstchecks ({freetext.length})</h2>
        <p className="mt-1 text-sm text-muted">Aus Datensparsamkeit speichert der Prototyp bei Freitext nur das Kriterienergebnis, nicht den Text. In der Pilotphase werden Freitexte bei Bedarf mit Einverständnis manuell geprüft.</p>
      </Card>
    </div>
  );
}
