"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { QuestionRenderer } from "@/components/QuestionRenderer";
import { Badge, Button, Callout, Card, Icon } from "@/components/ui";
import { COURSE_VERSION, moduleById, questionById, sourceById } from "@/lib/content";
import { lessonMinutes } from "@/lib/content/minutes";
import { completeLesson, recordAnswer } from "@/lib/store/state";
import { update, useAcademy } from "@/lib/store/storage";
import type { LessonBlock } from "@/lib/types";

export default function LessonView({ moduleId, lessonId }: { moduleId: string; lessonId: string }) {
  const router = useRouter();
  const s = useAcademy();
  const m = moduleById(moduleId)!;
  const idx = m.lessons.findIndex((l) => l.id === lessonId);
  const lesson = m.lessons[idx]!;
  const next = m.lessons[idx + 1];
  const done = !!s.lessonsCompleted[lesson.id];
  const checks = lesson.blocks.filter((b) => b.kind === "check").length;
  const [answered, setAnswered] = useState<Set<string>>(new Set());

  function finish() {
    update((st) => completeLesson(st, lesson.id, COURSE_VERSION, Date.now()));
    router.push(next ? `/learn/${m.id}/${next.id}/` : `/learn/${m.id}/`);
  }

  return (
    <div className="fade-in mx-auto max-w-3xl">
      <nav className="mb-4 flex items-center gap-2 text-sm text-faint" aria-label="Brotkrumen">
        <Link href={`/learn/${m.id}/`} className="hover:text-fg">Modul {m.number}</Link>
        <span aria-hidden>/</span>
        <span>Lektion {idx + 1} von {m.lessons.length}</span>
      </nav>
      <header className="mb-6">
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight sm:text-3xl">{lesson.title}</h1>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge>ca. {lessonMinutes(lesson)} Min.</Badge>
          <Badge tone="accent">{checks} Abrufübungen</Badge>
          {done && <Badge tone="success">abgeschlossen</Badge>}
        </div>
      </header>

      <div className="grid gap-5">
        {lesson.blocks.map((b, i) => (
          <Block key={i} block={b} onAnswered={(qid) => setAnswered((x) => new Set(x).add(qid))} />
        ))}

        <Card>
          <h2 className="mb-2 font-semibold">Zusammenfassung</h2>
          <ul className="grid gap-1.5 text-sm text-muted">
            {lesson.summary.map((x) => <li key={x} className="flex gap-2"><Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-accent" />{x}</li>)}
          </ul>
          <p className="mt-4 text-xs text-faint">Quellen: {lesson.sourceIds.map((id) => sourceById(id)?.title ?? id).join(" · ")}</p>
        </Card>

        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-faint">{answered.size} von {checks} Abrufübungen beantwortet{answered.size < checks && " – empfohlen vor dem Abschluss"}</p>
          <Button onClick={finish} className="min-h-12">
            {done ? (next ? "Nächste Lektion" : "Zur Modulübersicht") : "Lektion abschließen"} <Icon name="arrow" className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function Block({ block: b, onAnswered }: { block: LessonBlock; onAnswered: (qid: string) => void }) {
  switch (b.kind) {
    case "text":
      return (
        <section>
          {b.title && <h2 className="mb-2 text-lg font-semibold">{b.title}</h2>}
          <div className="prose-lesson text-[15px] text-fg/90 sm:text-base">{b.body}</div>
        </section>
      );
    case "example":
      return (
        <Card className="border-l-2 border-l-accent">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-accent">Beispiel</p>
          <h3 className="mb-2 font-semibold">{b.title}</h3>
          <div className="prose-lesson text-sm text-muted">{b.body}</div>
        </Card>
      );
    case "workedExample":
      return (
        <Card>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-accent-2">Lösungsweg Schritt für Schritt</p>
          <h3 className="mb-3 font-semibold">{b.title}</h3>
          <ol className="grid gap-2">
            {b.steps.map((st, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent-2/15 text-xs font-semibold text-accent-2">{i + 1}</span>
                <span className="text-muted">{st}</span>
              </li>
            ))}
          </ol>
        </Card>
      );
    case "caseStudy":
      return (
        <Card>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-warning">Fallstudie</p>
          <h3 className="mb-2 font-semibold">{b.title}</h3>
          <p className="text-sm text-muted">{b.situation}</p>
          <details className="mt-3 rounded-[var(--radius-sm)] border border-line p-3">
            <summary className="min-h-8 cursor-pointer text-sm font-medium">Erst selbst überlegen – dann Analyse anzeigen</summary>
            <p className="mt-2 text-sm text-muted">{b.analysis}</p>
          </details>
          {b.simulationNote && <p className="mt-2 text-xs text-faint">{b.simulationNote}</p>}
        </Card>
      );
    case "callout":
      return <Callout tone={b.tone} title={b.title}>{b.body}</Callout>;
    case "book":
      return (
        <article className="rounded-[var(--radius)] border border-line bg-elev px-5 py-6 sm:px-8">
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-accent-2">Kursbuch · {b.chapter}</p>
          <h2 className="mb-4 font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight sm:text-2xl">{b.title}</h2>
          <div className="grid max-w-[68ch] gap-4 text-[16px] leading-[1.75] text-fg/90">
            {b.paragraphs.map((p, i) => <p key={i} className={i === 0 ? "first-letter:float-left first-letter:mr-2 first-letter:text-4xl first-letter:font-semibold first-letter:leading-none first-letter:text-accent" : ""}>{p}</p>)}
          </div>
          {b.sourceIds && <p className="mt-5 text-xs text-faint">Quellen: {b.sourceIds.map((id) => sourceById(id)?.title ?? id).join(" · ")}</p>}
        </article>
      );
    case "skill":
      return (
        <section className="overflow-hidden rounded-[var(--radius)] border border-accent/35 bg-surface">
          <header className="flex flex-wrap items-center gap-2 border-b border-line bg-accent/10 px-4 py-3">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">Skill-Karte</span>
            <span className="rounded-full border border-line px-2 py-0.5 text-[11px] text-muted">{({ psychologie: "Psychologie", gespraech: "Gesprächsführung", schreiben: "Schreiben", prozess: "Arbeitsweise" } as const)[b.category]}</span>
            <h3 className="w-full text-lg font-semibold">{b.name}</h3>
          </header>
          <div className="grid gap-4 p-4 text-sm">
            <p className="text-fg/90">{b.what}</p>
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-faint">So geht&apos;s</p>
              <ol className="grid gap-1.5">{b.how.map((h, i) => <li key={i} className="flex gap-2.5"><span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-accent/15 text-[11px] font-semibold text-accent">{i + 1}</span><span className="text-muted">{h}</span></li>)}</ol>
            </div>
            <div className="rounded-[var(--radius-sm)] border-l-2 border-accent bg-elev p-3"><p className="mb-1 text-xs font-semibold text-faint">Beispiel</p><p className="italic">{b.example}</p></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div><p className="mb-1 text-xs font-semibold uppercase tracking-wider text-faint">Warum es wirkt</p><p className="text-muted">{b.why}</p></div>
              <div><p className="mb-1 text-xs font-semibold uppercase tracking-wider text-faint">Was die Forschung sagt</p><p className="text-muted">{b.evidence}</p></div>
            </div>
            <p className="rounded-[var(--radius-sm)] border border-success/40 bg-success/5 p-3 text-muted"><span className="font-semibold text-success">Grenze: </span>{b.boundary}</p>
            <p className="text-xs text-faint">Quellen: {b.sourceIds.map((id) => sourceById(id)?.title ?? id).join(" · ")}</p>
          </div>
        </section>
      );
    case "myth":
      return (
        <section className="rounded-[var(--radius)] border border-warning/40 bg-surface p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-warning">Mythos-Check</p>
          <p className="text-sm line-through decoration-warning/70">{b.claim}</p>
          <p className="mt-2 text-sm text-fg/90"><span className="font-semibold">Stand der Forschung: </span>{b.reality}</p>
          <p className="mt-2 text-xs text-faint">Quellen: {b.sourceIds.map((id) => sourceById(id)?.title ?? id).join(" · ")}</p>
        </section>
      );
    case "reflect":
      return (
        <Card className="border-dashed">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-faint">Reflexion</p>
          <p className="text-sm">{b.prompt}</p>
          <textarea rows={3} aria-label="Notiz zur Reflexion (wird nicht gespeichert)" className="mt-3 w-full rounded-[var(--radius-sm)] border border-line bg-elev p-3 text-base" placeholder="Nur für dich – wird nicht gespeichert." />
        </Card>
      );
    case "check": {
      const q = questionById(b.questionId)!;
      return (
        <Card className="border-accent/30">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-accent">Abrufübung</p>
          <QuestionRenderer
            question={q}
            onAnswered={(r, meta) => {
              update((st) => recordAnswer(st, q, r, { ...meta, context: "lesson", now: Date.now() }));
              onAnswered(q.id);
            }}
          />
        </Card>
      );
    }
  }
}
