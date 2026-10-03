"use client";
import Link from "next/link";
import { useState } from "react";
import { Badge, Button, ButtonLink, Card, Icon, PageHeader, ProgressBar } from "@/components/ui";
import { curriculum, moduleById, scenarios, sourceById } from "@/lib/content";
import { lessonMinutes, moduleMinutes } from "@/lib/content/minutes";
import { moduleProgress } from "@/lib/derived";
import { submitTransfer } from "@/lib/store/state";
import { update, useAcademy } from "@/lib/store/storage";

export default function ModuleOverview({ moduleId }: { moduleId: string }) {
  const s = useAcademy();
  const c = curriculum.find((x) => x.id === moduleId)!;
  const m = moduleById(moduleId);

  if (!m) {
    return (
      <div className="fade-in">
        <PageHeader eyebrow={`Modul ${c.number}`} title={c.title}>{c.subtitle}</PageHeader>
        <Card>
          <Badge>in Vorbereitung</Badge>
          <p className="mt-3 text-sm text-muted">Dieses Modul ist im Lehrplan vollständig geplant und wird nach Abschluss des Vertical Slice ausgearbeitet und fachlich geprüft.</p>
          <h2 className="mt-5 text-sm font-semibold">Geplante Themen</h2>
          <ul className="mt-2 grid gap-1.5 text-sm text-muted sm:grid-cols-2">
            {c.topics.map((t) => <li key={t}>• {t}</li>)}
          </ul>
          <ButtonLink href="/learn/" variant="secondary" className="mt-6"><Icon name="back" className="h-4 w-4" /> Zum Lernpfad</ButtonLink>
        </Card>
      </div>
    );
  }

  const p = moduleProgress(s, m.id);
  const sims = scenarios.filter((sc) => sc.reviewQuestionIds.some((q) => q.startsWith(`Q-${m.id}-`))).length;
  const mins = moduleMinutes(m, sims);
  return (
    <div className="fade-in">
      <PageHeader eyebrow={`Modul ${m.number} · Version ${m.version}`} title={m.title}>{m.subtitle}</PageHeader>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="grid gap-3 lg:col-span-2">
          {m.lessons.map((l, i) => {
            const done = !!s.lessonsCompleted[l.id];
            return (
              <Link key={l.id} href={`/learn/${m.id}/${l.id}/`} className="group">
                <Card className="flex items-center gap-4 transition-colors group-hover:border-line-strong">
                  <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl border text-sm ${done ? "border-success/50 bg-success/10 text-success" : "border-line text-muted"}`}>
                    {done ? <Icon name="check" className="h-4 w-4" /> : i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <h2 className="font-medium">{l.title}</h2>
                    <p className="text-xs text-faint">ca. {lessonMinutes(l)} Min. · {l.blocks.filter((b) => b.kind === "check").length} Abrufübungen{l.blocks.some((b) => b.kind === "book") && " · Kursbuch"}{l.blocks.some((b) => b.kind === "skill") && ` · ${l.blocks.filter((b) => b.kind === "skill").length} Skill-Karte(n)`}</p>
                  </div>
                  <Icon name="arrow" className="h-4 w-4 text-faint" />
                </Card>
              </Link>
            );
          })}
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold">Abschlussquiz</h2>
                <p className="text-sm text-muted">{m.examQuestionIds.length} Fragen · bestanden ab {m.passThreshold * 100} % · Wiederholung jederzeit möglich</p>
                {p.bestExam !== null && <p className="mt-1 text-xs text-faint">Bestes Ergebnis: {p.bestExam} % {p.examPassed && "· bestanden"}</p>}
              </div>
              <ButtonLink href={`/quiz/${m.id}/`}>{p.examPassed ? "Wiederholen" : "Starten"}</ButtonLink>
            </div>
          </Card>
          {m.transferTask && <TransferTask moduleId={m.id} task={m.transferTask} />}
        </div>
        <div className="grid content-start gap-4">
          <Card>
            <h2 className="mb-2 font-semibold">Fortschritt</h2>
            <ProgressBar value={p.ratio} label="Lektionen" />
            <p className="mt-2 text-sm text-muted">{p.lessonsDone} von {p.lessons} Lektionen</p>
          </Card>
          <Card>
            <h2 className="mb-2 font-semibold">Lernzeit (geschätzt)</h2>
            <p className="text-3xl font-semibold tabular-nums">{Math.floor(mins.total / 60)} h {mins.total % 60} min</p>
            <ul className="mt-2 grid gap-1 text-xs text-faint">
              <li>Lektionen & Kursbuch: {mins.lessons} min</li>
              <li>Abschlussquiz: {mins.exam} min</li>
              <li>Simulationen: {mins.sims} min</li>
              <li>Transferaufgabe: {mins.transfer} min</li>
            </ul>
            <p className="mt-2 text-[11px] text-faint">Annahme: 170 Wörter/Minute konzentriertes Lesen plus Übungszeit.</p>
          </Card>
          <Card>
            <h2 className="mb-2 font-semibold">Lernziele</h2>
            <ul className="grid gap-2 text-sm text-muted">
              {m.objectives.map((o) => <li key={o.id} className="flex gap-2"><Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-accent" />{o.text}</li>)}
            </ul>
          </Card>
          <Card>
            <h2 className="mb-2 font-semibold">Quellen</h2>
            <ul className="grid gap-1.5 text-xs text-muted">
              {m.sourceIds.map((id) => <li key={id}>{sourceById(id)?.title ?? id}</li>)}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}

function TransferTask({ moduleId, task }: { moduleId: string; task: { title: string; instructions: string; criteria: string[] } }) {
  const s = useAcademy();
  const prev = s.transferSubmissions[moduleId];
  const [text, setText] = useState(prev?.text ?? "");
  const [checks, setChecks] = useState<string[]>(prev?.selfCheck ?? []);
  const [saved, setSaved] = useState(false);
  return (
    <Card>
      <h2 className="font-semibold">{task.title}</h2>
      <p className="mt-1 text-sm text-muted">{task.instructions}</p>
      <textarea
        value={text}
        onChange={(e) => { setText(e.target.value); setSaved(false); }}
        rows={8}
        aria-label="Dein Leitfaden"
        className="mt-3 w-full rounded-[var(--radius-sm)] border border-line bg-elev p-3 text-base"
        placeholder="Dein Gesprächsleitfaden … (nur erfundene Daten)"
      />
      <fieldset className="mt-3">
        <legend className="mb-2 text-sm font-medium">Selbstcheck nach Bewertungskriterien</legend>
        <div className="grid gap-1.5">
          {task.criteria.map((c) => (
            <label key={c} className="flex min-h-10 items-start gap-3 text-sm text-muted">
              <input type="checkbox" className="mt-0.5 h-5 w-5 accent-[var(--accent)]" checked={checks.includes(c)} onChange={() => setChecks((x) => (x.includes(c) ? x.filter((y) => y !== c) : [...x, c]))} />
              {c}
            </label>
          ))}
        </div>
      </fieldset>
      <p className="mt-2 text-xs text-faint">Die Transferaufgabe wird nicht automatisch benotet. In der Pilotphase bewertet eine Person anhand der Kriterien (ASSESSMENT_RUBRIC.md).</p>
      <Button className="mt-3" disabled={text.trim().length < 50} onClick={() => { update((st) => submitTransfer(st, moduleId, text, checks, Date.now())); setSaved(true); }}>
        {prev ? "Aktualisieren" : "Abgeben"}
      </Button>
      {saved && <p role="status" className="mt-2 text-sm text-success">Gespeichert.</p>}
    </Card>
  );
}
